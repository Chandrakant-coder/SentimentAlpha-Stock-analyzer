import os
import threading
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Any
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from app.config import settings
from app.core.logging import logger
from app.core.exceptions import ModelInferenceError

class ModelStatus(str, Enum):
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"

class FinBERTLoader:
    """
    Thread-safe lazy loader and manager for the local ProsusAI/finbert model.
    Guarantees single load, cached offline operation, and explicit lifecycle status.
    """
    _instance: Optional["FinBERTLoader"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.model_name = settings.FINBERT_MODEL_NAME
        self.cache_dir = settings.MODEL_CACHE_DIR
        self.status = ModelStatus.NOT_DOWNLOADED
        self.error_message: Optional[str] = None
        self.device = torch.device("cpu")
        self.tokenizer: Optional[Any] = None
        self.model: Optional[Any] = None
        self.labels = ["positive", "negative", "neutral"]  # FinBERT label order
        self.version = "1.0.0"
        self._load_lock = threading.Lock()
        self._check_initial_status()

    def _check_initial_status(self):
        """Inspects local cache directory to check if model files are already present"""
        if settings.LIGHTWEIGHT_MODE:
            self.status = ModelStatus.READY
            logger.info("FinBERT running in LIGHTWEIGHT_MODE (deterministic mock for tests/dev)")
            return

        # Check for standard huggingface model cache or local snapshot
        has_config = list(self.cache_dir.glob("**/config.json")) or (self.cache_dir / "config.json").exists()
        has_snapshots = list(self.cache_dir.glob("**/snapshots/*"))
        has_blobs = list(self.cache_dir.glob("**/blobs/*"))

        if has_config and (has_snapshots or has_blobs):
            # Model is downloaded on disk, ready to be loaded into memory
            self.status = ModelStatus.READY if self.model is not None else ModelStatus.NOT_DOWNLOADED
            # Note: When model is loaded into memory, status becomes READY
        else:
            self.status = ModelStatus.NOT_DOWNLOADED

    def get_status(self) -> dict:
        return {
            "status": self.status.value,
            "model_name": self.model_name,
            "version": self.version,
            "device": str(self.device),
            "cache_dir": str(self.cache_dir),
            "offline_mode": settings.FINBERT_OFFLINE,
            "lightweight_mode": settings.LIGHTWEIGHT_MODE,
            "error_message": self.error_message,
        }

    def load_model(self, force_reload: bool = False) -> Tuple[Any, Any]:
        """
        Loads tokenizer and model into memory with thread safety.
        Returns (tokenizer, model).
        """
        if settings.LIGHTWEIGHT_MODE:
            self.status = ModelStatus.READY
            return None, None

        if self.status == ModelStatus.READY and self.model is not None and not force_reload:
            return self.tokenizer, self.model

        with self._load_lock:
            # Recheck after acquiring lock
            if self.status == ModelStatus.READY and self.model is not None and not force_reload:
                return self.tokenizer, self.model

            try:
                # Determine device
                if settings.FINBERT_DEVICE == "cuda" and torch.cuda.is_available():
                    self.device = torch.device("cuda")
                else:
                    self.device = torch.device("cpu")

                # If offline mode is requested
                local_files_only = settings.FINBERT_OFFLINE

                logger.info(f"Loading FinBERT model '{self.model_name}' on device '{self.device}' (offline={local_files_only})...")
                self.status = ModelStatus.DOWNLOADING if not local_files_only else ModelStatus.LOADING

                # Load Tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    cache_dir=str(self.cache_dir),
                    local_files_only=local_files_only,
                )

                self.status = ModelStatus.LOADING

                # Load Model
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    self.model_name,
                    cache_dir=str(self.cache_dir),
                    local_files_only=local_files_only,
                )

                self.model.to(self.device)
                self.model.eval()

                # Infer FinBERT label mapping if configured in id2label
                if hasattr(self.model.config, "id2label") and self.model.config.id2label:
                    self.labels = [self.model.config.id2label[i].lower() for i in range(len(self.model.config.id2label))]

                self.status = ModelStatus.READY
                self.error_message = None
                logger.info(f"FinBERT loaded successfully. Labels: {self.labels}")
                return self.tokenizer, self.model

            except Exception as e:
                self.status = ModelStatus.FAILED
                self.error_message = str(e)
                logger.error(f"Failed to load FinBERT model: {e}", exc_info=True)
                raise ModelInferenceError(f"Could not load FinBERT: {e}", details={"cache_dir": str(self.cache_dir)})

finbert_loader = FinBERTLoader()
