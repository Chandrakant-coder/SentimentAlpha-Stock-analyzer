export interface Stock {
  id: number;
  symbol: string;
  ticker: string;
  company_name: string;
  sector?: string;
  aliases?: string;
  is_active: boolean;
  created_at: string;
}

export interface SentimentProbability {
  positive: number;
  negative: number;
  neutral: number;
}

export interface SentimentResult {
  sentiment_label: 'positive' | 'negative' | 'neutral' | 'failed' | 'pending';
  positive_probability: number;
  negative_probability: number;
  neutral_probability: number;
  sentiment_score: number;
  model_name: string;
  model_version: string;
  inference_status: string;
  inference_timestamp?: string;
  error_message?: string;
}

export interface Article {
  id: number;
  title: string;
  description?: string;
  url: string;
  source: string;
  published_at: string;
  content_fingerprint: string;
  created_at: string;
  sentiment?: SentimentResult;
  mapped_stocks?: string[];
}

export interface ArticleListResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  items: Article[];
}

export interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  adj_close?: number;
  volume: number;
  returns_1d?: number;
  momentum_5d?: number;
  momentum_20d?: number;
  momentum_60d?: number;
  ma_20?: number;
  ma_50?: number;
  rsi_14?: number;
  macd?: number;
  macd_signal?: number;
  volatility_20d?: number;
  volume_ratio?: number;
}

export interface SentimentFactor {
  date: string;
  daily_mean_sentiment?: number;
  confidence_weighted_sentiment?: number;
  article_count: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  mean_positive_prob?: number;
  mean_negative_prob?: number;
  mean_neutral_prob?: number;
  rolling_7d_mean?: number;
  rolling_14d_mean?: number;
  sentiment_momentum?: number;
  sentiment_volatility?: number;
  sentiment_surprise?: number;
}

export interface ModelRun {
  id: number;
  model_id: string;
  model_type: string;
  target_horizon: number;
  validation_method: string;
  train_samples: number;
  test_samples: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  roc_auc?: number;
  feature_importance?: Record<string, number>;
  created_at: string;
}

export interface TradingSignal {
  id: number;
  symbol: string;
  company_name: string;
  signal_date: string;
  signal_type: 'BUY' | 'HOLD' | 'SELL';
  strategy: string;
  confidence: number;
  explanation: string;
  contributing_factors?: Record<string, any>;
  risk_warning?: string;
  created_at: string;
}

export interface BacktestTrade {
  symbol: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  shares: number;
  pnl: number;
  return_pct: number;
  exit_reason: string;
}

export interface BacktestRun {
  id: number;
  backtest_id: string;
  name: string;
  strategy_type: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_equity: number;
  total_return: number;
  benchmark_return?: number;
  cagr?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  win_rate?: number;
  total_trades: number;
  profit_factor?: number;
  equity_curve: {
    date: string;
    strategy_equity: number;
    benchmark_equity: number;
    cash: number;
    invested: number;
  }[];
  drawdown_series?: {
    date: string;
    drawdown: number;
  }[];
  config_params?: Record<string, any>;
  trades?: BacktestTrade[];
  created_at: string;
}

export interface PipelineJob {
  job_id: string;
  job_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress_pct: number;
  total_items: number;
  processed_items: number;
  message?: string;
  error_details?: string;
  started_at: string;
  completed_at?: string;
}

export interface SystemStatus {
  status: string;
  environment: string;
  database_connected: boolean;
  total_stocks: number;
  total_articles: number;
  total_sentiment_analyzed: number;
  finbert_status: 'not_downloaded' | 'downloading' | 'loading' | 'ready' | 'failed';
  finbert_device: string;
  finbert_model_cache: string;
  last_ingestion_time?: string;
  active_jobs: number;
}

export interface MarketDataStatus {
  symbol: string;
  ticker: string;
  currency: string;
  provider: string;
  close_field: string;
  adj_close_field: string;
  status: string;
  last_attempt_at?: string | null;
  last_success_at?: string | null;
  latest_market_date?: string | null;
  expected_session_date?: string | null;
  missing_expected_session: boolean;
  stale: boolean;
  records_fetched: number;
  records_inserted: number;
  records_updated: number;
  records_skipped: number;
  error?: string | null;
}
