import datetime
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.models import PriceHistory, SentimentFactor, Stock
from app.database.repositories import StockRepository

FEATURE_COLUMNS = [
    # Sentiment features
    "daily_mean_sentiment",
    "confidence_weighted_sentiment",
    "article_count",
    "bullish_count",
    "bearish_count",
    "mean_positive_prob",
    "mean_negative_prob",
    "rolling_7d_mean",
    "rolling_14d_mean",
    "sentiment_momentum",
    "sentiment_volatility",
    "sentiment_surprise",
    # Technical features
    "returns_1d",
    "momentum_5d",
    "momentum_20d",
    "momentum_60d",
    "rsi_14",
    "macd",
    "macd_signal",
    "volatility_20d",
    "volume_ratio",
]

class FeatureEngineeringService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_repo = StockRepository(db)

    def prepare_dataset(
        self,
        symbol: Optional[str] = None,
        target_horizon: int = 5,
        feature_subset: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Builds a leak-free merged dataset of price technicals and sentiment factors.
        Aligns feature variables at date t with target return from t to t + horizon.
        """
        # Query price history
        q_prices = self.db.query(PriceHistory, Stock.symbol).join(Stock, PriceHistory.stock_id == Stock.id)
        if symbol:
            q_prices = q_prices.filter(Stock.symbol == symbol.upper().replace(".NS", ""))
        price_rows = q_prices.order_by(PriceHistory.date.asc()).all()

        if not price_rows:
            logger.warning("No price rows available for dataset preparation.")
            return pd.DataFrame()

        price_data = []
        for p, sym in price_rows:
            price_data.append({
                "stock_id": p.stock_id,
                "symbol": sym,
                "date": p.date,
                "close": p.close,
                "adj_close": p.adj_close if p.adj_close is not None else p.close,
                "returns_1d": p.returns_1d,
                "momentum_5d": p.momentum_5d,
                "momentum_20d": p.momentum_20d,
                "momentum_60d": p.momentum_60d,
                "ma_20": p.ma_20,
                "ma_50": p.ma_50,
                "rsi_14": p.rsi_14,
                "macd": p.macd,
                "macd_signal": p.macd_signal,
                "volatility_20d": p.volatility_20d,
                "volume_ratio": p.volume_ratio,
            })
        price_df = pd.DataFrame(price_data)

        # Query sentiment factors
        q_factors = self.db.query(SentimentFactor).order_by(SentimentFactor.date.asc()).all()
        factor_data = []
        for f in q_factors:
            factor_data.append({
                "stock_id": f.stock_id,
                "date": f.date,
                "daily_mean_sentiment": f.daily_mean_sentiment,
                "confidence_weighted_sentiment": f.confidence_weighted_sentiment,
                "article_count": f.article_count,
                "bullish_count": f.bullish_count,
                "bearish_count": f.bearish_count,
                "mean_positive_prob": f.mean_positive_prob,
                "mean_negative_prob": f.mean_negative_prob,
                "rolling_7d_mean": f.rolling_7d_mean,
                "rolling_14d_mean": f.rolling_14d_mean,
                "sentiment_momentum": f.sentiment_momentum,
                "sentiment_volatility": f.sentiment_volatility,
                "sentiment_surprise": f.sentiment_surprise,
            })
        factor_df = pd.DataFrame(factor_data)

        if not factor_df.empty:
            merged = pd.merge(price_df, factor_df, on=["stock_id", "date"], how="left")
        else:
            merged = price_df.copy()
            for col in [
                "daily_mean_sentiment", "confidence_weighted_sentiment", "article_count",
                "bullish_count", "bearish_count", "mean_positive_prob", "mean_negative_prob",
                "rolling_7d_mean", "rolling_14d_mean", "sentiment_momentum", "sentiment_volatility",
                "sentiment_surprise"
            ]:
                merged[col] = 0.0

        # Fill missing sentiment factors with neutral 0 values for non-event trading days
        sentiment_cols = [
            "daily_mean_sentiment", "confidence_weighted_sentiment", "article_count",
            "bullish_count", "bearish_count", "mean_positive_prob", "mean_negative_prob",
            "rolling_7d_mean", "rolling_14d_mean", "sentiment_momentum", "sentiment_volatility",
            "sentiment_surprise"
        ]
        for col in sentiment_cols:
            if col in merged.columns:
                merged[col] = merged[col].fillna(0.0)

        # Forward target uses adj_close so splits are not treated as returns.
        # Chart OHLC remains unadjusted close.
        merged = merged.sort_values(["symbol", "date"]).reset_index(drop=True)
        if "adj_close" not in merged.columns:
            merged["adj_close"] = merged["close"]
        merged["adj_close"] = merged["adj_close"].fillna(merged["close"])
        merged["target_forward_return"] = (
            merged.groupby("symbol")["adj_close"]
            .shift(-target_horizon)
            .sub(merged["adj_close"])
            .div(merged["adj_close"])
        )
        merged["target_direction"] = (merged["target_forward_return"] > 0).astype(int)

        # Drop rows where target is NaN (the last target_horizon rows per stock)
        clean_df = merged.dropna(subset=["target_forward_return", "returns_1d", "rsi_14"]).copy()
        clean_df = clean_df.sort_values("date").reset_index(drop=True)
        return clean_df

    def split_chronological_purged(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        horizon: int = 5,
        purge_overlap: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Chronological train/test split with look-ahead purging.
        Drops training observations from date (T_split - horizon) to T_split
        whose forward target returns span across into the test evaluation period.
        """
        if df.empty:
            return df, df

        df = df.sort_values("date").reset_index(drop=True)
        total_rows = len(df)
        split_idx = int(total_rows * (1.0 - test_size))

        train_cutoff_date = df.iloc[split_idx]["date"]

        if purge_overlap:
            # Purge training samples whose future horizon window overlaps into test set
            # A sample at t has target spanning to t + horizon. If t + horizon >= train_cutoff_date, purge it.
            purge_start_idx = max(0, split_idx - horizon)
            train_df = df.iloc[:purge_start_idx].copy()
            logger.info(f"Purged {split_idx - purge_start_idx} overlapping samples prior to test boundary {train_cutoff_date}.")
        else:
            train_df = df.iloc[:split_idx].copy()

        test_df = df.iloc[split_idx:].copy()
        return train_df, test_df
