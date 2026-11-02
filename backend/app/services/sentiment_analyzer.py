from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.repositories import ArticleRepository, SentimentRepository
from app.ml.inference import inference_engine

class SentimentAnalyzerService:
    def __init__(self, db: Session):
        self.db = db
        self.article_repo = ArticleRepository(db)
        self.sentiment_repo = SentimentRepository(db)
        self.engine = inference_engine

    def analyze_unprocessed_articles(self, limit: int = 100, progress_callback = None) -> Dict[str, Any]:
        """
        Fetches unprocessed articles, performs batched local FinBERT inference,
        and saves results.
        """
        articles = self.article_repo.get_unprocessed_for_sentiment(limit=limit)
        total = len(articles)
        if total == 0:
            logger.info("No unanalyzed articles found.")
            return {"total_analyzed": 0, "successful": 0, "failed": 0}

        logger.info(f"Analyzing sentiment for {total} articles using FinBERT...")

        # Prepare text strings
        texts = [f"{a.title}. {a.description or ''}" for a in articles]
        
        # Run inference in batches
        results = self.engine.predict_batch(texts)
        
        success_count = 0
        failed_count = 0

        for idx, (article, res) in enumerate(zip(articles, results)):
            self.sentiment_repo.save_result(
                article_id=article.id,
                model_name=res["model_name"],
                model_version=res["model_version"],
                label=res["sentiment_label"],
                pos_prob=res["positive_probability"],
                neg_prob=res["negative_probability"],
                neu_prob=res["neutral_probability"],
                score=res["sentiment_score"],
                status=res["inference_status"],
                error_message=res.get("error_message"),
            )
            if res["inference_status"] == "ready":
                success_count += 1
            else:
                failed_count += 1

            if progress_callback and (idx + 1) % 5 == 0:
                progress_callback(int(((idx + 1) / total) * 100), idx + 1, total)

        logger.info(f"Sentiment analysis completed: {success_count} success, {failed_count} failed.")
        return {
            "total_analyzed": total,
            "successful": success_count,
            "failed": failed_count,
        }
