import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.engine import get_db
from app.database.models import TradingSignal, Stock
from app.database.schemas import TradingSignalResponse
from app.services.signal_generator import SignalGeneratorService

router = APIRouter(prefix="/signals", tags=["Trading Signals"])

@router.get("", response_model=List[TradingSignalResponse])
def get_signals(
    symbol: Optional[str] = Query(None),
    strategy: str = Query("rule_based"),
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
):
    service = SignalGeneratorService(db)

    if refresh:
        if symbol:
            service.generate_signal_for_stock(symbol, strategy=strategy)
        else:
            service.generate_all_signals(strategy=strategy)

    q = db.query(TradingSignal, Stock).join(Stock, TradingSignal.stock_id == Stock.id)
    if symbol:
        q = q.filter(Stock.symbol == symbol.upper().replace(".NS", ""))
    if strategy:
        q = q.filter(TradingSignal.strategy == strategy)

    records = q.order_by(desc(TradingSignal.created_at)).all()

    # Deduplicate: show only latest signal per stock
    seen_stocks = set()
    latest_signals = []
    for sig, stock in records:
        if stock.symbol not in seen_stocks:
            seen_stocks.add(stock.symbol)
            factors = json.loads(sig.contributing_factors) if sig.contributing_factors else None
            latest_signals.append(
                TradingSignalResponse(
                    id=sig.id,
                    symbol=stock.symbol,
                    company_name=stock.company_name,
                    signal_date=sig.signal_date,
                    signal_type=sig.signal_type,
                    strategy=sig.strategy,
                    confidence=sig.confidence,
                    explanation=sig.explanation,
                    contributing_factors=factors,
                    risk_warning=sig.risk_warning,
                    created_at=sig.created_at,
                )
            )

    # If no signals found in DB yet, generate on the fly
    if not latest_signals:
        if symbol:
            service.generate_signal_for_stock(symbol, strategy=strategy)
        else:
            service.generate_all_signals(strategy=strategy)
        return get_signals(symbol=symbol, strategy=strategy, refresh=False, db=db)

    return latest_signals
