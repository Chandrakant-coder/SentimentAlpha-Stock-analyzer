import datetime
from app.database.models import Stock, Article, ArticleStockMapping, SentimentResult
from app.database.repositories import StockRepository, FactorRepository
from app.services.factor_builder import SentimentFactorBuilder

def test_sentiment_factor_aggregation(db):
    stock_repo = StockRepository(db)
    factor_repo = FactorRepository(db)
    stock = stock_repo.add_or_update("TATAMOTORS", "TATAMOTORS.NS", "Tata Motors Limited")

    # Add 2 articles on the same day with different sentiments
    dt = datetime.datetime(2026, 5, 10, 10, 0, 0)
    
    art1 = Article(
        title="Tata Motors EV sales hit record high",
        url="https://example.com/tm1",
        source="ET",
        published_at=dt,
        content_fingerprint="fp1",
    )
    art2 = Article(
        title="Tata Motors commercial vehicles see modest growth",
        url="https://example.com/tm2",
        source="MC",
        published_at=dt,
        content_fingerprint="fp2",
    )
    db.add_all([art1, art2])
    db.commit()

    # Mappings
    db.add(ArticleStockMapping(article_id=art1.id, stock_id=stock.id, matched_term="Tata Motors", confidence=1.0))
    db.add(ArticleStockMapping(article_id=art2.id, stock_id=stock.id, matched_term="Tata Motors", confidence=0.9))

    # Sentiments
    db.add(SentimentResult(
        article_id=art1.id,
        model_name="ProsusAI/finbert",
        model_version="1.0.0",
        sentiment_label="positive",
        positive_probability=0.90,
        negative_probability=0.05,
        neutral_probability=0.05,
        sentiment_score=0.85,
        inference_status="ready",
    ))
    db.add(SentimentResult(
        article_id=art2.id,
        model_name="ProsusAI/finbert",
        model_version="1.0.0",
        sentiment_label="neutral",
        positive_probability=0.20,
        negative_probability=0.10,
        neutral_probability=0.70,
        sentiment_score=0.10,
        inference_status="ready",
    ))
    db.commit()

    builder = SentimentFactorBuilder(db)
    factors = builder.compute_factors_for_stock("TATAMOTORS")
    assert len(factors) == 1
    f = factors[0]

    assert f["article_count"] == 2
    assert f["bullish_count"] == 1
    assert f["neutral_count"] == 1
    assert f["bearish_count"] == 0
    # Weighted sentiment must give higher weight to high-conviction article 1
    assert f["confidence_weighted_sentiment"] > f["daily_mean_sentiment"]
    assert f["rolling_7d_mean"] is not None
