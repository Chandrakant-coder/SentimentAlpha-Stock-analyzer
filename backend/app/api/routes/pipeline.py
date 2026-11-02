from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.engine import get_db
from app.database.repositories import JobRepository, StockRepository
from app.database.schemas import PipelineJobResponse, MarketDataSyncResponse
from app.services.pipeline_service import pipeline_service
from app.services.price_data import MarketDataService

router = APIRouter(prefix="/pipeline", tags=["Pipeline & Background Jobs"])

@router.post("/ingest")
def trigger_news_ingestion(db: Session = Depends(get_db)):
    """Triggers background financial news RSS ingestion and stock mapping"""
    job_id = pipeline_service.start_ingestion_job(db)
    return {
        "job_id": job_id,
        "message": "Financial news ingestion job queued.",
        "status": "queued",
    }

@router.post("/analyze-sentiment")
def trigger_sentiment_analysis(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Triggers background local FinBERT inference for pending articles"""
    job_id = pipeline_service.start_sentiment_job(db, limit=limit)
    return {
        "job_id": job_id,
        "message": f"FinBERT sentiment analysis job queued for up to {limit} articles.",
        "status": "queued",
    }

@router.post("/sync-market-data")
def trigger_market_data_sync(
    symbol: Optional[str] = Query(None, description="If omitted, sync all active stocks"),
    period: str = Query("1y"),
    db: Session = Depends(get_db),
):
    """Queue a Yahoo Finance daily-bar refresh. Historical rows are kept if the provider fails."""
    job_id = pipeline_service.start_market_data_job(db, symbol=symbol, period=period)
    return {
        "job_id": job_id,
        "message": "Market data sync queued. HTTP 200 does not mean bars are current.",
        "status": "queued",
    }

@router.get("/market-data-status", response_model=List[MarketDataSyncResponse])
def list_market_data_status(
    symbol: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    service = MarketDataService(db)
    if symbol:
        return [service.get_symbol_status(symbol)]
    stocks = StockRepository(db).get_all(active_only=True)
    return [service.get_symbol_status(s.symbol) for s in stocks]

@router.get("/jobs/{job_id}", response_model=PipelineJobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job_repo = JobRepository(db)
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job

@router.get("/jobs", response_model=List[PipelineJobResponse])
def list_jobs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    job_repo = JobRepository(db)
    return job_repo.get_recent_jobs(limit=limit)
