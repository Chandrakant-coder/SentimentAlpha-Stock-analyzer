import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.engine import get_db
from app.database.models import BacktestRun, BacktestTrade
from app.database.schemas import BacktestRequest, BacktestRunResponse, BacktestTradeResponse
from app.services.backtester import PortfolioBacktester

router = APIRouter(prefix="/backtests", tags=["Portfolio Backtesting"])

@router.post("", response_model=BacktestRunResponse)
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    backtester = PortfolioBacktester(db)
    try:
        res = backtester.run_backtest(
            symbol=req.symbol,
            strategy_type=req.strategy_type,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            entry_sentiment_threshold=req.entry_sentiment_threshold,
            exit_sentiment_threshold=req.exit_sentiment_threshold,
            transaction_cost_pct=req.transaction_cost_pct,
            slippage_pct=req.slippage_pct,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=List[BacktestRunResponse])
def list_backtests(limit: int = 10, db: Session = Depends(get_db)):
    runs = db.query(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(limit).all()
    results = []
    for r in runs:
        eq = json.loads(r.equity_curve) if r.equity_curve else []
        dd = json.loads(r.drawdown_series) if r.drawdown_series else []
        cfg = json.loads(r.config_params) if r.config_params else {}
        results.append(
            BacktestRunResponse(
                id=r.id,
                backtest_id=r.backtest_id,
                name=r.name,
                strategy_type=r.strategy_type,
                start_date=r.start_date,
                end_date=r.end_date,
                initial_capital=r.initial_capital,
                final_equity=r.final_equity,
                total_return=r.total_return,
                benchmark_return=r.benchmark_return,
                cagr=r.cagr,
                sharpe_ratio=r.sharpe_ratio,
                max_drawdown=r.max_drawdown,
                win_rate=r.win_rate,
                total_trades=r.total_trades,
                profit_factor=r.profit_factor,
                equity_curve=eq,
                drawdown_series=dd,
                config_params=cfg,
                created_at=r.created_at,
            )
        )
    return results

@router.get("/{backtest_id}", response_model=BacktestRunResponse)
def get_backtest(backtest_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestRun).filter(BacktestRun.backtest_id == backtest_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest not found")

    eq = json.loads(r.equity_curve) if r.equity_curve else []
    dd = json.loads(r.drawdown_series) if r.drawdown_series else []
    cfg = json.loads(r.config_params) if r.config_params else {}

    return BacktestRunResponse(
        id=r.id,
        backtest_id=r.backtest_id,
        name=r.name,
        strategy_type=r.strategy_type,
        start_date=r.start_date,
        end_date=r.end_date,
        initial_capital=r.initial_capital,
        final_equity=r.final_equity,
        total_return=r.total_return,
        benchmark_return=r.benchmark_return,
        cagr=r.cagr,
        sharpe_ratio=r.sharpe_ratio,
        max_drawdown=r.max_drawdown,
        win_rate=r.win_rate,
        total_trades=r.total_trades,
        profit_factor=r.profit_factor,
        equity_curve=eq,
        drawdown_series=dd,
        config_params=cfg,
        created_at=r.created_at,
    )

@router.get("/{backtest_id}/trades", response_model=List[BacktestTradeResponse])
def get_backtest_trades(backtest_id: str, db: Session = Depends(get_db)):
    r = db.query(BacktestRun).filter(BacktestRun.backtest_id == backtest_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backtest not found")

    trades = (
        db.query(BacktestTrade)
        .filter(BacktestTrade.backtest_run_id == r.id)
        .order_by(BacktestTrade.entry_date.asc())
        .all()
    )
    return trades
