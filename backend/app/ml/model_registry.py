import json
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import joblib
from app.config import settings
from app.core.logging import logger

class ModelRegistry:
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or settings.SAVED_MODELS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model_id: str,
        model_pipeline: Any,
        metadata: Dict[str, Any],
    ) -> Path:
        """Saves model pipeline and accompanying metadata to disk"""
        model_path = self.storage_dir / f"{model_id}.joblib"
        meta_path = self.storage_dir / f"{model_id}.json"

        joblib.dump(model_pipeline, model_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info(f"Model {model_id} saved successfully to {model_path}")
        return model_path

    def load_model(self, model_id: str) -> Tuple[Any, Dict[str, Any]]:
        """Loads model pipeline and metadata from disk"""
        model_path = self.storage_dir / f"{model_id}.joblib"
        meta_path = self.storage_dir / f"{model_id}.json"

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        model_pipeline = joblib.load(model_path)
        metadata = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        return model_pipeline, metadata

model_registry = ModelRegistry()
