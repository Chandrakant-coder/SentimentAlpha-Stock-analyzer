import uuid
import json
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.models import Stock, PriceHistory, SentimentFactor, BacktestRun, BacktestTrade
from app.database.repositories import StockRepository

class PortfolioBacktester:
    def __init__(self, db: Session):
        self.db = db
        self.stock_repo = StockRepository(db)

    def run_backtest(
        self,
        symbol: str,
        strategy_type: str = "sentiment_momentum",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 100000.0,
        entry_sentiment_threshold: float = 0.15,
        exit_sentiment_threshold: float = -0.05,
        transaction_cost_pct: float = 0.001,  # 10 bps
        slippage_pct: float = 0.0005,          # 5 bps
    ) -> Dict[str, Any]:
        """
        Executes a leak-free long-only backtest for a specific stock.
        Signals calculated at session t close are executed at session t+1.
        Deducts transaction costs and slippage on both entry and exit.
        """
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            raise ValueError(f"Stock {symbol} not found")

        # Load price history
        q_prices = self.db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id)
        if start_date:
            q_prices = q_prices.filter(PriceHistory.date >= datetime.datetime.fromisoformat(start_date))
        if end_date:
            q_prices = q_prices.filter(PriceHistory.date <= datetime.datetime.fromisoformat(end_date))
        prices = q_prices.order_by(PriceHistory.date.asc()).all()

        # Auto-sync prices if missing
        if len(prices) < 20:
            from app.services.price_data import MarketDataService
            mds = MarketDataService(self.db)
            mds.fetch_and_calculate_indicators(stock.symbol)
            q_prices = self.db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id)
            if start_date:
                q_prices = q_prices.filter(PriceHistory.date >= datetime.datetime.fromisoformat(start_date))
            if end_date:
                q_prices = q_prices.filter(PriceHistory.date <= datetime.datetime.fromisoformat(end_date))
            prices = q_prices.order_by(PriceHistory.date.asc()).all()

        if len(prices) < 20:
            raise ValueError(f"Insufficient price history ({len(prices)} bars) for backtesting {symbol}")

        # Load sentiment factors
        factors = (
            self.db.query(SentimentFactor)
            .filter(SentimentFactor.stock_id == stock.id)
            .order_by(SentimentFactor.date.asc())
            .all()
        )
        factor_map = {f.date.strftime("%Y-%m-%d"): f for f in factors}

        # Build chronological bars with post-event sentiment drift / decay
        current_sentiment = 0.0
        current_mom = 0.0
        decay = 0.85

        bars = []
        for p in prices:
            d_str = p.date.strftime("%Y-%m-%d")
            f = factor_map.get(d_str)
            if f and f.confidence_weighted_sentiment is not None:
                current_sentiment = f.confidence_weighted_sentiment
                current_mom = f.sentiment_momentum or 0.0
            else:
                current_sentiment *= decay
                current_mom *= decay

            bars.append({
                "date": p.date,
                "date_str": d_str,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
                "ma_20": p.ma_20 or p.close,
                "ma_50": p.ma_50 or p.close,
                "rsi_14": p.rsi_14 or 50.0,
                "sentiment": round(current_sentiment, 4),
                "sentiment_momentum": round(current_mom, 4),
            })

        # Simulation state
        cash = initial_capital
        position_shares = 0
        entry_price = 0.0
        entry_date = None
        trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []

        # Benchmark initial close for Buy & Hold
        bench_start_price = bars[0]["close"]

        # Track pending order generated at end of day t, executed at t+1 open
        pending_order = None  # ("BUY" or "SELL", reason)

        for i, bar in enumerate(bars):
            current_date = bar["date"]
            open_price = bar["open"] if bar["open"] > 0 else bar["close"]
            close_price = bar["close"]

            # 1. Execute pending orders at market open of session t+1
            if pending_order:
                action, reason = pending_order
                pending_order = None

                if action == "BUY" and position_shares == 0:
                    effective_price = open_price * (1.0 + slippage_pct)
                    trade_cost_rate = 1.0 + transaction_cost_pct
                    affordable_shares = int(cash / (effective_price * trade_cost_rate))
                    if affordable_shares > 0:
                        total_cost = affordable_shares * effective_price
                        fees = total_cost * transaction_cost_pct
                        cash -= (total_cost + fees)
                        position_shares = affordable_shares
                        entry_price = effective_price
                        entry_date = current_date
                        logger.debug(f"BUY executed on {current_date}: {position_shares} shares @ {effective_price:.2f}")

                elif action == "SELL" and position_shares > 0:
                    effective_price = open_price * (1.0 - slippage_pct)
                    gross_proceeds = position_shares * effective_price
                    fees = gross_proceeds * transaction_cost_pct
                    net_proceeds = gross_proceeds - fees
                    cash += net_proceeds
                    pnl = net_proceeds - (position_shares * entry_price)
                    ret_pct = ((effective_price / entry_price) - 1.0) * 100.0

                    trades.append({
                        "symbol": stock.symbol,
                        "entry_date": entry_date,
                        "exit_date": current_date,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(effective_price, 2),
                        "shares": position_shares,
                        "pnl": round(pnl, 2),
                        "return_pct": round(ret_pct, 2),
                        "exit_reason": reason,
                    })
                    logger.debug(f"SELL executed on {current_date}: {position_shares} shares @ {effective_price:.2f}, PnL: {pnl:.2f}")
                    position_shares = 0
                    entry_price = 0.0
                    entry_date = None

            # 2. Record daily mark-to-market equity
            current_portfolio_value = cash + (position_shares * close_price)
            bench_value = initial_capital * (close_price / bench_start_price)
            equity_curve.append({
                "date": bar["date_str"],
                "strategy_equity": round(current_portfolio_value, 2),
                "benchmark_equity": round(bench_value, 2),
                "cash": round(cash, 2),
                "invested": round(position_shares * close_price, 2),
            })

            # 3. Generate signals at end of day based on day's close and sentiment
            # Scheduled for execution next morning to prevent look-ahead bias
            sent = bar["sentiment"]
            sent_mom = bar["sentiment_momentum"]
            rsi = bar["rsi_14"]
            ma20 = bar["ma_20"]
            ma50 = bar["ma_50"]

            if strategy_type == "sentiment_momentum":
                # Confluence entry: positive news sentiment + upward technical trend
                # OR strong trend breakout when news is non-negative
                sentiment_entry = (sent >= entry_sentiment_threshold) and (close_price >= ma20 * 0.99)
                trend_entry = (close_price > ma20) and (ma20 >= ma50 * 0.99) and (45 <= rsi <= 72) and (sent >= exit_sentiment_threshold)
                buy_condition = sentiment_entry or trend_entry
                
                # Exit when sentiment deteriorates or trend reverses/overbought
                sell_condition = (sent <= exit_sentiment_threshold and sent < 0) or (rsi > 78) or (close_price < ma50 * 0.97)
            else:
                # Pure sentiment threshold strategy
                sentiment_active = any(b["sentiment"] != 0 for b in bars)
                if sentiment_active:
                    buy_condition = sent >= entry_sentiment_threshold
                    sell_condition = sent <= exit_sentiment_threshold
                else:
                    buy_condition = (close_price > ma20) and (rsi < 68)
                    sell_condition = (close_price < ma20) or (rsi > 75)

            if position_shares == 0 and buy_condition:
                reason = "Sentiment Entry" if sent >= entry_sentiment_threshold else "Trend & Momentum Entry"
                pending_order = ("BUY", reason)
            elif position_shares > 0 and sell_condition:
                reason = "Negative Sentiment Exit" if sent <= exit_sentiment_threshold and sent < 0 else "Technical Trend Exit"
                pending_order = ("SELL", reason)

        # Close any open position at the final session close
        if position_shares > 0:
            final_bar = bars[-1]
            final_price = final_bar["close"] * (1.0 - slippage_pct)
            gross = position_shares * final_price
            fees = gross * transaction_cost_pct
            net = gross - fees
            cash += net
            pnl = net - (position_shares * entry_price)
            ret_pct = ((final_price / entry_price) - 1.0) * 100.0
            trades.append({
                "symbol": stock.symbol,
                "entry_date": entry_date,
                "exit_date": final_bar["date"],
                "entry_price": round(entry_price, 2),
                "exit_price": round(final_price, 2),
                "shares": position_shares,
                "pnl": round(pnl, 2),
                "return_pct": round(ret_pct, 2),
                "exit_reason": "End of Backtest Period",
            })
            equity_curve[-1]["strategy_equity"] = round(cash, 2)
            equity_curve[-1]["cash"] = round(cash, 2)
            equity_curve[-1]["invested"] = 0.0

        # Calculate Performance Metrics
        final_equity = equity_curve[-1]["strategy_equity"]
        total_return = ((final_equity / initial_capital) - 1.0) * 100.0
        final_bench = equity_curve[-1]["benchmark_equity"]
        benchmark_return = ((final_bench / initial_capital) - 1.0) * 100.0

        eq_series = pd.Series([e["strategy_equity"] for e in equity_curve])
        daily_returns = eq_series.pct_change().dropna()

        # Drawdown calculation
        running_max = eq_series.cummax()
        drawdown = (eq_series - running_max) / running_max
        max_drawdown = float(drawdown.min() * 100.0) if not drawdown.empty else 0.0

        drawdown_series = [
            {"date": e["date"], "drawdown": round(float(dd) * 100.0, 2)}
            for e, dd in zip(equity_curve, drawdown)
        ]

        # Annualized return (CAGR) and Sharpe Ratio
        n_days = max(1, len(equity_curve))
        years = n_days / 252.0
        cagr = ((final_equity / initial_capital) ** (1.0 / years) - 1.0) * 100.0 if years > 0 and final_equity > 0 else total_return

        volatility = float(daily_returns.std() * np.sqrt(252) * 100.0) if len(daily_returns) > 1 else 0.0
        # Assume 6% risk-free rate for Indian markets
        rf_daily = (1.06 ** (1 / 252)) - 1.0
        excess_daily_returns = daily_returns - rf_daily
        sharpe = float((excess_daily_returns.mean() / daily_returns.std()) * np.sqrt(252)) if len(daily_returns) > 1 and daily_returns.std() > 0 else 0.0

        # Trade metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] < 0]
        win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        # Generate unique Backtest ID and persist
        backtest_id = f"bt_{symbol.lower()}_{uuid.uuid4().hex[:8]}"
        config_params = {
            "symbol": symbol,
            "strategy_type": strategy_type,
            "initial_capital": initial_capital,
            "entry_sentiment_threshold": entry_sentiment_threshold,
            "exit_sentiment_threshold": exit_sentiment_threshold,
            "transaction_cost_pct": transaction_cost_pct,
            "slippage_pct": slippage_pct,
        }

        db_run = BacktestRun(
            backtest_id=backtest_id,
            name=f"{symbol} {strategy_type.title()} Backtest",
            strategy_type=strategy_type,
            start_date=bars[0]["date"],
            end_date=bars[-1]["date"],
            initial_capital=initial_capital,
            final_equity=round(final_equity, 2),
            total_return=round(total_return, 2),
            benchmark_return=round(benchmark_return, 2),
            cagr=round(cagr, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown=round(max_drawdown, 2),
            win_rate=round(win_rate, 2),
            total_trades=total_trades,
            profit_factor=round(profit_factor, 2),
            equity_curve=json.dumps(equity_curve),
            drawdown_series=json.dumps(drawdown_series),
            config_params=json.dumps(config_params),
            created_at=datetime.datetime.utcnow(),
        )
        self.db.add(db_run)
        self.db.commit()
        self.db.refresh(db_run)

        # Save individual trades
        for t in trades:
            db_trade = BacktestTrade(
                backtest_run_id=db_run.id,
                stock_id=stock.id,
                symbol=t["symbol"],
                entry_date=t["entry_date"],
                exit_date=t["exit_date"],
                entry_price=t["entry_price"],
                exit_price=t["exit_price"],
                shares=t["shares"],
                pnl=t["pnl"],
                return_pct=t["return_pct"],
                exit_reason=t["exit_reason"],
            )
            self.db.add(db_trade)
        self.db.commit()

        logger.info(f"Backtest {backtest_id} complete: Return={total_return:.2f}%, Sharpe={sharpe:.2f}, Trades={total_trades}")
        return {
            "id": db_run.id,
            "backtest_id": backtest_id,
            "name": db_run.name,
            "strategy_type": strategy_type,
            "start_date": db_run.start_date.isoformat(),
            "end_date": db_run.end_date.isoformat(),
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return": round(total_return, 2),
            "benchmark_return": round(benchmark_return, 2),
            "cagr": round(cagr, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": total_trades,
            "profit_factor": round(profit_factor, 2),
            "equity_curve": equity_curve,
            "drawdown_series": drawdown_series,
            "trades": [
                {**t, "entry_date": t["entry_date"].isoformat(), "exit_date": t["exit_date"].isoformat()}
                for t in trades
            ],
            "config_params": config_params,
            "created_at": db_run.created_at.isoformat(),
        }
