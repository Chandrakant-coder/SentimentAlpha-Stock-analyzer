from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.engine import get_db
from app.database.repositories import StockRepository, FactorRepository
from app.database.schemas import SentimentFactorResponse

router = APIRouter(prefix="/factors", tags=["Sentiment Factors"])

@router.get("/{symbol}", response_model=List[SentimentFactorResponse])
def get_factors(
    symbol: str,
    limit: int = Query(180, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stock_repo = StockRepository(db)
    stock = stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    factor_repo = FactorRepository(db)
    factors = factor_repo.get_by_stock(stock.id, limit=limit)
    return factors
