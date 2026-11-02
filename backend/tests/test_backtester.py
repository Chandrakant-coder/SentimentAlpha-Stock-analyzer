import datetime
from app.database.models import PriceHistory, SentimentFactor
from app.database.repositories import StockRepository
from app.services.backtester import PortfolioBacktester

def test_backtester_execution_and_costs(db):
    stock_repo = StockRepository(db)
    stock = stock_repo.add_or_update("INFY", "INFY.NS", "Infosys Limited")

    # Insert 30 bars of prices and high sentiment on day 5, low on day 15
    base_date = datetime.datetime(2026, 1, 1)
    for i in range(30):
        dt = base_date + datetime.timedelta(days=i)
        price = 1000.0 + (i * 10)
        p = PriceHistory(
            stock_id=stock.id,
            date=dt,
            open=price - 2,
            high=price + 5,
            low=price - 5,
            close=price,
            volume=100000.0,
            ma_20=1000.0,
            ma_50=950.0,
            rsi_14=50.0,
        )
        db.add(p)

        # Bullish sentiment on day 5, bearish sentiment on day 15
        sent = 0.40 if i == 5 else (-0.20 if i == 15 else 0.0)
        f = SentimentFactor(
            stock_id=stock.id,
            date=dt,
            confidence_weighted_sentiment=sent,
            sentiment_momentum=0.10 if i == 5 else -0.10,
        )
        db.add(f)
    db.commit()

    backtester = PortfolioBacktester(db)
    res = backtester.run_backtest(
        symbol="INFY",
        strategy_type="simple_sentiment",
        initial_capital=100000.0,
        entry_sentiment_threshold=0.15,
        exit_sentiment_threshold=-0.05,
        transaction_cost_pct=0.001,
        slippage_pct=0.0005,
    )

    assert res["total_trades"] >= 1
    trade = res["trades"][0]
    # Signal was on day 5, execution must be on day 6!
    day5_date = (base_date + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    assert trade["entry_date"] > day5_date
    assert res["final_equity"] > 0
    assert len(res["equity_curve"]) == 30
