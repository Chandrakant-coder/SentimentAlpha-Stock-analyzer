"""
Tests for market-data ingestion covering:
- Unadjusted close preserved correctly (auto_adjust=False)
- Adjusted close computed and stored separately
- Duplicate-safe upserts
- Refresh failure preserves existing records
- Stale-data detection via nse_calendar
- Correct latest-date selection from actual PriceHistory rows
- Indicator recalculation on new data
- Missing or empty provider responses handled gracefully
- Future-data leakage prevention in signal dates
"""
import datetime
import math
import pandas as pd
import numpy as np
import pytest

from app.database.models import PriceHistory, MarketDataSync
from app.database.repositories import StockRepository, PriceRepository
from app.services.price_data import (
    MarketDataService,
    normalize_yahoo_ohlc,
    attach_indicators,
    _records_from_frame,
    build_sync_diagnostics,
    download_yahoo_history,
)
from app.services.nse_calendar import (
    last_completed_nse_session,
    missing_expected_session,
    publication_session_date,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_yahoo_frame(n: int = 30, base_price: float = 1200.0) -> pd.DataFrame:
    """Return a minimal yfinance-style daily DataFrame with both Close and Adj Close."""
    idx = pd.date_range("2026-09-01", periods=n, freq="B")
    close = base_price + np.arange(n, dtype=float) * 2.0
    adj = close * 0.98  # Adj close slightly less (simulating a dividend adjustment)
    df = pd.DataFrame(
        {
            "Open": close - 5.0,
            "High": close + 10.0,
            "Low": close - 8.0,
            "Close": close,
            "Adj Close": adj,
            "Volume": np.full(n, 1_000_000, dtype=float),
        },
        index=idx,
    )
    df.index.name = "Date"
    return df


def _seed_stock(db, symbol="TESTSYM", ticker="TESTSYM.NS"):
    repo = StockRepository(db)
    return repo.add_or_update(symbol, ticker, f"{symbol} Limited")


# ---------------------------------------------------------------------------
# A. Unadjusted close preservation
# ---------------------------------------------------------------------------

class TestUnadjustedClose:
    def test_auto_adjust_false_preserves_regular_close(self):
        """normalize_yahoo_ohlc must keep Close unchanged from yfinance when auto_adjust=False."""
        raw = _make_raw_yahoo_frame(5, base_price=1184.50)
        normalized = normalize_yahoo_ohlc(raw)
        assert not normalized.empty
        # close should equal the raw Close column, NOT adj_close
        raw_closes = raw["Close"].values
        for i, row in normalized.iterrows():
            # row["close"] must match original Close within rounding
            assert abs(row["close"] - raw_closes[i]) < 0.001, (
                f"close {row['close']} != raw Close {raw_closes[i]} — auto_adjust may have been True"
            )

    def test_adj_close_differs_from_close_when_dividend_applied(self):
        """adj_close must be stored separately and differ from close when adjusted."""
        raw = _make_raw_yahoo_frame(5, base_price=11230.0)
        normalized = normalize_yahoo_ohlc(raw)
        for _, row in normalized.iterrows():
            # Our fixture sets Adj Close = Close * 0.98, so they differ
            assert row["adj_close"] < row["close"], (
                f"adj_close {row['adj_close']} should be < close {row['close']}"
            )

    def test_adj_close_falls_back_to_close_when_missing(self):
        """When Yahoo returns no Adj Close, adj_close must default to close."""
        raw = _make_raw_yahoo_frame(3)
        raw_no_adj = raw.drop(columns=["Adj Close"])
        normalized = normalize_yahoo_ohlc(raw_no_adj)
        for _, row in normalized.iterrows():
            assert abs(row["adj_close"] - row["close"]) < 0.001


# ---------------------------------------------------------------------------
# B. OHLC validation
# ---------------------------------------------------------------------------

class TestOHLCValidation:
    def test_invalid_ohlc_rows_are_dropped(self):
        """Rows where high < low or close <= 0 must be rejected."""
        raw = _make_raw_yahoo_frame(5)
        # Corrupt row 2: set High below Low
        raw.iloc[2, raw.columns.get_loc("High")] = raw.iloc[2]["Low"] - 1
        # Corrupt row 3: zero close
        raw.iloc[3, raw.columns.get_loc("Close")] = 0.0

        normalized = normalize_yahoo_ohlc(raw)
        assert len(normalized) == 3  # 2 corrupt rows dropped, 5 - 2 = 3
        assert all(normalized["close"] > 0)
        assert all(normalized["high"] >= normalized["low"])

    def test_empty_dataframe_returns_empty(self):
        normalized = normalize_yahoo_ohlc(pd.DataFrame())
        assert normalized.empty

    def test_dataframe_missing_close_returns_empty(self):
        df = pd.DataFrame({"Open": [100], "Volume": [10000]})
        normalized = normalize_yahoo_ohlc(df)
        assert normalized.empty


# ---------------------------------------------------------------------------
# C. Technical indicators
# ---------------------------------------------------------------------------

class TestIndicators:
    def test_ma20_uses_unadjusted_close(self):
        """MA20 must be computed on the unadjusted close series, not adj_close."""
        raw = _make_raw_yahoo_frame(50)
        normalized = normalize_yahoo_ohlc(raw)
        framed = attach_indicators(normalized)
        # After 20 bars, ma_20 must equal rolling mean of unadjusted close
        for idx in range(19, len(framed)):
            expected_ma = framed["close"].iloc[idx - 19: idx + 1].mean()
            assert abs(framed["ma_20"].iloc[idx] - expected_ma) < 0.01

    def test_returns_use_adj_close(self):
        """returns_1d must be pct_change of adj_close, not unadjusted close."""
        raw = _make_raw_yahoo_frame(10)
        normalized = normalize_yahoo_ohlc(raw)
        framed = attach_indicators(normalized)
        # Row 1: returns_1d = (adj[1] - adj[0]) / adj[0]
        adj = framed["adj_close"].values
        expected_r1 = (adj[1] - adj[0]) / adj[0]
        assert abs(framed["returns_1d"].iloc[1] - expected_r1) < 1e-6

    def test_rsi_bounded_0_100(self):
        raw = _make_raw_yahoo_frame(60)
        normalized = normalize_yahoo_ohlc(raw)
        framed = attach_indicators(normalized)
        valid_rsi = framed["rsi_14"].dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()

    def test_no_indicators_on_empty_frame(self):
        result = attach_indicators(pd.DataFrame())
        assert result.empty


# ---------------------------------------------------------------------------
# D. Database upserts
# ---------------------------------------------------------------------------

class TestDatabaseUpserts:
    def test_duplicate_upsert_updates_not_inserts(self, db):
        stock = _seed_stock(db)
        price_repo = PriceRepository(db)
        date = datetime.datetime(2026, 10, 22)

        records = [{
            "date": date, "open": 1180.0, "high": 1195.0, "low": 1170.0,
            "close": 1184.50, "adj_close": 1180.0, "volume": 5_000_000.0,
        }]
        stats = price_repo.save_prices(stock.id, records)
        assert stats["inserted"] == 1
        assert stats["updated"] == 0

        # Upsert same date with updated price
        records[0]["close"] = 1190.00
        stats2 = price_repo.save_prices(stock.id, records)
        assert stats2["inserted"] == 0
        assert stats2["updated"] == 1

        row = db.query(PriceHistory).filter(
            PriceHistory.stock_id == stock.id,
            PriceHistory.date == date,
        ).first()
        assert abs(row.close - 1190.00) < 0.001

    def test_invalid_record_is_skipped(self, db):
        stock = _seed_stock(db, symbol="SKIPTEST")
        price_repo = PriceRepository(db)
        records = [
            {"date": datetime.datetime(2026, 10, 1), "open": None, "high": 100.0,
             "low": 90.0, "close": 95.0, "volume": 10000.0},
        ]
        stats = price_repo.save_prices(stock.id, records)
        assert stats["skipped"] == 1
        assert stats["inserted"] == 0

    def test_negative_close_is_skipped(self, db):
        stock = _seed_stock(db, symbol="NEGTEST")
        price_repo = PriceRepository(db)
        records = [
            {"date": datetime.datetime(2026, 10, 1), "open": 100.0, "high": 105.0,
             "low": 95.0, "close": -10.0, "volume": 5000.0},
        ]
        stats = price_repo.save_prices(stock.id, records)
        assert stats["skipped"] == 1

    def test_no_duplicate_dates_stored(self, db):
        stock = _seed_stock(db, symbol="DUPTEST")
        price_repo = PriceRepository(db)
        date = datetime.datetime(2026, 10, 20)
        records = [
            {"date": date, "open": 100.0, "high": 105.0, "low": 95.0,
             "close": 102.0, "adj_close": 101.0, "volume": 10000.0},
            {"date": date, "open": 101.0, "high": 106.0, "low": 96.0,
             "close": 103.0, "adj_close": 102.0, "volume": 11000.0},
        ]
        price_repo.save_prices(stock.id, records)
        count = db.query(PriceHistory).filter(
            PriceHistory.stock_id == stock.id,
            PriceHistory.date == date,
        ).count()
        assert count == 1  # Only one row per (stock, date)


# ---------------------------------------------------------------------------
# E. Sync failure preserves existing records
# ---------------------------------------------------------------------------

class TestSyncFailurePreservation:
    def test_failed_sync_does_not_delete_existing_rows(self, db):
        stock = _seed_stock(db, symbol="FAILSYM")
        price_repo = PriceRepository(db)

        # Pre-populate 10 rows
        for i in range(10):
            dt = datetime.datetime(2026, 10, 1) + datetime.timedelta(days=i)
            price_repo.save_prices(stock.id, [{
                "date": dt, "open": 100.0, "high": 105.0,
                "low": 95.0, "close": 100.0 + i, "adj_close": 99.0 + i, "volume": 10000.0,
            }])

        pre_count = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).count()
        assert pre_count == 10

        # Simulate a failed download: pass a function that raises
        def failing_download(ticker, period):
            raise ConnectionError("Network timeout")

        service = MarketDataService(db, download_fn=failing_download)
        result = service.sync_symbol(stock.symbol)

        assert result["status"] == "failed"
        assert "Network timeout" in result["error"]

        post_count = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).count()
        assert post_count == pre_count, "Failed sync must not delete existing rows"

    def test_empty_provider_response_keeps_existing_data(self, db):
        stock = _seed_stock(db, symbol="EMPTYSYM")
        price_repo = PriceRepository(db)

        # Pre-populate 5 rows
        for i in range(5):
            dt = datetime.datetime(2026, 10, 1) + datetime.timedelta(days=i)
            price_repo.save_prices(stock.id, [{
                "date": dt, "open": 100.0, "high": 105.0,
                "low": 95.0, "close": 100.0 + i, "adj_close": 99.0, "volume": 5000.0,
            }])

        def empty_download(ticker, period):
            return pd.DataFrame()

        service = MarketDataService(db, download_fn=empty_download)
        result = service.sync_symbol(stock.symbol)

        assert result["status"] == "empty"
        post_count = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).count()
        assert post_count == 5


