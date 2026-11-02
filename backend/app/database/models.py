import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database.engine import Base

class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), unique=True, nullable=False, index=True)  # e.g., "RELIANCE", "TCS"
    ticker = Column(String(32), unique=True, nullable=False, index=True)  # e.g., "RELIANCE.NS"
    company_name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=True)
    aliases = Column(Text, nullable=True)  # JSON or pipe-delimited aliases
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    mappings = relationship("ArticleStockMapping", back_populates="stock", cascade="all, delete-orphan")
    prices = relationship("PriceHistory", back_populates="stock", cascade="all, delete-orphan")
    factors = relationship("SentimentFactor", back_populates="stock", cascade="all, delete-orphan")
    signals = relationship("TradingSignal", back_populates="stock", cascade="all, delete-orphan")
    market_sync = relationship("MarketDataSync", back_populates="stock", uselist=False, cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(1024), unique=True, nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    published_at = Column(DateTime, nullable=False, index=True)
    content_fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    raw_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    stock_mappings = relationship("ArticleStockMapping", back_populates="article", cascade="all, delete-orphan")
    sentiment = relationship("SentimentResult", back_populates="article", uselist=False, cascade="all, delete-orphan")


class ArticleStockMapping(Base):
    __tablename__ = "article_stock_mappings"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    matched_term = Column(String(100), nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    article = relationship("Article", back_populates="stock_mappings")
    stock = relationship("Stock", back_populates="mappings")

    __table_args__ = (
        UniqueConstraint("article_id", "stock_id", name="uq_article_stock"),
    )


class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    sentiment_label = Column(String(20), nullable=False)  # positive, negative, neutral
    positive_probability = Column(Float, nullable=False)
    negative_probability = Column(Float, nullable=False)
    neutral_probability = Column(Float, nullable=False)
    sentiment_score = Column(Float, nullable=False)  # pos - neg
    inference_status = Column(String(20), nullable=False)  # ready, failed, etc.
    error_message = Column(Text, nullable=True)
    inference_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    article = relationship("Article", back_populates="sentiment")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)  # unadjusted regular-session close (chart / OHLC)
    adj_close = Column(Float, nullable=True)  # split/dividend-adjusted close (returns / ML)
    volume = Column(Float, nullable=False)
    
    # Computed technical indicators
    returns_1d = Column(Float, nullable=True)
    momentum_5d = Column(Float, nullable=True)
    momentum_20d = Column(Float, nullable=True)
    momentum_60d = Column(Float, nullable=True)
    ma_20 = Column(Float, nullable=True)
    ma_50 = Column(Float, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    volatility_20d = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)

    stock = relationship("Stock", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_stock_price_date"),
        Index("idx_price_stock_date", "stock_id", "date"),
    )


class MarketDataSync(Base):
    """Per-symbol market-data freshness. Distinct from latest_market_date."""

    __tablename__ = "market_data_syncs"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    ticker = Column(String(32), nullable=False)
    provider = Column(String(50), default="yfinance")
    status = Column(String(20), nullable=False, default="never")  # never, success, failed, empty
    last_attempt_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    latest_market_date = Column(DateTime, nullable=True)
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    close_field = Column(String(40), default="unadjusted_close")
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

    stock = relationship("Stock", back_populates="market_sync")


class SentimentFactor(Base):
    __tablename__ = "sentiment_factors"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    
    daily_mean_sentiment = Column(Float, nullable=True)
    confidence_weighted_sentiment = Column(Float, nullable=True)
    article_count = Column(Integer, default=0)
    bullish_count = Column(Integer, default=0)
    bearish_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    mean_positive_prob = Column(Float, nullable=True)
    mean_negative_prob = Column(Float, nullable=True)
    mean_neutral_prob = Column(Float, nullable=True)
    
    rolling_7d_mean = Column(Float, nullable=True)
    rolling_14d_mean = Column(Float, nullable=True)
    sentiment_momentum = Column(Float, nullable=True)
    sentiment_volatility = Column(Float, nullable=True)
    sentiment_surprise = Column(Float, nullable=True)

    stock = relationship("Stock", back_populates="factors")

    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_stock_factor_date"),
        Index("idx_factor_stock_date", "stock_id", "date"),
    )


class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(64), unique=True, nullable=False, index=True)
    model_type = Column(String(50), nullable=False)  # LogisticRegression, RandomForestClassifier
    target_horizon = Column(Integer, nullable=False)  # 5, 21
    validation_method = Column(String(50), default="walk_forward_purged")
    features_used = Column(Text, nullable=False)  # JSON list
    train_samples = Column(Integer, nullable=False)
    test_samples = Column(Integer, nullable=False)
    
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1 = Column(Float, nullable=True)
    roc_auc = Column(Float, nullable=True)
    feature_importance = Column(Text, nullable=True)  # JSON dict
    hyperparameters = Column(Text, nullable=True)  # JSON dict
    model_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_run_id = Column(Integer, ForeignKey("model_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction_date = Column(DateTime, nullable=False, index=True)
    target_date = Column(DateTime, nullable=False)
    predicted_direction = Column(Integer, nullable=False)  # 1 for up, 0 for down
    probability = Column(Float, nullable=False)
    actual_direction = Column(Integer, nullable=True)


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_date = Column(DateTime, nullable=False, index=True)
    signal_type = Column(String(10), nullable=False)  # BUY, HOLD, SELL
    strategy = Column(String(50), nullable=False)  # rule_based, ml_based
    confidence = Column(Float, default=0.0)
    explanation = Column(Text, nullable=False)
    contributing_factors = Column(Text, nullable=True)  # JSON dict
    risk_warning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    stock = relationship("Stock", back_populates="signals")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, index=True)
    backtest_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    strategy_type = Column(String(50), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_equity = Column(Float, nullable=False)
    
    total_return = Column(Float, nullable=False)
    benchmark_return = Column(Float, nullable=True)
    cagr = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    profit_factor = Column(Float, nullable=True)
    
    equity_curve = Column(Text, nullable=False)  # JSON array
    drawdown_series = Column(Text, nullable=True)  # JSON array
    config_params = Column(Text, nullable=True)  # JSON dict
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    trades = relationship("BacktestTrade", back_populates="backtest_run", cascade="all, delete-orphan")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id = Column(Integer, primary_key=True, index=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False)
    entry_date = Column(DateTime, nullable=False)
    exit_date = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    pnl = Column(Float, nullable=False)
    return_pct = Column(Float, nullable=False)
    exit_reason = Column(String(50), nullable=False)

    backtest_run = relationship("BacktestRun", back_populates="trades")


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, nullable=False, index=True)
    job_type = Column(String(50), nullable=False)  # ingestion, sentiment, training, backtest
    status = Column(String(20), nullable=False)  # queued, running, completed, failed
    progress_pct = Column(Integer, default=0)
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
