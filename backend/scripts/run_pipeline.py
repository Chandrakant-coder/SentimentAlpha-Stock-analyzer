import sys
import argparse
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.logging import logger
from app.database.engine import SessionLocal
from app.main import init_db
from app.services.ingestion import NewsIngestionService
from app.services.sentiment_analyzer import SentimentAnalyzerService
from app.services.factor_builder import SentimentFactorBuilder
from app.services.price_data import MarketDataService
from app.services.ml_models import MLModelService
from app.services.signal_generator import SignalGeneratorService
from app.services.backtester import PortfolioBacktester

def run_full_pipeline(symbols=None, news_limit=50):
    logger.info("==========================================")
    logger.info("   STARTING SENTIMENT-ALPHA PIPELINE     ")
    logger.info("==========================================")
    
    init_db()
    db = SessionLocal()

    try:
        # Step 1: Ingest News
        logger.info("\n--- [1/6] Ingesting Financial News RSS ---")
        ingestion = NewsIngestionService(db)
        ingest_stats = ingestion.ingest_all_feeds()
        logger.info(f"Ingested {ingest_stats['total_inserted']} new articles, mapped {ingest_stats['total_mapped']} stock mentions.")

        # Step 2: FinBERT Sentiment Inference
        logger.info("\n--- [2/6] Running Local FinBERT Sentiment Analysis ---")
        analyzer = SentimentAnalyzerService(db)
        sent_stats = analyzer.analyze_unprocessed_articles(limit=news_limit)
        logger.info(f"Analyzed {sent_stats['total_analyzed']} articles ({sent_stats['successful']} successful).")

        # Step 3: Factor Aggregation
        logger.info("\n--- [3/6] Computing Daily Sentiment Factors ---")
        factor_builder = SentimentFactorBuilder(db)
        factor_stats = factor_builder.build_factors_for_all_stocks()
        logger.info(f"Updated sentiment factors for {len(factor_stats)} stocks.")

        # Step 4: Sync Market Prices & Technicals
        logger.info("\n--- [4/6] Syncing Market Data & Technical Indicators ---")
        market_service = MarketDataService(db)
        target_symbols = symbols or ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
        for sym in target_symbols:
            logger.info(f"Syncing prices for {sym}...")
            market_service.fetch_and_calculate_indicators(sym, period="1y")

        # Step 5: Train ML Model
        logger.info("\n--- [5/6] Training Chronological ML Model ---")
        ml_service = MLModelService(db)
        try:
            train_res = ml_service.train_model(model_type="RandomForestClassifier", target_horizon=5)
            logger.info(f"Model trained successfully: Accuracy={train_res['accuracy']:.3f}, F1={train_res['f1']:.3f}")
        except Exception as e:
            logger.warning(f"ML Training skipped (needs more historical data): {e}")

        # Step 6: Generate Signals & Demonstration Backtest
        logger.info("\n--- [6/6] Generating Signals & Backtesting ---")
        sig_service = SignalGeneratorService(db)
        sig_service.generate_all_signals(strategy="rule_based")

        backtester = PortfolioBacktester(db)
        for sym in ["RELIANCE"]:
            try:
                bt = backtester.run_backtest(symbol=sym, strategy_type="sentiment_momentum")
                logger.info(f"Backtest {sym}: Total Return={bt['total_return']}%, Sharpe={bt['sharpe_ratio']}, MaxDD={bt['max_drawdown']}%")
            except Exception as e:
                logger.warning(f"Backtest for {sym} skipped: {e}")

        logger.info("\n==========================================")
        logger.info("   PIPELINE RUN COMPLETED SUCCESSFULLY!  ")
        logger.info("==========================================")

    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SentimentAlpha CLI Pipeline Runner")
    parser.add_argument("--limit", type=int, default=50, help="Max articles to analyze")
    parser.add_argument("--stocks", nargs="+", default=None, help="Stock symbols to sync")
    args = parser.parse_args()

    run_full_pipeline(symbols=args.stocks, news_limit=args.limit)