# ---------------------------------------------------------------------------
# F. Stale-data detection
# ---------------------------------------------------------------------------

class TestStalenessDetection:
    def test_weekday_latest_is_not_stale(self):
        """If latest_market_date == last_completed_nse_session, not stale."""
        expected = last_completed_nse_session(
            datetime.datetime(2026, 10, 23, 17, 0, 0)  # Friday evening IST
        )
        assert not missing_expected_session(expected, datetime.datetime(2026, 10, 23, 17, 0))

    def test_saturday_expected_session_is_friday(self):
        """On Saturday, expected session must be Friday."""
        saturday = datetime.datetime(2026, 10, 24, 10, 0, 0)
        expected = last_completed_nse_session(saturday)
        assert expected.weekday() == 4  # Friday

    def test_missing_session_detected(self):
        """If latest_market_date is 2 days before expected, missing_expected_session is True."""
        old_date = datetime.datetime(2026, 10, 21)  # Wednesday
        now = datetime.datetime(2026, 10, 24, 10, 0)  # Saturday; expected = Friday
        assert missing_expected_session(old_date, now=now)

    def test_build_sync_diagnostics_marks_stale_when_missing_session(self):
        old_date = datetime.datetime(2026, 10, 21)
        now = datetime.datetime(2026, 10, 24, 10, 0)
        diag = build_sync_diagnostics(
            symbol="RELIANCE",
            ticker="RELIANCE.NS",
            status="success",
            latest_market_date=old_date,
            last_attempt_at=now,
            last_success_at=now,
            now=now,
        )
        assert diag["missing_expected_session"] is True
        assert diag["stale"] is True

    def test_build_sync_diagnostics_not_stale_when_current(self):
        # Friday evening: expected = Friday, latest = Friday → not stale
        friday_evening = datetime.datetime(2026, 10, 23, 17, 0)
        friday_date = datetime.datetime(2026, 10, 23)
        diag = build_sync_diagnostics(
            symbol="RELIANCE",
            ticker="RELIANCE.NS",
            status="success",
            latest_market_date=friday_date,
            last_attempt_at=friday_evening,
            last_success_at=friday_evening,
            now=friday_evening,
        )
        assert diag["missing_expected_session"] is False
        # stale is False only when not missing and status != failed
        assert diag["stale"] is False


