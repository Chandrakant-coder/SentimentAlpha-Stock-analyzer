import datetime
from app.database.repositories import StockRepository, ArticleRepository, ArticleStockMappingRepository, FactorRepository
from app.services.stock_mapper import stock_mapper
from app.services.sentiment_analyzer import SentimentAnalyzerService
from app.services.factor_builder import SentimentFactorBuilder

def test_article_lifecycle_integration(db):
    # 1. Seed stock
    stock_repo = StockRepository(db)
    stock = stock_repo.add_or_update(
        symbol="RELIANCE",
        ticker="RELIANCE.NS",
        company_name="Reliance Industries Limited",
        sector="Energy & Petrochemicals",
        aliases="Reliance,RIL,Jio",
    )

    # 2. Ingest Article
    art_repo = ArticleRepository(db)
    pub_dt = datetime.datetime.utcnow()
    article = art_repo.create(
        title="Reliance announces massive expansion in green energy and retail",
        description="RIL plans 50000 crore capital expenditure driving strong earnings outlook.",
        url="https://example.com/ril-green-energy",
        source="Economic Times",
        published_at=pub_dt,
        fingerprint="fp_ril_integration",
    )
    assert article is not None

    # 3. Stock Mapping
    matched = stock_mapper.map_text_to_stocks(f"{article.title} {article.description}")
    symbols = [m["symbol"] for m in matched]
    assert "RELIANCE" in symbols

    mapping_repo = ArticleStockMappingRepository(db)
    for m in matched:
        mapping_repo.add_mapping(article.id, stock.id, m["matched_term"], m["confidence"])

    # 4. Sentiment Inference
    analyzer = SentimentAnalyzerService(db)
    res = analyzer.analyze_unprocessed_articles(limit=10)
    assert res["successful"] == 1

    # 5. Daily Factor Generation
    factor_builder = SentimentFactorBuilder(db)
    factors = factor_builder.compute_factors_for_stock("RELIANCE")
    assert len(factors) == 1
    f = factors[0]
    assert f["article_count"] == 1
    assert f["confidence_weighted_sentiment"] > 0
    assert f["bullish_count"] == 1
