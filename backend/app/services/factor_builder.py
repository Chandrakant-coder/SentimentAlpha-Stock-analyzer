import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.logging import logger
from app.database.models import Article, ArticleStockMapping, SentimentResult, Stock, SentimentFactor
from app.database.repositories import StockRepository, FactorRepository
from app.services.nse_calendar import publication_session_date

class SentimentFactorBuilder:
    def __init__(self, db: Session):
        self.db = db
        self.stock_repo = StockRepository(db)
        self.factor_repo = FactorRepository(db)

    def compute_factors_for_stock(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Gathers all sentiment records mapped to a stock, groups them by day,
        computes daily aggregates & rolling features, and stores them in SQLite.
        """
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            logger.warning(f"Stock {symbol} not found.")
            return []

        # Query all articles mapped to this stock that have valid sentiment
        rows = (
            self.db.query(
                Article.published_at,
                SentimentResult.sentiment_score,
                SentimentResult.positive_probability,
                SentimentResult.negative_probability,
                SentimentResult.neutral_probability,
                SentimentResult.sentiment_label,
                ArticleStockMapping.confidence,
            )
            .join(ArticleStockMapping, Article.id == ArticleStockMapping.article_id)
            .join(SentimentResult, Article.id == SentimentResult.article_id)
            .filter(
                ArticleStockMapping.stock_id == stock.id,
                SentimentResult.inference_status == "ready",
            )
            .all()
        )

        if not rows:
            logger.info(f"No sentiment records found for stock {symbol}.")
            return []

        # Convert to pandas DataFrame
        data = []
        for r in rows:
            pub_date = r[0]
            # After 15:30 IST cash close, the article belongs to the next calendar day
            # so it cannot enter a same-session close signal.
            d = publication_session_date(pub_date)
            data.append({
                "date": pd.to_datetime(d),
                "score": float(r[1]),
                "pos_prob": float(r[2]),
                "neg_prob": float(r[3]),
                "neu_prob": float(r[4]),
                "label": str(r[5]).lower(),
                "confidence": float(r[6] or 1.0),
            })

        df = pd.DataFrame(data)

        # Calculate weight: confidence * (1.0 - neutral_probability)
        # Articles with higher certainty / non-neutral probability carry higher weight
        df["weight"] = df["confidence"] * np.maximum(0.01, 1.0 - df["neu_prob"])
        df["weighted_score"] = df["score"] * df["weight"]

        # Group by Date
        daily_records = []
        grouped = df.groupby("date")

        for dt, group in grouped:
            article_count = len(group)
            bullish_count = int((group["label"] == "positive").sum())
            bearish_count = int((group["label"] == "negative").sum())
            neutral_count = int((group["label"] == "neutral").sum())

            daily_mean = float(group["score"].mean())
            total_weight = float(group["weight"].sum())
            weighted_sentiment = float(group["weighted_score"].sum() / total_weight) if total_weight > 0 else daily_mean

            mean_pos = float(group["pos_prob"].mean())
            mean_neg = float(group["neg_prob"].mean())
            mean_neu = float(group["neu_prob"].mean())

            daily_records.append({
                "date": dt,
                "daily_mean_sentiment": daily_mean,
                "confidence_weighted_sentiment": weighted_sentiment,
                "article_count": article_count,
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count,
                "mean_positive_prob": mean_pos,
                "mean_negative_prob": mean_neg,
                "mean_neutral_prob": mean_neu,
            })

        agg_df = pd.DataFrame(daily_records).sort_values("date").reset_index(drop=True)

        # Compute rolling window factors
        # 7-day rolling mean
        agg_df["rolling_7d_mean"] = agg_df["confidence_weighted_sentiment"].rolling(window=7, min_periods=1).mean()
        # 14-day rolling mean
        agg_df["rolling_14d_mean"] = agg_df["confidence_weighted_sentiment"].rolling(window=14, min_periods=1).mean()
        # Sentiment momentum: short-term rolling mean minus longer-term rolling mean
        agg_df["sentiment_momentum"] = agg_df["rolling_7d_mean"] - agg_df["rolling_14d_mean"]
        # Sentiment volatility: 14-day standard deviation
        agg_df["sentiment_volatility"] = agg_df["confidence_weighted_sentiment"].rolling(window=14, min_periods=2).std().fillna(0.0)
        # Sentiment surprise: today's sentiment vs 14-day expected moving average
        agg_df["sentiment_surprise"] = agg_df["confidence_weighted_sentiment"] - agg_df["rolling_14d_mean"]

        results = []
        for _, row in agg_df.iterrows():
            d_val = row["date"].to_pydatetime()
            factor_dict = {
                "daily_mean_sentiment": round(float(row["daily_mean_sentiment"]), 4) if pd.notna(row["daily_mean_sentiment"]) else None,
                "confidence_weighted_sentiment": round(float(row["confidence_weighted_sentiment"]), 4) if pd.notna(row["confidence_weighted_sentiment"]) else None,
                "article_count": int(row["article_count"]),
                "bullish_count": int(row["bullish_count"]),
                "bearish_count": int(row["bearish_count"]),
                "neutral_count": int(row["neutral_count"]),
                "mean_positive_prob": round(float(row["mean_positive_prob"]), 4) if pd.notna(row["mean_positive_prob"]) else None,
                "mean_negative_prob": round(float(row["mean_negative_prob"]), 4) if pd.notna(row["mean_negative_prob"]) else None,
                "mean_neutral_prob": round(float(row["mean_neutral_prob"]), 4) if pd.notna(row["mean_neutral_prob"]) else None,
                "rolling_7d_mean": round(float(row["rolling_7d_mean"]), 4) if pd.notna(row["rolling_7d_mean"]) else None,
                "rolling_14d_mean": round(float(row["rolling_14d_mean"]), 4) if pd.notna(row["rolling_14d_mean"]) else None,
                "sentiment_momentum": round(float(row["sentiment_momentum"]), 4) if pd.notna(row["sentiment_momentum"]) else None,
                "sentiment_volatility": round(float(row["sentiment_volatility"]), 4) if pd.notna(row["sentiment_volatility"]) else None,
                "sentiment_surprise": round(float(row["sentiment_surprise"]), 4) if pd.notna(row["sentiment_surprise"]) else None,
            }
            self.factor_repo.save_factor(stock.id, d_val, factor_dict)
            results.append({"date": d_val, **factor_dict})

        logger.info(f"Built and persisted {len(results)} daily sentiment factors for {symbol}.")
        return results

    def build_factors_for_all_stocks(self) -> Dict[str, int]:
        stocks = self.stock_repo.get_all(active_only=True)
        out = {}
        for s in stocks:
            factors = self.compute_factors_for_stock(s.symbol)
            out[s.symbol] = len(factors)
        return out