# ---------------------------------------------------------------------------
# G. Latest-date selection from actual DB rows
# ---------------------------------------------------------------------------

class TestLatestDateSelection:
    def test_latest_date_from_price_history(self, db):
        stock = _seed_stock(db, symbol="LATESTSYM")
        price_repo = PriceRepository(db)

        dates = [
            datetime.datetime(2026, 10, 20),
            datetime.datetime(2026, 10, 21),
            datetime.datetime(2026, 10, 22),
        ]
        for dt in dates:
            price_repo.save_prices(stock.id, [{
                "date": dt, "open": 100.0, "high": 110.0, "low": 90.0,
                "close": 105.0, "adj_close": 104.0, "volume": 10000.0,
            }])

        service = MarketDataService(db)
        latest = service._latest_stored_date(stock.id)
        assert latest == datetime.datetime(2026, 10, 22)

    def test_status_uses_actual_price_history_not_sync_row(self, db):
        """get_symbol_status must derive latest_market_date from PriceHistory, not sync metadata."""
        stock = _seed_stock(db, symbol="STATUSSYM")
        price_repo = PriceRepository(db)
        price_repo.save_prices(stock.id, [{
            "date": datetime.datetime(2026, 10, 22), "open": 200.0,
            "high": 210.0, "low": 190.0, "close": 205.0, "adj_close": 204.0, "volume": 20000.0,
        }])

        service = MarketDataService(db)
        status = service.get_symbol_status(stock.symbol)
        # latest_market_date must reflect actual PriceHistory
        assert status["latest_market_date"] is not None
        latest_date = status["latest_market_date"]
        if hasattr(latest_date, "date"):
            latest_date = latest_date.date()
        assert str(latest_date)[:10] == "2026-10-22"


