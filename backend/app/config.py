import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SentimentAlpha"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    MODEL_CACHE_DIR: Path = DATA_DIR / "models" / "finbert"
    SAVED_MODELS_DIR: Path = DATA_DIR / "models" / "trained"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'sentiment_alpha.db'}"
    )
    
    # FinBERT Inference
    FINBERT_MODEL_NAME: str = "ProsusAI/finbert"
    FINBERT_DEVICE: str = os.getenv("FINBERT_DEVICE", "cpu")
    FINBERT_BATCH_SIZE: int = int(os.getenv("FINBERT_BATCH_SIZE", "16"))
    FINBERT_MAX_LENGTH: int = int(os.getenv("FINBERT_MAX_LENGTH", "256"))
    FINBERT_OFFLINE: bool = os.getenv("FINBERT_OFFLINE", "False").lower() in ("true", "1")
    LIGHTWEIGHT_MODE: bool = os.getenv("LIGHTWEIGHT_MODE", "False").lower() in ("true", "1")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # Ingestion Configuration
    NEWS_REQUEST_TIMEOUT: int = 15
    MAX_ARTICLES_PER_FEED: int = 50
    DEFAULT_PREDICTION_HORIZON: int = 5  # Trading days
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.SAVED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "raw").mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "processed").mkdir(parents=True, exist_ok=True)
