import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.database.engine import get_db
from app.database.models import Stock, Article, SentimentResult, PipelineJob
from app.database.schemas import SystemStatusResponse
from app.ml.finbert_loader import finbert_loader

router = APIRouter(tags=["Health & System"])

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

@router.get("/system/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    total_stocks = db.query(Stock).count() if db_connected else 0
    total_articles = db.query(Article).count() if db_connected else 0
    total_sentiment = (
        db.query(SentimentResult).filter(SentimentResult.inference_status == "ready").count()
        if db_connected
        else 0
    )

    last_article = db.query(Article).order_by(Article.created_at.desc()).first() if db_connected else None
    last_ingest = last_article.created_at if last_article else None

    active_jobs = (
        db.query(PipelineJob).filter(PipelineJob.status.in_(["queued", "running"])).count()
        if db_connected
        else 0
    )

    fb_status = finbert_loader.get_status()

    return SystemStatusResponse(
        status="operational" if db_connected else "degraded",
        environment=settings.ENVIRONMENT,
        database_connected=db_connected,
        total_stocks=total_stocks,
        total_articles=total_articles,
        total_sentiment_analyzed=total_sentiment,
        finbert_status=fb_status["status"],
        finbert_device=fb_status["device"],
        finbert_model_cache=fb_status["cache_dir"],
        last_ingestion_time=last_ingest,
        active_jobs=active_jobs,
    )