# ---------------------------------------------------------------------------
# H. Full sync round-trip with mocked yfinance
# ---------------------------------------------------------------------------

class TestSyncRoundTrip:
    def test_sync_stores_unadjusted_close_and_adj_close(self, db):
        stock = _seed_stock(db, symbol="SYNCSYM")
        raw = _make_raw_yahoo_frame(30, base_price=1200.0)

        service = MarketDataService(db, download_fn=lambda t, p: raw)
        result = service.sync_symbol(stock.symbol)

        assert result["status"] == "success"
        assert result["records_fetched"] == 30
        assert result["records_inserted"] == 30

        rows = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).order_by(PriceHistory.date).all()
        assert len(rows) == 30

        # Unadjusted close must differ from adj_close (fixture sets adj = close * 0.98)
        for row in rows:
            assert row.close > row.adj_close, (
                f"close {row.close} should be > adj_close {row.adj_close}"
            )

    def test_sync_recalculates_indicators_after_new_prices(self, db):
        stock = _seed_stock(db, symbol="INDSYM")
        raw = _make_raw_yahoo_frame(60)

        service = MarketDataService(db, download_fn=lambda t, p: raw)
        result = service.sync_symbol(stock.symbol)

        # After 60 bars, MA20 must be populated
        rows = db.query(PriceHistory).filter(
            PriceHistory.stock_id == stock.id,
            PriceHistory.ma_20 != None,
        ).count()
        assert rows >= 41  # 60 - 19 warmup rows have MA20

    def test_sync_idempotent_on_second_run(self, db):
        stock = _seed_stock(db, symbol="IDEMSYM")
        raw = _make_raw_yahoo_frame(20)

        service = MarketDataService(db, download_fn=lambda t, p: raw)
        r1 = service.sync_symbol(stock.symbol)
        r2 = service.sync_symbol(stock.symbol)

        assert r1["records_inserted"] == 20
        # Second run: all rows already exist, should be updates not inserts
        assert r2["records_inserted"] == 0
        assert r2["records_updated"] == 20

        total = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).count()
        assert total == 20


