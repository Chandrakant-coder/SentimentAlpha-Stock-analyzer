import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.engine import SessionLocal
from app.database.repositories import JobRepository
from app.services.ingestion import NewsIngestionService
from app.services.sentiment_analyzer import SentimentAnalyzerService
from app.services.factor_builder import SentimentFactorBuilder
from app.services.price_data import MarketDataService
from app.services.ml_models import MLModelService
from app.services.signal_generator import SignalGeneratorService

executor = ThreadPoolExecutor(max_workers=3)

class PipelineService:
    @staticmethod
    def _run_ingestion_job(job_id: str):
        db = SessionLocal()
        job_repo = JobRepository(db)
        try:
            job_repo.update_job(job_id, status="running", progress_pct=10, message="Fetching RSS financial feeds...")
            service = NewsIngestionService(db)
            stats = service.ingest_all_feeds()

            job_repo.update_job(
                job_id,
                status="completed",
                progress_pct=100,
                processed_items=stats["total_inserted"],
                total_items=stats["total_fetched"],
                message=f"Ingestion complete: {stats['total_inserted']} new articles, {stats['total_mapped']} mappings.",
            )
        except Exception as e:
            logger.error(f"Ingestion job {job_id} failed: {e}", exc_info=True)
            job_repo.update_job(job_id, status="failed", error_details=str(e), message="Ingestion failed.")
        finally:
            db.close()

    @staticmethod
    def _run_sentiment_job(job_id: str, limit: int = 100):
        db = SessionLocal()
        job_repo = JobRepository(db)
        try:
            job_repo.update_job(job_id, status="running", progress_pct=10, message="Running local FinBERT inference...")

            def progress_callback(pct, done, total):
                job_repo.update_job(job_id, progress_pct=pct, processed_items=done, total_items=total, message=f"Processed {done}/{total} articles")

            service = SentimentAnalyzerService(db)
            stats = service.analyze_unprocessed_articles(limit=limit, progress_callback=progress_callback)

            # Also update factors
            job_repo.update_job(job_id, progress_pct=90, message="Aggregating daily sentiment factors...")
            factor_builder = SentimentFactorBuilder(db)
            factor_builder.build_factors_for_all_stocks()

            job_repo.update_job(
                job_id,
                status="completed",
                progress_pct=100,
                processed_items=stats["successful"],
                total_items=stats["total_analyzed"],
                message=f"Sentiment complete: {stats['successful']} successful, {stats['failed']} failed.",
            )
        except Exception as e:
            logger.error(f"Sentiment analysis job {job_id} failed: {e}", exc_info=True)
            job_repo.update_job(job_id, status="failed", error_details=str(e), message="Sentiment analysis failed.")
        finally:
            db.close()

    @staticmethod
    def _run_training_job(job_id: str, train_params: Dict[str, Any]):
        db = SessionLocal()
        job_repo = JobRepository(db)
        try:
            job_repo.update_job(job_id, status="running", progress_pct=20, message="Preparing dataset and features...")
            ml_service = MLModelService(db)
            res = ml_service.train_model(
                model_type=train_params.get("model_type", "XGBoostClassifier"),
                target_horizon=train_params.get("target_horizon", 5),
                feature_subset=train_params.get("features"),
                test_size=train_params.get("test_size", 0.2),
                purge_overlap=train_params.get("purge_overlap", True),
            )
            job_repo.update_job(
                job_id,
                status="completed",
                progress_pct=100,
                processed_items=res["test_samples"],
                total_items=res["train_samples"] + res["test_samples"],
                message=f"Trained {res['model_type']}: Accuracy {res['accuracy']:.3f}, F1 {res['f1']:.3f}",
            )
        except Exception as e:
            logger.error(f"Training job {job_id} failed: {e}", exc_info=True)
            job_repo.update_job(job_id, status="failed", error_details=str(e), message="Model training failed.")
        finally:
            db.close()

    def start_ingestion_job(self, db: Session) -> str:
        job_id = f"job_ingest_{uuid.uuid4().hex[:8]}"
        job_repo = JobRepository(db)
        job_repo.create_job(job_id, job_type="ingestion")
        executor.submit(self._run_ingestion_job, job_id)
        return job_id

    def start_sentiment_job(self, db: Session, limit: int = 100) -> str:
        job_id = f"job_sentiment_{uuid.uuid4().hex[:8]}"
        job_repo = JobRepository(db)
        job_repo.create_job(job_id, job_type="sentiment")
        executor.submit(self._run_sentiment_job, job_id, limit)
        return job_id

    @staticmethod
    def _run_market_data_job(job_id: str, symbol: Optional[str], period: str):
        db = SessionLocal()
        job_repo = JobRepository(db)
        try:
            job_repo.update_job(job_id, status="running", progress_pct=10, message="Downloading Yahoo Finance daily bars...")
            service = MarketDataService(db)
            if symbol:
                result = service.sync_symbol(symbol, period=period)
                ok = result["status"] == "success"
                job_repo.update_job(
                    job_id,
                    status="completed" if ok else "failed",
                    progress_pct=100,
                    processed_items=result.get("records_fetched", 0),
                    total_items=result.get("records_fetched", 0),
                    message=(
                        f"{symbol}: latest session {result.get('latest_market_date')} "
                        f"status={result['status']}"
                    ),
                    error_details=result.get("error"),
                )
            else:
                bundle = service.sync_all_stocks(period=period)
                failed = bundle["failed"]
                job_repo.update_job(
                    job_id,
                    status="completed" if failed == 0 else "failed",
                    progress_pct=100,
                    processed_items=bundle["successful"],
                    total_items=bundle["symbols"],
                    message=f"Synced {bundle['successful']}/{bundle['symbols']} symbols.",
                    error_details=None if failed == 0 else f"{failed} symbol(s) failed",
                )
        except Exception as e:
            logger.error(f"Market data job {job_id} failed: {e}", exc_info=True)
            job_repo.update_job(job_id, status="failed", error_details=str(e), message="Market data sync failed.")
        finally:
            db.close()

    def start_training_job(self, db: Session, train_params: Dict[str, Any]) -> str:
        job_id = f"job_train_{uuid.uuid4().hex[:8]}"
        job_repo = JobRepository(db)
        job_repo.create_job(job_id, job_type="training")
        executor.submit(self._run_training_job, job_id, train_params)
        return job_id

    def start_market_data_job(self, db: Session, symbol: Optional[str] = None, period: str = "1y") -> str:
        job_id = f"job_market_{uuid.uuid4().hex[:8]}"
        job_repo = JobRepository(db)
        job_repo.create_job(job_id, job_type="market_data")
        executor.submit(self._run_market_data_job, job_id, symbol, period)
        return job_id

pipeline_service = PipelineService()
