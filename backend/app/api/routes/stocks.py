from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.engine import get_db
from app.database.models import PriceHistory
from app.database.repositories import StockRepository, PriceRepository, FactorRepository
from app.database.schemas import (
    StockResponse,
    PriceHistoryResponse,
    SentimentFactorResponse,
    MarketDataSyncResponse,
)
from app.services.price_data import MarketDataService

router = APIRouter(prefix="/stocks", tags=["Stocks & Market Data"])

@router.get("", response_model=List[StockResponse])
def list_stocks(active_only: bool = True, db: Session = Depends(get_db)):
    repo = StockRepository(db)
    return repo.get_all(active_only=active_only)

@router.get("/latest-prices", response_model=List[Dict[str, Any]])
def get_all_latest_prices(db: Session = Depends(get_db)):
    """Return the single most-recent price bar for every active stock.

    Used by the Market Overview page to show the latest close and session
    date for all tracked symbols in one request without fetching full history.
    """
    repo = StockRepository(db)
    stocks = repo.get_all(active_only=True)
    result = []
    for stock in stocks:
        row = (
            db.query(PriceHistory)
            .filter(PriceHistory.stock_id == stock.id)
            .order_by(desc(PriceHistory.date))
            .first()
        )
        entry: Dict[str, Any] = {
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "sector": stock.sector,
            "ticker": stock.ticker,
        }
        if row:
            entry.update({
                "date": row.date.isoformat(),
                "close": round(float(row.close), 2),
                "open": round(float(row.open), 2),
                "high": round(float(row.high), 2),
                "low": round(float(row.low), 2),
                "volume": float(row.volume),
                "adj_close": round(float(row.adj_close), 2) if row.adj_close else None,
                "change_pct": None,   # populated below
                "rsi_14": round(float(row.rsi_14), 2) if row.rsi_14 else None,
                "ma_20": round(float(row.ma_20), 2) if row.ma_20 else None,
            })
            # Compute 1-day change % from prev bar
            prev = (
                db.query(PriceHistory)
                .filter(PriceHistory.stock_id == stock.id, PriceHistory.date < row.date)
                .order_by(desc(PriceHistory.date))
                .first()
            )
            if prev and prev.close and prev.close > 0:
                entry["change_pct"] = round(
                    ((row.close - prev.close) / prev.close) * 100, 2
                )
        else:
            entry.update({"date": None, "close": None, "change_pct": None})
        result.append(entry)
    return result

@router.get("/{symbol}", response_model=StockResponse)
def get_stock(symbol: str, db: Session = Depends(get_db)):
    repo = StockRepository(db)
    stock = repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    return stock

@router.get("/{symbol}/prices", response_model=List[PriceHistoryResponse])
def get_stock_prices(
    symbol: str,
    limit: int = Query(180, ge=1, le=1000),
    sync_if_empty: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Return stored unadjusted daily OHLC bars.

    Auto-syncs from Yahoo Finance when:
    - No bars are stored yet (first access), OR
    - The latest stored bar is behind the expected NSE session (stale data).

    A 200 response means the query succeeded.  Check /prices/status for
    whether the bars are the latest NSE session or whether a provider error
    occurred.
    """
    repo = StockRepository(db)
    stock = repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")

    price_repo = PriceRepository(db)
    service = MarketDataService(db)
    prices = price_repo.get_by_stock(stock.id, limit=limit)

    if sync_if_empty and (not prices or service._is_stale(stock.id)):
        service.sync_symbol(stock.symbol)
        prices = price_repo.get_by_stock(stock.id, limit=limit)

    return prices

@router.get("/{symbol}/prices/status", response_model=MarketDataSyncResponse)
def get_stock_price_status(symbol: str, db: Session = Depends(get_db)):
    repo = StockRepository(db)
    stock = repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    service = MarketDataService(db)
    return service.get_symbol_status(stock.symbol)

@router.post("/{symbol}/sync", response_model=MarketDataSyncResponse)
def sync_stock_prices(
    symbol: str,
    period: str = Query("1y"),
    db: Session = Depends(get_db),
):
    repo = StockRepository(db)
    stock = repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    service = MarketDataService(db)
    result = service.sync_symbol(stock.symbol, period=period)
    result.pop("records", None)
    return result

@router.get("/{symbol}/factors", response_model=List[SentimentFactorResponse])
def get_stock_sentiment_factors(
    symbol: str,
    limit: int = Query(180, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    repo = StockRepository(db)
    stock = repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")

    factor_repo = FactorRepository(db)
    factors = factor_repo.get_by_stock(stock.id, limit=limit)
    return factors
