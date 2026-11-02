class SentimentAlphaException(Exception):
    """Base exception for SentimentAlpha"""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ModelInferenceError(SentimentAlphaException):
    """Raised when FinBERT inference fails"""
    pass

class ModelNotFoundError(SentimentAlphaException):
    """Raised when required model artifact is missing"""
    pass

class DataIngestionError(SentimentAlphaException):
    """Raised when news ingestion fails"""
    pass

class StockNotFoundError(SentimentAlphaException):
    """Raised when requested stock symbol is not found"""
    pass

class BacktestError(SentimentAlphaException):
    """Raised when backtesting encounters an invalid state"""
    pass

class PipelineError(SentimentAlphaException):
    """Raised when pipeline job execution fails"""
    pass