# ---------------------------------------------------------------------------
# I. Future-data leakage prevention
# ---------------------------------------------------------------------------

class TestNoFutureDataLeakage:
    def test_publication_after_close_mapped_to_next_day(self):
        """Article published at 16:00 IST must be mapped to the next calendar day,
        not the same-session close signal date."""
        # 16:00 IST is after 15:30 NSE cash close
        pub_at = datetime.datetime(2026, 10, 22, 16, 0, 0)  # naive, treated as IST
        session_date = publication_session_date(pub_at)
        assert session_date == datetime.date(2026, 10, 23), (
            f"Article at 16:00 IST on 22nd must map to 23rd, got {session_date}"
        )

    def test_publication_before_close_maps_to_same_day(self):
        """Article published at 09:00 IST should map to the same day."""
        pub_at = datetime.datetime(2026, 10, 22, 9, 0, 0)
        session_date = publication_session_date(pub_at)
        assert session_date == datetime.date(2026, 10, 22)

    def test_signal_date_not_ahead_of_latest_price(self, db):
        """SignalGeneratorService must use the latest_price.date as signal_date,
        not a future date injected from news."""
        from app.database.models import PriceHistory, SentimentFactor
        from app.services.signal_generator import SignalGeneratorService

        stock_repo = StockRepository(db)
        stock = stock_repo.add_or_update("FUTSYM", "FUTSYM.NS", "Future Sym Ltd")

        # Latest price: 2026-10-22
        price_date = datetime.datetime(2026, 10, 22)
        ph = PriceHistory(
            stock_id=stock.id, date=price_date,
            open=1000.0, high=1020.0, low=990.0, close=1010.0,
            volume=50000.0, ma_20=1005.0, ma_50=990.0, rsi_14=55.0,
        )
        db.add(ph)

        # Sentiment factor: also 2026-10-22 (same day, before close)
        sf = SentimentFactor(
            stock_id=stock.id, date=price_date,
            confidence_weighted_sentiment=0.25, sentiment_momentum=0.1, article_count=3,
        )
        db.add(sf)
        db.commit()

        # Add a "future" sentiment factor on 2026-10-25 (should NOT be used)
        future_sf = SentimentFactor(
            stock_id=stock.id, date=datetime.datetime(2026, 10, 25),
            confidence_weighted_sentiment=0.99, sentiment_momentum=0.5, article_count=10,
        )
        db.add(future_sf)
        db.commit()

        gen = SignalGeneratorService(db)
        result = gen.generate_signal_for_stock("FUTSYM")

        # Signal date must equal latest price date
        sig_date_str = result["signal_date"][:10]
        assert sig_date_str == "2026-10-22", (
            f"Signal date {sig_date_str} must not be ahead of latest price date 2026-10-22"
        )


