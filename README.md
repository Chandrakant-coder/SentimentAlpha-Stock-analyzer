# SentimentAlpha — Local AI Financial Intelligence & Quantitative Web Platform

SentimentAlpha is an institutional-grade, full-stack quantitative financial intelligence web platform. It ingests live financial news via RSS, performs sentiment analysis using a **locally running ProsusAI/finbert model** (no external/paid LLM APIs), maps news to Nifty 50 companies, computes sentiment factors, merges them with historical market data from Yahoo Finance, trains leak-free chronological machine learning models with purged walk-forward cross-validation, executes long-only backtests with realistic transaction costs and slippage, and presents all intelligence in a Bloomberg/terminal-inspired React dashboard.

---

## Architecture Overview

```
sentiment-alpha/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application & startup lifecycle
│   │   ├── config.py                   # Pydantic BaseSettings & path configuration
│   │   ├── api/
│   │   │   └── routes/                 # REST endpoints (health, stocks, news, sentiment, factors, models, signals, backtests, pipeline)
│   │   ├── core/                       # Logging & custom exception handlers
│   │   ├── database/                   # SQLAlchemy engine, SQLite models, schemas, repositories
│   │   ├── services/
│   │   │   ├── ingestion.py            # Financial RSS news ingestion & canonical deduplication
│   │   │   ├── stock_mapper.py         # Deterministic Nifty 50 entity mapper (regex boundary protection)
│   │   │   ├── sentiment_analyzer.py   # Batched FinBERT sentiment orchestration
│   │   │   ├── factor_builder.py       # Daily sentiment factors (confidence-weighted, 7d/14d rolling, momentum, surprise)
│   │   │   ├── price_data.py           # yfinance market data & technical indicators (RSI-14, MACD, MA20, MA50, Volatility)
│   │   │   ├── feature_engineering.py  # Leak-free feature merging & chronological purged validation splits
│   │   │   ├── ml_models.py            # Logistic Regression & Random Forest classifiers with held-out metrics
│   │   │   ├── signal_generator.py     # Research signals (BUY/HOLD/SELL) with explainability & risk warnings
│   │   │   ├── backtester.py           # Long-only portfolio backtesting with session-next execution, slippage & fees
│   │   │   └── pipeline_service.py     # Thread-pool background job executor & status tracking
│   │   └── ml/
│   │       ├── finbert_loader.py       # Thread-safe lazy FinBERT loader with offline caching & state tracking
│   │       ├── inference.py            # Batched local FinBERT inference engine (CPU/CUDA)
│   │       └── model_registry.py       # Joblib persistence & versioning for trained models
│   ├── tests/                          # Automated test suite (18 unit/integration tests with 100% pass rate)
│   ├── scripts/
│   │   ├── initialize_db.py            # Database initialization and stock universe seeding
│   │   └── run_pipeline.py             # CLI runner for end-to-end pipeline execution
│   ├── data/
│   │   ├── models/finbert/             # Local ProsusAI/finbert cached weights (~438MB)
│   │   └── models/trained/             # Trained ML joblib models & metadata
│   ├── requirements.txt                # Pinned backend dependencies
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/                        # Axios client with typed FastAPI endpoints
│   │   ├── components/                 # FinBERT live status badge, navigation
│   │   ├── layouts/                    # Dark financial terminal layout shell
│   │   ├── pages/
│   │   │   ├── MarketOverviewPage.tsx  # Market sentiment KPIs, top bullish/bearish ranking, benchmark trend
│   │   │   ├── StockResearchPage.tsx   # Stock selector, historical price + MAs, sentiment factors, trading signal
│   │   │   ├── NewsExplorerPage.tsx    # Paginated news, source filter, stock filter, FinBERT probability breakdown
│   │   │   ├── MLLabPage.tsx           # Model training, walk-forward purged validation, feature importance chart
│   │   │   ├── BacktestingLabPage.tsx  # Strategy config, equity curve vs benchmark, drawdown, trade ledger table
│   │   │   └── SystemHealthPage.tsx    # FinBERT diagnostics, database status, background jobs tracker
│   │   ├── types/                      # TypeScript domain models
│   │   ├── App.tsx                     # React Router & TanStack Query setup
│   │   └── main.tsx                    # React DOM entry point
│   ├── package.json
│   ├── vite.config.ts                  # Vite proxying /api to http://localhost:8000
│   └── tailwind.config.js              # Dark trading terminal color palette
└── README.md
```

---

## Windows 11 Setup and Execution

### Prerequisites
- Python 3.10+ (installed in PATH or Windows user AppData)
- Node.js v18+ and npm

### Terminal 1 — Backend (FastAPI & Local FinBERT)
Open PowerShell in the project directory:

