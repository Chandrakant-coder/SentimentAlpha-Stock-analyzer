from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.engine import get_db
from app.database.repositories import ArticleRepository, ArticleStockMappingRepository
from app.database.schemas import ArticleListResponse, ArticleResponse, SentimentResultResponse
from app.database.models import Article

router = APIRouter(prefix="/news", tags=["Financial News"])

@router.get("", response_model=ArticleListResponse)
def list_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    symbol: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    repo = ArticleRepository(db)
    mapping_repo = ArticleStockMappingRepository(db)
    items, total = repo.get_paginated(
        page=page,
        page_size=page_size,
        symbol=symbol,
        sentiment_label=sentiment,
        source=source,
        search=search,
    )

    result_items: List[ArticleResponse] = []
    for art in items:
        mapped_symbols = mapping_repo.get_mapped_symbols_for_article(art.id)
        sent_resp = None
        if art.sentiment:
            sent_resp = SentimentResultResponse(
                sentiment_label=art.sentiment.sentiment_label,
                positive_probability=art.sentiment.positive_probability,
                negative_probability=art.sentiment.negative_probability,
                neutral_probability=art.sentiment.neutral_probability,
                sentiment_score=art.sentiment.sentiment_score,
                model_name=art.sentiment.model_name,
                model_version=art.sentiment.model_version,
                inference_status=art.sentiment.inference_status,
                inference_timestamp=art.sentiment.inference_timestamp,
                error_message=art.sentiment.error_message,
            )

        result_items.append(
            ArticleResponse(
                id=art.id,
                title=art.title,
                description=art.description,
                url=art.url,
                source=art.source,
                published_at=art.published_at,
                content_fingerprint=art.content_fingerprint,
                created_at=art.created_at,
                sentiment=sent_resp,
                mapped_stocks=mapped_symbols,
            )
        )

    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return ArticleListResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=result_items,
    )

@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    art = db.query(Article).filter(Article.id == article_id).first()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")

    mapping_repo = ArticleStockMappingRepository(db)
    mapped_symbols = mapping_repo.get_mapped_symbols_for_article(art.id)

    sent_resp = None
    if art.sentiment:
        sent_resp = SentimentResultResponse(
            sentiment_label=art.sentiment.sentiment_label,
            positive_probability=art.sentiment.positive_probability,
            negative_probability=art.sentiment.negative_probability,
            neutral_probability=art.sentiment.neutral_probability,
            sentiment_score=art.sentiment.sentiment_score,
            model_name=art.sentiment.model_name,
            model_version=art.sentiment.model_version,
            inference_status=art.sentiment.inference_status,
            inference_timestamp=art.sentiment.inference_timestamp,
            error_message=art.sentiment.error_message,
        )

    return ArticleResponse(
        id=art.id,
        title=art.title,
        description=art.description,
        url=art.url,
        source=art.source,
        published_at=art.published_at,
        content_fingerprint=art.content_fingerprint,
        created_at=art.created_at,
        sentiment=sent_resp,
        mapped_stocks=mapped_symbols,
    )
