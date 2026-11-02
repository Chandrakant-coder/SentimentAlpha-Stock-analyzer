"""Yahoo Finance market-data ingestion.

Price policy
------------
Daily *charts* store Yahoo's unadjusted OHLC (auto_adjust=False via
yf.Ticker().history()):
  open / high / low / close / volume  == regular-session bars
  adj_close                           == split/dividend-adjusted close
                                         (falls back to close when absent)

Technical overlays shown on the price chart (MA20, MA50, RSI, MACD) are
computed from the unadjusted close so they sit on the same series the UI plots.

Return-style features used by ML (returns_1d, momentum_*, volatility_20d)
are computed from adj_close so corporate actions do not look like returns.

Yahoo daily bars are delayed historical session data, not a live quote.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.database.models import MarketDataSync, PriceHistory
from app.database.repositories import PriceRepository, StockRepository
from app.services.nse_calendar import IST, last_completed_nse_session, missing_expected_session

DownloadFn = Callable[[str, str], pd.DataFrame]


def download_yahoo_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch unadjusted daily OHLCV plus Adj Close from Yahoo Finance.

    Uses yf.Ticker().history() with auto_adjust=False, which returns a flat
    column index including 'Adj Close' alongside the unadjusted OHLC columns.
    The index is timezone-aware (IST +05:30); _session_index_to_ist_dates
    converts it to naive midnight dates.

    Falls back to yf.download() if Ticker.history() returns an empty frame.
    Retries once on transient failures before giving up.
    """
    import time as _time

    def _try_ticker_history() -> pd.DataFrame:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval="1d", auto_adjust=False, actions=False)
        return df if (df is not None and not df.empty) else pd.DataFrame()

    def _try_download() -> pd.DataFrame:
        return yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )

    # Attempt 1: Ticker.history()
    try:
        df = _try_ticker_history()
        if not df.empty:
            return df
    except Exception as e:
        logger.warning("Ticker.history() attempt 1 failed for %s: %s", ticker, e)

    # Brief pause then retry
    _time.sleep(1)

    # Attempt 2: Ticker.history() retry
    try:
        df = _try_ticker_history()
        if not df.empty:
            return df
    except Exception as e:
        logger.warning("Ticker.history() attempt 2 failed for %s: %s", ticker, e)

    # Attempt 3: yf.download() fallback
    logger.warning("Falling back to yf.download() for %s", ticker)
    try:
        df = _try_download()
        if not df.empty:
            return df
    except Exception as e:
        logger.warning("yf.download() fallback failed for %s: %s", ticker, e)

    # All attempts failed — return empty DataFrame so caller handles it gracefully
    logger.error("All yfinance download attempts failed for %s — returning empty frame", ticker)
    return pd.DataFrame()


def _flatten_yahoo_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names from either Ticker.history() or yf.download().

    Ticker.history() returns a flat Index like ['Open','High','Low','Close',
    'Adj Close','Volume','Dividends','Stock Splits'].

    yf.download() for a single ticker returns a MultiIndex like
    [('Adj Close','RELIANCE.NS'), ('Close','RELIANCE.NS'), ...].

    Both are reduced to simple strings: 'Open', 'High', 'Low', 'Close',
    'Adj Close', 'Volume'.
    """
    if isinstance(df.columns, pd.MultiIndex):
        # Level 0 = price-type name, level 1 = ticker symbol.  Keep level 0.
        df = df.copy()
        df.columns = [str(c[0]).strip() for c in df.columns]
    else:
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
    return df


def _session_index_to_ist_dates(index: pd.Index) -> pd.Series:
    """Convert a DatetimeIndex (tz-aware or naive) to naive midnight IST dates."""
    idx = pd.to_datetime(index)
    if getattr(idx, "tz", None) is not None:
        # tz-aware (e.g. +05:30 from Ticker.history) → convert to IST, strip tz
        idx = idx.tz_convert(IST).tz_localize(None)
    # Already naive (e.g. from yf.download) → treat as IST, just normalise
    return pd.Series(idx).dt.normalize()


def normalize_yahoo_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and standardise a yfinance daily frame.

    Returns a DataFrame with columns:
        date, open, high, low, close (unadjusted), adj_close, volume

    Invalid rows (zero/negative close, high < low, etc.) are dropped.
    Duplicate calendar dates keep the last occurrence.
    Stores row-skipped count in df.attrs['rows_skipped'].
    """
    if df is None or df.empty:
        return pd.DataFrame()

    work = _flatten_yahoo_columns(df)

    if "Close" not in work.columns:
        logger.warning("Yahoo frame missing Close column: %s", list(work.columns))
        return pd.DataFrame()

    work = work.reset_index()
    # After reset_index the old index becomes either 'Date' or the first column
    date_col = "Date" if "Date" in work.columns else work.columns[0]
    work["date"] = _session_index_to_ist_dates(work[date_col])

    adj_col = "Adj Close" if "Adj Close" in work.columns else None
    for required in ("Open", "High", "Low", "Close", "Volume"):
        if required not in work.columns:
            work[required] = np.nan

    out = pd.DataFrame(
        {
            "date": work["date"],
            "open": pd.to_numeric(work["Open"], errors="coerce"),
            "high": pd.to_numeric(work["High"], errors="coerce"),
            "low": pd.to_numeric(work["Low"], errors="coerce"),
            "close": pd.to_numeric(work["Close"], errors="coerce"),
            "volume": pd.to_numeric(work["Volume"], errors="coerce"),
            "adj_close": pd.to_numeric(work[adj_col], errors="coerce") if adj_col else np.nan,
        }
    )
    # When adj_close is entirely absent or all-NaN, default it to close
    if out["adj_close"].isna().all():
        out["adj_close"] = out["close"]

    valid = (
        out["close"].notna()
        & (out["close"] > 0)
        & out["open"].notna()
        & (out["open"] > 0)
        & out["high"].notna()
        & out["low"].notna()
        & (out["high"] >= out["low"])
        & (out["high"] >= out[["open", "close"]].max(axis=1))
        & (out["low"] <= out[["open", "close"]].min(axis=1))
        & out["volume"].notna()
        & (out["volume"] >= 0)
    )
    skipped = int((~valid).sum())
    if skipped:
        logger.warning("Dropped %s invalid Yahoo OHLC rows for this frame", skipped)
    out = out.loc[valid].copy()
    out = out.sort_values("date").drop_duplicates("date", keep="last")
    out.attrs["rows_skipped"] = skipped
    return out.reset_index(drop=True)


