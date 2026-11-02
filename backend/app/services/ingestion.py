import hashlib
import datetime
import email.utils
from typing import List, Dict, Any, Optional
import feedparser
import requests
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.config import settings
from app.database.repositories import ArticleRepository, ArticleStockMappingRepository, StockRepository
from app.services.stock_mapper import stock_mapper

# Real financial news RSS feeds covering Indian markets & Nifty 50
FINANCIAL_RSS_FEEDS = [
    {
        "name": "Economic Times - Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    },
    {
        "name": "Moneycontrol - Market News",
        "url": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    },
    {
        "name": "Livemint - Companies News",
        "url": "https://www.livemint.com/rss/companies",
    },
    {
        "name": "Yahoo Finance India",
        "url": "https://finance.yahoo.com/news/rssindex",
    },
]

class NewsIngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.article_repo = ArticleRepository(db)
        self.mapping_repo = ArticleStockMappingRepository(db)
        self.stock_repo = StockRepository(db)

    def _normalize_timestamp(self, entry: Any) -> datetime.datetime:
        """Parses published date into normalized UTC datetime"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime.datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime.datetime(*entry.updated_parsed[:6])
            except Exception:
                pass

        raw_date = getattr(entry, "published", None) or getattr(entry, "updated", None)
        if raw_date:
            try:
                parsed_tuple = email.utils.parsedate_to_datetime(raw_date)
                return parsed_tuple.replace(tzinfo=None)
            except Exception:
                pass

        return datetime.datetime.utcnow()

    def _generate_fingerprint(self, title: str, url: str, published_at: datetime.datetime) -> str:
        """Creates unique canonical SHA-256 fingerprint"""
        data = f"{title.strip().lower()}|{url.strip().lower()}|{published_at.strftime('%Y-%m-%d')}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def ingest_feed(self, feed_name: str, feed_url: str) -> Dict[str, int]:
        """Ingests articles from a single RSS feed"""
        stats = {"fetched": 0, "inserted": 0, "duplicates": 0, "mapped": 0}
        logger.info(f"Ingesting feed: {feed_name} from {feed_url}")

        try:
            # Fetch with custom headers to prevent 403 blocks
            resp = requests.get(
                feed_url,
                timeout=settings.NEWS_REQUEST_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SentimentAlpha/1.0"},
            )
            parsed = feedparser.parse(resp.content)
            stats["fetched"] = len(parsed.entries)

            for entry in parsed.entries[: settings.MAX_ARTICLES_PER_FEED]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                
                if not title or not link:
                    continue

                published_at = self._normalize_timestamp(entry)
                fingerprint = self._generate_fingerprint(title, link, published_at)

                article = self.article_repo.create(
                    title=title,
                    description=summary,
                    url=link,
                    source=feed_name,
                    published_at=published_at,
                    fingerprint=fingerprint,
                )

                if not article:
                    stats["duplicates"] += 1
                    continue

                stats["inserted"] += 1

                # Map article text to Nifty stocks
                combined_text = f"{title} {summary}"
                matched_stocks = stock_mapper.map_text_to_stocks(combined_text)

                for match in matched_stocks:
                    db_stock = self.stock_repo.get_by_symbol(match["symbol"])
                    if db_stock:
                        self.mapping_repo.add_mapping(
                            article_id=article.id,
                            stock_id=db_stock.id,
                            matched_term=match["matched_term"],
                            confidence=match["confidence"],
                        )
                        stats["mapped"] += 1

        except Exception as e:
            logger.error(f"Error fetching RSS feed '{feed_name}': {e}", exc_info=True)

        return stats

    def ingest_all_feeds(self, feeds: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Ingests all configured feeds"""
        target_feeds = feeds or FINANCIAL_RSS_FEEDS
        total_stats = {"total_fetched": 0, "total_inserted": 0, "total_duplicates": 0, "total_mapped": 0, "feeds": {}}

        for feed in target_feeds:
            feed_stats = self.ingest_feed(feed["name"], feed["url"])
            total_stats["feeds"][feed["name"]] = feed_stats
            total_stats["total_fetched"] += feed_stats["fetched"]
            total_stats["total_inserted"] += feed_stats["inserted"]
            total_stats["total_duplicates"] += feed_stats["duplicates"]
            total_stats["total_mapped"] += feed_stats["mapped"]

        logger.info(f"Ingestion complete: {total_stats['total_inserted']} new articles saved, {total_stats['total_mapped']} mappings created.")
        return total_stats