```powershell
cd sentiment-alpha\backend

# 1. Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies (PyTorch CPU & ML packages)
pip install -r requirements.txt

# 3. Initialize SQLite database & seed Nifty 50 universe
python scripts/initialize_db.py

# 4. (Optional) Run the complete CLI pipeline (fetches RSS, runs local FinBERT, syncs prices, trains ML model, runs backtest)
python scripts/run_pipeline.py --limit 30

# 5. Start FastAPI development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

FastAPI interactive Swagger documentation will be available at: `http://localhost:8000/docs`

---

### Terminal 2 — Frontend (React, TypeScript & Vite)
Open a second PowerShell window:

```powershell
cd sentiment-alpha\frontend

# 1. Install Node dependencies
npm install

# 2. Start Vite development server
npm run dev
```

Open your browser to: `http://localhost:5173`

---

## Local FinBERT Inference Engine

- **Model**: `ProsusAI/finbert` (Hugging Face Transformers)
- **Execution**: Runs **100% locally on your computer** using PyTorch CPU backend (`model.eval()`, `torch.inference_mode()`).
- **Cache Location**: `backend/data/models/finbert/`
- **Offline Mode**: Supported via `FINBERT_OFFLINE=True`.
- **Status Lifecycle**: `not_downloaded` $\rightarrow$ `downloading` $\rightarrow$ `loading` $\rightarrow$ `ready` $\rightarrow$ `failed`.
- **Score Formula**:
  $$\text{sentiment\_score} = \text{positive\_probability} - \text{negative\_probability}$$
  Class probabilities and signed scores are kept strictly distinct.

---

## Automated Test Suite

Run the complete automated test suite (18 unit & integration tests) in PowerShell:

```powershell
cd sentiment-alpha\backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

Tests cover:
- Database initialization, foreign keys, and unique constraint deduplication
- Deterministic stock regex mapping and boundary protection against false positives
- Real RSS parsing, canonical URL hashing, and timestamp normalization
- FinBERT score calculation ($P_{\text{pos}} - P_{\text{neg}}$) and empty text handling
- Daily sentiment factor aggregation and confidence weighting
- Chronological walk-forward ML dataset purging (look-ahead protection)
- Backtest execution timing ($t+1$ session execution) and fee/slippage deductions
- Full FastAPI endpoint response schemas and error codes
- End-to-end integration test (Article $\rightarrow$ Entity Mapping $\rightarrow$ FinBERT Inference $\rightarrow$ Daily Factors)

---

## Pipeline Operations via CLI

Run individual operations from the command line:

```powershell
# Ingest news feeds only
python -c "from app.database.engine import SessionLocal; from app.services.ingestion import NewsIngestionService; db = SessionLocal(); NewsIngestionService(db).ingest_all_feeds(); db.close()"

# Run local FinBERT sentiment analysis on pending articles
python -c "from app.database.engine import SessionLocal; from app.services.sentiment_analyzer import SentimentAnalyzerService; db = SessionLocal(); SentimentAnalyzerService(db).analyze_unprocessed_articles(limit=50); db.close()"

# Sync price history and technical indicators for a stock
python -c "from app.database.engine import SessionLocal; from app.services.price_data import MarketDataService; db = SessionLocal(); MarketDataService(db).fetch_and_calculate_indicators('RELIANCE'); db.close()"

# Train a chronological ML model
python -c "from app.database.engine import SessionLocal; from app.services.ml_models import MLModelService; db = SessionLocal(); MLModelService(db).train_model(model_type='RandomForestClassifier', target_horizon=5); db.close()"

# Execute a backtest
python -c "from app.database.engine import SessionLocal; from app.services.backtester import PortfolioBacktester; db = SessionLocal(); print(PortfolioBacktester(db).run_backtest(symbol='RELIANCE')); db.close()"
```

---

## Web Dashboard Pages

1. **Market Overview** (`/`): Real-time FinBERT market sentiment score, Bullish vs Bearish breakdown, Nifty 50 top bullish/bearish ranking, Benchmark trend line, and live RSS news feed.
2. **Stock Research** (`/research`): Stock selector, Price & Moving Averages (MA20/MA50) chart, Sentiment factor trends (7d/14d rolling), Technical KPIs (RSI, Volatility, Momentum), and Transparent Research Signal with natural language explanation and risk warnings.
3. **News Explorer** (`/news`): Multi-filter search (headline, stock, sentiment label, source), paginated cards with raw FinBERT 3-class probability distribution bars, and direct source links.
4. **ML Lab** (`/ml-lab`): Prediction horizon selection (5d/21d), model selection (Random Forest, Logistic Regression), feature checklist, walk-forward purged training job trigger, model version comparison table, and feature importance bar chart.
5. **Backtesting Lab** (`/backtesting`): Interactive parameter configuration (sentiment entry/exit thresholds, initial capital, slippage, brokerage fees), Strategy Equity Curve vs Benchmark Buy & Hold, Underwater Drawdown chart, and complete Trade Ledger table.
6. **System Health** (`/health`): Live FinBERT model badge and cache status, SQLite database connectivity, and active/completed background job progress monitor.
#   S e n t i m e n t A l p h a - S t o c k - a n a l y z e r  
 