def attach_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical indicators.

    Chart overlays (MA20, MA50, RSI, MACD, volume_ratio) use unadjusted close.
    Return/momentum/volatility features use adj_close so splits and dividends
    don't appear as price moves.
    """
    if df.empty:
        return df
    close = df["close"].astype(float)
    adj = df["adj_close"].astype(float)

    df = df.copy()
    df["returns_1d"] = adj.pct_change()
    df["momentum_5d"] = adj.pct_change(5)
    df["momentum_20d"] = adj.pct_change(20)
    df["momentum_60d"] = adj.pct_change(60)
    df["ma_20"] = close.rolling(window=20).mean()
    df["ma_50"] = close.rolling(window=50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window=14).mean()
    loss = (-delta.clip(upper=0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["volatility_20d"] = df["returns_1d"].rolling(window=20).std()

    vol = df["volume"].astype(float)
    vol_ma_20 = vol.rolling(window=20).mean()
    df["volume_ratio"] = vol / vol_ma_20.replace(0, np.nan)
    return df


def _records_from_frame(df: pd.DataFrame) -> List[Dict[str, Any]]:
    indicator_keys = [
        "returns_1d", "momentum_5d", "momentum_20d", "momentum_60d",
        "ma_20", "ma_50", "rsi_14", "macd", "macd_signal",
        "volatility_20d", "volume_ratio",
    ]
    records: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        dt = row["date"]
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()
        rec: Dict[str, Any] = {
            "date": datetime.datetime(dt.year, dt.month, dt.day),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "adj_close": round(float(row["adj_close"]), 4) if pd.notna(row["adj_close"]) else None,
            "volume": float(row["volume"]),
        }
        for key in indicator_keys:
            val = row[key] if key in row else np.nan
            rec[key] = round(float(val), 6) if pd.notna(val) else None
        records.append(rec)
    return records


def build_sync_diagnostics(
    *,
    symbol: str,
    ticker: str,
    status: str,
    latest_market_date: Optional[datetime.datetime],
    last_attempt_at: Optional[datetime.datetime],
    last_success_at: Optional[datetime.datetime],
    records_fetched: int = 0,
    records_inserted: int = 0,
    records_updated: int = 0,
    records_skipped: int = 0,
    error: Optional[str] = None,
    now: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    expected = last_completed_nse_session(now)
    missing = missing_expected_session(latest_market_date, now=now)
    return {
        "symbol": symbol,
        "ticker": ticker,
        "currency": "INR",
        "provider": "yfinance",
        "close_field": "unadjusted_close",
        "adj_close_field": "adj_close",
        "status": status,
        "last_attempt_at": last_attempt_at,
        "last_success_at": last_success_at,
        "latest_market_date": latest_market_date,
        "expected_session_date": expected.isoformat(),
        "missing_expected_session": missing,
        "stale": status == "failed" or missing,
        "records_fetched": records_fetched,
        "records_inserted": records_inserted,
        "records_updated": records_updated,
        "records_skipped": records_skipped,
        "error": error,
    }


class MarketDataService:
    def __init__(self, db: Session, download_fn: Optional[DownloadFn] = None):
        self.db = db
        self.stock_repo = StockRepository(db)
        self.price_repo = PriceRepository(db)
        self._download = download_fn or download_yahoo_history

    def _upsert_sync_row(
        self,
        stock_id: int,
        ticker: str,
        *,
        status: str,
        error: Optional[str],
        fetched: int,
        inserted: int,
        updated: int,
        skipped: int,
        latest_market_date: Optional[datetime.datetime],
        success: bool,
    ) -> MarketDataSync:
        now = datetime.datetime.utcnow()
        row = (
            self.db.query(MarketDataSync)
            .filter(MarketDataSync.stock_id == stock_id)
            .first()
        )
        if not row:
            row = MarketDataSync(stock_id=stock_id, ticker=ticker)
            self.db.add(row)
        row.ticker = ticker
        row.provider = "yfinance"
        row.status = status
        row.last_attempt_at = now
        row.records_fetched = fetched
        row.records_inserted = inserted
        row.records_updated = updated
        row.records_skipped = skipped
        row.error_message = error
        row.close_field = "unadjusted_close"
        row.updated_at = now
        if success:
            row.last_success_at = now
            if latest_market_date is not None:
                row.latest_market_date = latest_market_date
        else:
            # Keep previously stored latest_market_date; do not erase existing history.
            existing_latest = (
                self.db.query(PriceHistory.date)
                .filter(PriceHistory.stock_id == stock_id)
                .order_by(PriceHistory.date.desc())
                .first()
            )
            if existing_latest:
                row.latest_market_date = existing_latest[0]
        self.db.commit()
        self.db.refresh(row)
        return row

    def _latest_stored_date(self, stock_id: int) -> Optional[datetime.datetime]:
        row = (
            self.db.query(PriceHistory.date)
            .filter(PriceHistory.stock_id == stock_id)
            .order_by(PriceHistory.date.desc())
            .first()
        )
        return row[0] if row else None

    def _is_stale(self, stock_id: int) -> bool:
        """True when the latest stored bar is older than the last completed NSE session."""
        latest = self._latest_stored_date(stock_id)
        return missing_expected_session(latest)

    def sync_symbol(self, symbol: str, period: str = "1y") -> Dict[str, Any]:
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            logger.warning("Stock symbol %s not found in database.", symbol)
            return build_sync_diagnostics(
                symbol=symbol.upper().replace(".NS", ""),
                ticker="",
                status="failed",
                latest_market_date=None,
                last_attempt_at=datetime.datetime.utcnow(),
                last_success_at=None,
                error="Unknown symbol",
            )

        ticker = stock.ticker
        logger.info("Downloading Yahoo daily bars for %s via Ticker.history (period=%s)", ticker, period)

        try:
            raw = self._download(ticker, period)
            normalized = normalize_yahoo_ohlc(raw)
            skipped_invalid = int(normalized.attrs.get("rows_skipped", 0)) if hasattr(normalized, "attrs") else 0

            if normalized.empty:
                logger.warning("No usable price data from yfinance for %s.", ticker)
                # If we already have recent data, treat this as a no-op rather than a failure
                # so the UI doesn't show stale/failed when data is actually current.
                existing_latest = self._latest_stored_date(stock.id)
                if existing_latest and not missing_expected_session(existing_latest):
                    logger.info(
                        "Provider returned empty for %s but stored data is current (%s). Keeping existing rows.",
                        ticker, existing_latest,
                    )
                    sync_row = self._upsert_sync_row(
                        stock.id, ticker,
                        status="success",
                        error=None,
                        fetched=0, inserted=0, updated=0, skipped=0,
                        latest_market_date=existing_latest,
                        success=True,
                    )
                    return build_sync_diagnostics(
                        symbol=stock.symbol, ticker=ticker,
                        status="success",
                        latest_market_date=sync_row.latest_market_date,
                        last_attempt_at=sync_row.last_attempt_at,
                        last_success_at=sync_row.last_success_at,
                        records_skipped=skipped_invalid,
                        error=None,
                    )
                sync_row = self._upsert_sync_row(
                    stock.id, ticker,
                    status="empty",
                    error="Provider returned no usable daily bars",
                    fetched=0, inserted=0, updated=0, skipped=skipped_invalid,
                    latest_market_date=existing_latest,
                    success=False,
                )
                return build_sync_diagnostics(
                    symbol=stock.symbol, ticker=ticker,
                    status=sync_row.status,
                    latest_market_date=sync_row.latest_market_date,
                    last_attempt_at=sync_row.last_attempt_at,
                    last_success_at=sync_row.last_success_at,
                    records_skipped=skipped_invalid,
                    error=sync_row.error_message,
                )

            framed = attach_indicators(normalized)
            records = _records_from_frame(framed)
            stats = self.price_repo.save_prices(stock.id, records)
            latest = records[-1]["date"] if records else self._latest_stored_date(stock.id)
            sync_row = self._upsert_sync_row(
                stock.id, ticker,
                status="success",
                error=None,
                fetched=len(records),
                inserted=stats["inserted"],
                updated=stats["updated"],
                skipped=stats["skipped"] + skipped_invalid,
                latest_market_date=latest,
                success=True,
            )
            logger.info(
                "Synced %s: fetched=%s inserted=%s updated=%s latest=%s",
                stock.symbol, len(records), stats["inserted"], stats["updated"], latest,
            )
            result = build_sync_diagnostics(
                symbol=stock.symbol, ticker=ticker,
                status="success",
                latest_market_date=sync_row.latest_market_date,
                last_attempt_at=sync_row.last_attempt_at,
                last_success_at=sync_row.last_success_at,
                records_fetched=len(records),
                records_inserted=stats["inserted"],
                records_updated=stats["updated"],
                records_skipped=stats["skipped"] + skipped_invalid,
                error=None,
            )
            result["records"] = records
            return result

        except Exception as e:
            logger.error("Error fetching price data for %s: %s", symbol, e, exc_info=True)
            sync_row = self._upsert_sync_row(
                stock.id, ticker,
                status="failed",
                error=str(e),
                fetched=0, inserted=0, updated=0, skipped=0,
                latest_market_date=self._latest_stored_date(stock.id),
                success=False,
            )
            return build_sync_diagnostics(
                symbol=stock.symbol, ticker=ticker,
                status="failed",
                latest_market_date=sync_row.latest_market_date,
                last_attempt_at=sync_row.last_attempt_at,
                last_success_at=sync_row.last_success_at,
                error=str(e),
            )

    def fetch_and_calculate_indicators(self, symbol: str, period: str = "1y") -> List[Dict[str, Any]]:
        result = self.sync_symbol(symbol, period=period)
        return result.get("records") or []

    def sync_all_stocks(self, period: str = "1y") -> Dict[str, Any]:
        stocks = self.stock_repo.get_all(active_only=True)
        results = []
        for stock in stocks:
            results.append(self.sync_symbol(stock.symbol, period=period))
        return {
            "symbols": len(results),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "results": results,
        }

    def sync_stale_stocks(self, period: str = "1y") -> Dict[str, Any]:
        """Sync only symbols whose latest stored bar is behind the expected NSE session.

        Called automatically at startup so the dashboard always reflects the
        latest available Yahoo Finance session without a manual trigger.
        """
        stocks = self.stock_repo.get_all(active_only=True)
        stale = [s for s in stocks if self._is_stale(s.id)]
        if not stale:
            logger.info("All %s stocks are current. No stale sync required.", len(stocks))
            return {"symbols": 0, "successful": 0, "failed": 0, "results": []}

        logger.info("Auto-syncing %s stale stock(s): %s", len(stale), [s.symbol for s in stale])
        results = []
        for stock in stale:
            results.append(self.sync_symbol(stock.symbol, period=period))
        return {
            "symbols": len(results),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "results": results,
        }

    def get_symbol_status(self, symbol: str) -> Dict[str, Any]:
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            return build_sync_diagnostics(
                symbol=symbol.upper().replace(".NS", ""),
                ticker="",
                status="failed",
                latest_market_date=None,
                last_attempt_at=None,
                last_success_at=None,
                error="Unknown symbol",
            )
        row = (
            self.db.query(MarketDataSync)
            .filter(MarketDataSync.stock_id == stock.id)
            .first()
        )
        latest = self._latest_stored_date(stock.id)
        if not row:
            return build_sync_diagnostics(
                symbol=stock.symbol,
                ticker=stock.ticker,
                status="never",
                latest_market_date=latest,
                last_attempt_at=None,
                last_success_at=None,
                error=None if latest else "Market data has never been synced",
            )
        return build_sync_diagnostics(
            symbol=stock.symbol,
            ticker=stock.ticker,
            status=row.status,
            latest_market_date=latest or row.latest_market_date,
            last_attempt_at=row.last_attempt_at,
            last_success_at=row.last_success_at,
            records_fetched=row.records_fetched or 0,
            records_inserted=row.records_inserted or 0,
            records_updated=row.records_updated or 0,
            records_skipped=row.records_skipped or 0,
            error=row.error_message,
        )
