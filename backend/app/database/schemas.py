import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# Base & Pagination
class BaseSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

class PaginatedResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    pages: int

# Stock Schemas
class StockBase(BaseSchema):
    symbol: str
    ticker: str
    company_name: str
    sector: Optional[str] = None
    aliases: Optional[str] = None
    is_active: bool = True

class StockResponse(StockBase):
    id: int
    created_at: datetime.datetime

# Sentiment Schemas
class SentimentProbability(BaseSchema):
    positive: float
    negative: float
    neutral: float

class SentimentResultResponse(BaseSchema):
    sentiment_label: str
    positive_probability: float
    negative_probability: float
    neutral_probability: float
    sentiment_score: float
    model_name: str
    model_version: str
    inference_status: str
    inference_timestamp: Optional[datetime.datetime] = None
    error_message: Optional[str] = None

# Article Schemas
class ArticleBase(BaseSchema):
    title: str
    description: Optional[str] = None
    url: str
    source: str
    published_at: datetime.datetime

class ArticleResponse(ArticleBase):
    id: int
    content_fingerprint: str
    created_at: datetime.datetime
    sentiment: Optional[SentimentResultResponse] = None
    mapped_stocks: Optional[List[str]] = None

class ArticleListResponse(PaginatedResponse):
    items: List[ArticleResponse]

# Price & Technicals
class PriceHistoryResponse(BaseSchema):
    date: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: Optional[float] = None
    volume: float
    returns_1d: Optional[float] = None
    momentum_5d: Optional[float] = None
    momentum_20d: Optional[float] = None
    momentum_60d: Optional[float] = None
    ma_20: Optional[float] = None
    ma_50: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    volatility_20d: Optional[float] = None
    volume_ratio: Optional[float] = None

# Sentiment Factors
class SentimentFactorResponse(BaseSchema):
    date: datetime.datetime
    daily_mean_sentiment: Optional[float] = None
    confidence_weighted_sentiment: Optional[float] = None
    article_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    mean_positive_prob: Optional[float] = None
    mean_negative_prob: Optional[float] = None
    mean_neutral_prob: Optional[float] = None
    rolling_7d_mean: Optional[float] = None
    rolling_14d_mean: Optional[float] = None
    sentiment_momentum: Optional[float] = None
    sentiment_volatility: Optional[float] = None
    sentiment_surprise: Optional[float] = None

# Machine Learning Models
class ModelTrainRequest(BaseSchema):
    model_type: str = Field(default="XGBoostClassifier", description="XGBoostClassifier (primary prediction model)")
    target_horizon: int = Field(default=5, description="Prediction horizon in trading days (e.g. 5 or 21)")
    features: Optional[List[str]] = Field(default=None, description="Subset of features to train on")
    test_size: float = Field(default=0.2, description="Held-out validation proportion")
    purge_overlap: bool = Field(default=True, description="Purge overlapping horizon samples")

class ModelRunResponse(BaseSchema):
    id: int
    model_id: str
    model_type: str
    target_horizon: int
    validation_method: str
    train_samples: int
    test_samples: int
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    roc_auc: Optional[float] = None
    feature_importance: Optional[Dict[str, float]] = None
    created_at: datetime.datetime

# Trading Signals
class TradingSignalResponse(BaseSchema):
    id: int
    symbol: str
    company_name: str
    signal_date: datetime.datetime
    signal_type: str  # BUY, HOLD, SELL
    strategy: str
    confidence: float
    explanation: str
    contributing_factors: Optional[Dict[str, Any]] = None
    risk_warning: Optional[str] = None
    created_at: datetime.datetime

# Backtesting
class BacktestRequest(BaseSchema):
    symbol: str = Field(default="RELIANCE", description="Stock symbol to backtest")
    strategy_type: str = Field(default="sentiment_momentum", description="sentiment_momentum, rule_based, or ml_signal")
    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    initial_capital: float = Field(default=100000.0, description="Starting cash")
    entry_sentiment_threshold: float = Field(default=0.15, description="Sentiment score required to enter long")
    exit_sentiment_threshold: float = Field(default=-0.05, description="Sentiment score required to exit long")
    transaction_cost_pct: float = Field(default=0.001, description="Brokerage / fees per trade (e.g. 0.001 = 10 bps)")
    slippage_pct: float = Field(default=0.0005, description="Price slippage per trade (0.0005 = 5 bps)")

class BacktestTradeResponse(BaseSchema):
    symbol: str
    entry_date: datetime.datetime
    exit_date: datetime.datetime
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    return_pct: float
    exit_reason: str

class BacktestRunResponse(BaseSchema):
    id: int
    backtest_id: str
    name: str
    strategy_type: str
    start_date: datetime.datetime
    end_date: datetime.datetime
    initial_capital: float
    final_equity: float
    total_return: float
    benchmark_return: Optional[float] = None
    cagr: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: int
    profit_factor: Optional[float] = None
    equity_curve: List[Dict[str, Any]]
    drawdown_series: Optional[List[Dict[str, Any]]] = None
    config_params: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime

# Pipeline Jobs
class PipelineJobResponse(BaseSchema):
    job_id: str
    job_type: str
    status: str  # queued, running, completed, failed
    progress_pct: int
    total_items: int
    processed_items: int
    message: Optional[str] = None
    error_details: Optional[str] = None
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

# System Health & Status
class SystemStatusResponse(BaseSchema):
    status: str
    environment: str
    database_connected: bool
    total_stocks: int
    total_articles: int
    total_sentiment_analyzed: int
    finbert_status: str  # not_downloaded, downloading, loading, ready, failed
    finbert_device: str
    finbert_model_cache: str
    last_ingestion_time: Optional[datetime.datetime] = None
    active_jobs: int


class MarketDataSyncResponse(BaseSchema):
    symbol: str
    ticker: str
    currency: str = "INR"
    provider: str = "yfinance"
    close_field: str = "unadjusted_close"
    adj_close_field: str = "adj_close"
    status: str
    last_attempt_at: Optional[datetime.datetime] = None
    last_success_at: Optional[datetime.datetime] = None
    latest_market_date: Optional[datetime.datetime] = None
    expected_session_date: Optional[str] = None
    missing_expected_session: bool = False
    stale: bool = False
    records_fetched: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    error: Optional[str] = None
