import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.core.logging import logger
from app.core.exceptions import SentimentAlphaException
from app.database.engine import engine, Base, SessionLocal
from app.database.models import Stock
from app.database.repositories import StockRepository
from app.services.stock_mapper import DEFAULT_NIFTY_STOCKS
from app.api.routes import health, stocks, news, sentiment, factors, models, signals, backtests, pipeline

def init_db():
    """Idempotently create tables and seed default Nifty 50 stocks"""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    from app.database.migrations import apply_sqlite_migrations
    apply_sqlite_migrations(engine)

    db = SessionLocal()
    try:
        stock_repo = StockRepository(db)
        existing = stock_repo.get_all(active_only=False)
        if not existing:
            logger.info("Seeding default Nifty 50 universe into database...")
            for s in DEFAULT_NIFTY_STOCKS:
                stock_repo.add_or_update(
                    symbol=s["symbol"],
                    ticker=s["ticker"],
                    company_name=s["company_name"],
                    sector=s.get("sector"),
                    aliases=json.dumps(s.get("aliases", [])),
                )
            logger.info(f"Seeded {len(DEFAULT_NIFTY_STOCKS)} stocks.")
    except Exception as e:
        logger.error(f"Error seeding database: {e}", exc_info=True)
    finally:
        db.close()

import threading

def _preload_finbert():
    try:
        from app.ml.finbert_loader import finbert_loader
        has_config = list(finbert_loader.cache_dir.glob("**/config.json"))
        if has_config:
            logger.info("FinBERT weights detected on disk. Preloading into memory...")
            finbert_loader.load_model()
    except Exception as e:
        logger.warning(f"Background FinBERT preload warning: {e}")


def _auto_sync_stale_prices():
    """Background thread: sync any stocks whose latest bar is behind the expected NSE session."""
    try:
        from app.services.price_data import MarketDataService
        db = SessionLocal()
        try:
            service = MarketDataService(db)
            result = service.sync_stale_stocks(period="1y")
            if result["symbols"] > 0:
                logger.info(
                    "Auto-sync on startup: synced %s/%s stale symbols.",
                    result["successful"], result["symbols"],
                )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Background price auto-sync warning: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    init_db()
    threading.Thread(target=_preload_finbert, daemon=True).start()
    threading.Thread(target=_auto_sync_stale_prices, daemon=True).start()
    yield
    # Shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Local AI Financial Intelligence Web Platform powered by FinBERT",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(SentimentAlphaException)
async def sentiment_alpha_exception_handler(request: Request, exc: SentimentAlphaException):
    return JSONResponse(
        status_code=400,
        content={"error": exc.message, "details": exc.details},
    )

# Include Routers
app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(stocks.router, prefix=settings.API_PREFIX)
app.include_router(news.router, prefix=settings.API_PREFIX)
app.include_router(sentiment.router, prefix=settings.API_PREFIX)
app.include_router(factors.router, prefix=settings.API_PREFIX)
app.include_router(models.router, prefix=settings.API_PREFIX)
app.include_router(signals.router, prefix=settings.API_PREFIX)
app.include_router(backtests.router, prefix=settings.API_PREFIX)
app.include_router(pipeline.router, prefix=settings.API_PREFIX)

@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/health",
        "status": f"{settings.API_PREFIX}/system/status",
    }
