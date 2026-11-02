from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database.engine import get_db
from app.database.models import Stock, Article, ArticleStockMapping, SentimentResult, SentimentFactor
from app.database.repositories import StockRepository

router = APIRouter(prefix="/sentiment", tags=["Sentiment Analytics"])

@router.get("/overview")
def get_market_sentiment_overview(db: Session = Depends(get_db)):
    """
    Returns market sentiment summary, top bullish, top bearish stocks,
    and news volume trends.
    """
    # 1. Total positive vs negative vs neutral articles
    counts = (
        db.query(SentimentResult.sentiment_label, func.count(SentimentResult.id))
        .filter(SentimentResult.inference_status == "ready")
        .group_by(SentimentResult.sentiment_label)
        .all()
    )
    sentiment_distribution = {label: count for label, count in counts}

    # 2. Top bullish and bearish stocks based on latest daily sentiment factors
    # Subquery for latest factor per stock
    subq = (
        db.query(
            SentimentFactor.stock_id,
            func.max(SentimentFactor.date).label("max_date")
        )
        .group_by(SentimentFactor.stock_id)
        .subquery()
    )

    latest_factors = (
        db.query(SentimentFactor, Stock.symbol, Stock.company_name)
        .join(subq, (SentimentFactor.stock_id == subq.c.stock_id) & (SentimentFactor.date == subq.c.max_date))
        .join(Stock, SentimentFactor.stock_id == Stock.id)
        .all()
    )

    stock_sentiments = []
    for f, sym, name in latest_factors:
        score = f.confidence_weighted_sentiment or 0.0
        stock_sentiments.append({
            "symbol": sym,
            "company_name": name,
            "score": round(score, 3),
            "article_count": f.article_count,
            "bullish_count": f.bullish_count,
            "bearish_count": f.bearish_count,
            "momentum": round(f.sentiment_momentum or 0.0, 3),
        })

    bullish_ranking = sorted(stock_sentiments, key=lambda x: x["score"], reverse=True)[:5]
    bearish_ranking = sorted(stock_sentiments, key=lambda x: x["score"])[:5]

    # Overall market sentiment score
    overall_mean = (
        db.query(func.avg(SentimentResult.sentiment_score))
        .filter(SentimentResult.inference_status == "ready")
        .scalar()
    ) or 0.0

    return {
        "overall_market_sentiment": round(float(overall_mean), 3),
        "sentiment_distribution": sentiment_distribution,
        "bullish_ranking": bullish_ranking,
        "bearish_ranking": bearish_ranking,
        "total_active_stocks": len(stock_sentiments),
    }

@router.get("/stocks/{symbol}")
def get_stock_sentiment_detail(symbol: str, db: Session = Depends(get_db)):
    stock_repo = StockRepository(db)
    stock = stock_repo.get_by_symbol(symbol)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    recent_articles = (
        db.query(Article, SentimentResult)
        .join(ArticleStockMapping, Article.id == ArticleStockMapping.article_id)
        .outerjoin(SentimentResult, Article.id == SentimentResult.article_id)
        .filter(ArticleStockMapping.stock_id == stock.id)
        .order_by(desc(Article.published_at))
        .limit(20)
        .all()
    )

    article_list = []
    for art, sent in recent_articles:
        article_list.append({
            "id": art.id,
            "title": art.title,
            "source": art.source,
            "published_at": art.published_at.isoformat(),
            "sentiment_label": sent.sentiment_label if sent else "pending",
            "sentiment_score": sent.sentiment_score if sent else 0.0,
            "probabilities": {
                "positive": sent.positive_probability if sent else 0.0,
                "negative": sent.negative_probability if sent else 0.0,
                "neutral": sent.neutral_probability if sent else 1.0,
            } if sent else None,
        })

    return {
        "symbol": stock.symbol,
        "company_name": stock.company_name,
        "sector": stock.sector,
        "recent_articles": article_list,
    }
