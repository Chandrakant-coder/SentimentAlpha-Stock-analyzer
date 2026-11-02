import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database.engine import get_db
from app.database.models import ModelRun
from app.database.schemas import ModelTrainRequest, ModelRunResponse
from app.services.pipeline_service import pipeline_service

router = APIRouter(prefix="/models", tags=["Machine Learning Models"])

@router.post("/train")
def train_model(req: ModelTrainRequest, db: Session = Depends(get_db)):
    """Triggers model training job in the background"""
    job_id = pipeline_service.start_training_job(
        db,
        {
            "model_type": req.model_type,
            "target_horizon": req.target_horizon,
            "features": req.features,
            "test_size": req.test_size,
            "purge_overlap": req.purge_overlap,
        },
    )
    return {
        "job_id": job_id,
        "message": f"Training job initiated for {req.model_type} (horizon={req.target_horizon}d)",
        "status": "queued",
    }

@router.get("", response_model=List[ModelRunResponse])
def list_models(db: Session = Depends(get_db)):
    runs = db.query(ModelRun).order_by(desc(ModelRun.created_at)).all()
    out = []
    for r in runs:
        fi = json.loads(r.feature_importance) if r.feature_importance else None
        out.append(
            ModelRunResponse(
                id=r.id,
                model_id=r.model_id,
                model_type=r.model_type,
                target_horizon=r.target_horizon,
                validation_method=r.validation_method,
                train_samples=r.train_samples,
                test_samples=r.test_samples,
                accuracy=r.accuracy,
                precision=r.precision,
                recall=r.recall,
                f1=r.f1,
                roc_auc=r.roc_auc,
                feature_importance=fi,
                created_at=r.created_at,
            )
        )
    return out

@router.get("/{model_id}/metrics")
def get_model_metrics(model_id: str, db: Session = Depends(get_db)):
    run = db.query(ModelRun).filter(ModelRun.model_id == model_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Model run {model_id} not found")

    return {
        "model_id": run.model_id,
        "model_type": run.model_type,
        "target_horizon": run.target_horizon,
        "metrics": {
            "accuracy": run.accuracy,
            "precision": run.precision,
            "recall": run.recall,
            "f1": run.f1,
            "roc_auc": run.roc_auc,
        },
        "feature_importance": json.loads(run.feature_importance) if run.feature_importance else {},
        "hyperparameters": json.loads(run.hyperparameters) if run.hyperparameters else {},
        "features_used": json.loads(run.features_used) if run.features_used else [],
        "train_samples": run.train_samples,
        "test_samples": run.test_samples,
        "created_at": run.created_at.isoformat(),
    }