# ---------------------------------------------------------------------------
# J. API response consistency
# ---------------------------------------------------------------------------

class TestAPIResponseConsistency:
    def test_prices_endpoint_returns_unadjusted_close_field(self, client, db):
        from app.database.repositories import StockRepository, PriceRepository

        stock_repo = StockRepository(db)
        stock = stock_repo.add_or_update("APITEST", "APITEST.NS", "API Test Stock")

        price_repo = PriceRepository(db)
        price_repo.save_prices(stock.id, [{
            "date": datetime.datetime(2026, 10, 22),
            "open": 1180.0, "high": 1200.0, "low": 1170.0,
            "close": 1184.50, "adj_close": 1179.0, "volume": 3_000_000.0,
        }])

        res = client.get(f"/api/stocks/APITEST/prices")
        assert res.status_code == 200
        bars = res.json()
        assert len(bars) >= 1
        bar = bars[0]
        # close must be unadjusted
        assert abs(bar["close"] - 1184.50) < 0.01
        # adj_close must be present and different
        assert bar["adj_close"] is not None
        assert abs(bar["adj_close"] - 1179.0) < 0.01
        # date must be a parseable ISO string with correct date
        assert bar["date"][:10] == "2026-10-22"

    def test_market_status_endpoint_includes_freshness_fields(self, client, db):
        from app.database.repositories import StockRepository

        stock_repo = StockRepository(db)
        stock_repo.add_or_update("FRESHTEST", "FRESHTEST.NS", "Freshness Test Stock")

        res = client.get("/api/stocks/FRESHTEST/prices/status")
        assert res.status_code == 200
        data = res.json()
        required = {
            "symbol", "ticker", "status", "latest_market_date",
            "expected_session_date", "missing_expected_session",
            "stale", "records_fetched",
        }
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_sync_endpoint_200_does_not_guarantee_freshness(self, client, db):
        """POST /sync must still return 200 even when provider returns empty data,
        but status field must indicate the problem."""
        from app.database.repositories import StockRepository
        from unittest.mock import patch

        stock_repo = StockRepository(db)
        stock_repo.add_or_update("SYNCFAIL", "SYNCFAIL.NS", "Sync Fail Stock")

        with patch("app.api.routes.stocks.MarketDataService") as MockService:
            instance = MockService.return_value
            instance.sync_symbol.return_value = {
                "symbol": "SYNCFAIL",
                "ticker": "SYNCFAIL.NS",
                "currency": "INR",
                "provider": "yfinance",
                "close_field": "unadjusted_close",
                "adj_close_field": "adj_close",
                "status": "failed",
                "last_attempt_at": "2026-10-24T10:00:00",
                "last_success_at": None,
                "latest_market_date": None,
                "expected_session_date": "2026-10-23",
                "missing_expected_session": True,
                "stale": True,
                "records_fetched": 0,
                "records_inserted": 0,
                "records_updated": 0,
                "records_skipped": 0,
                "error": "Provider timeout",
            }

            res = client.post("/api/stocks/SYNCFAIL/sync")
            assert res.status_code == 200  # HTTP 200 is correct
            data = res.json()
            # But status field must expose the failure
            assert data["status"] == "failed"
            assert data["stale"] is True
            assert data["error"] is not None
