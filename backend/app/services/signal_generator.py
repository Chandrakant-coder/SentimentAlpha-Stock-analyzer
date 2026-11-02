import datetime
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.models import Stock, PriceHistory, SentimentFactor, TradingSignal
from app.database.repositories import StockRepository
from app.services.ml_models import MLModelService

class SignalGeneratorService:
    def __init__(self, db: Session):
        self.db = db
        self.stock_repo = StockRepository(db)
        self.ml_service = MLModelService(db)

    def generate_signal_for_stock(self, symbol: str, strategy: str = "rule_based") -> Dict[str, Any]:
        """
        Generates transparent research signals with explicit explanations,
        contributing factors, and risk warnings.
        """
        stock = self.stock_repo.get_by_symbol(symbol)
        if not stock:
            return {"error": f"Stock {symbol} not found"}

        # Get latest price row
        latest_price = (
            self.db.query(PriceHistory)
            .filter(PriceHistory.stock_id == stock.id)
            .order_by(PriceHistory.date.desc())
            .first()
        )

        # Sentiment available on or before the price session only (no weekend/future news).
        latest_factor = (
            self.db.query(SentimentFactor)
            .filter(
                SentimentFactor.stock_id == stock.id,
                SentimentFactor.date <= latest_price.date,
            )
            .order_by(SentimentFactor.date.desc())
            .first()
        )

        if not latest_price:
            return {"error": f"No market data available for {symbol}"}

        date_val = latest_price.date
        rsi = latest_price.rsi_14 or 50.0
        ma20 = latest_price.ma_20 or latest_price.close
        ma50 = latest_price.ma_50 or latest_price.close
        close = latest_price.close

        sentiment = latest_factor.confidence_weighted_sentiment if latest_factor else 0.0
        sent_mom = latest_factor.sentiment_momentum if latest_factor else 0.0
        art_count = latest_factor.article_count if latest_factor else 0

        contributing = {
            "close_price": close,
            "rsi_14": round(rsi, 2),
            "ma_20": round(ma20, 2),
            "ma_50": round(ma50, 2),
            "sentiment_score": round(sentiment, 3),
            "sentiment_momentum": round(sent_mom, 3),
            "article_count": art_count,
        }

        # 1. Rule-based Strategy
        if strategy == "rule_based":
            reasons = []
            risks = []
            score = 0

            # Sentiment factor contributions
            if sentiment >= 0.15:
                score += 1
                reasons.append(f"Bullish news sentiment (+{sentiment:.2f})")
            elif sentiment <= -0.15:
                score -= 1
                reasons.append(f"Bearish news sentiment ({sentiment:.2f})")

            if sent_mom > 0.05:
                score += 1
                reasons.append("Positive sentiment momentum over 7d vs 14d")
            elif sent_mom < -0.05:
                score -= 1
                reasons.append("Deteriorating sentiment momentum")

            # Technical factor contributions
            if close > ma20 and ma20 > ma50:
                score += 1
                reasons.append("Price in upward trend (Price > MA20 > MA50)")
            elif close < ma20 and ma20 < ma50:
                score -= 1
                reasons.append("Price in downward trend (Price < MA20 < MA50)")

            if rsi > 70:
                risks.append(f"RSI ({rsi:.1f}) in overbought territory (>70)")
                score -= 0.5
            elif rsi < 30:
                reasons.append(f"RSI ({rsi:.1f}) in oversold territory (<30)")
                score += 0.5

            if art_count < 2:
                risks.append("Low news coverage volume (< 2 articles in latest cycle)")

            # Final decision
            if score >= 1.5:
                signal_type = "BUY"
                conf = min(0.95, 0.60 + score * 0.1)
                explanation = "Confluence of positive financial sentiment and bullish technical trend: " + "; ".join(reasons)
            elif score <= -1.5:
                signal_type = "SELL"
                conf = min(0.95, 0.60 + abs(score) * 0.1)
                explanation = "Confluence of negative financial sentiment and technical breakdown: " + "; ".join(reasons)
            else:
                signal_type = "HOLD"
                conf = 0.50
                explanation = "Neutral or mixed sentiment and price action signals: " + ("; ".join(reasons) if reasons else "No dominant catalyst")

            risk_warning = "; ".join(risks) if risks else "Standard market volatility risk applies."

        # 2. ML-based Strategy
        else:
            ml_pred = self.ml_service.predict_latest_for_stock(symbol)
            prob = ml_pred.get("probability", 0.5)
            signal_type = ml_pred.get("prediction", "HOLD")
            conf = prob if signal_type == "BUY" else (1.0 - prob if signal_type == "SELL" else 0.5)
            prob_up = ml_pred.get("prob_up", prob)
            prob_down = ml_pred.get("prob_down", 1.0 - prob)
            explanation = (
                f"XGBoost chronological model forecast ({signal_type}) — "
                f"Up probability: {prob_up * 100:.1f}%, Down probability: {prob_down * 100:.1f}%. "
                f"Model uses joint FinBERT sentiment factors and market technical indicators."
            )
            risk_warning = "XGBoost model predictions are probabilistic estimates derived from historical walk-forward regimes."
            contributing["ml_probability"] = round(prob, 4)
            contributing["ml_prob_up"] = round(prob_up, 4)
            contributing["ml_prob_down"] = round(prob_down, 4)
            contributing["ml_model_id"] = ml_pred.get("model_id")
            contributing["ml_model_type"] = ml_pred.get("model_type", "XGBoostClassifier")

        # Save to database
        db_sig = TradingSignal(
            stock_id=stock.id,
            signal_date=date_val,
            signal_type=signal_type,
            strategy=strategy,
            confidence=round(conf, 4),
            explanation=explanation,
            contributing_factors=json.dumps(contributing),
            risk_warning=risk_warning,
            created_at=datetime.datetime.utcnow(),
        )
        self.db.add(db_sig)
        self.db.commit()
        self.db.refresh(db_sig)

        return {
            "id": db_sig.id,
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "signal_date": date_val.isoformat(),
            "signal_type": signal_type,
            "strategy": strategy,
            "confidence": round(conf, 4),
            "explanation": explanation,
            "contributing_factors": contributing,
            "risk_warning": risk_warning,
            "created_at": db_sig.created_at.isoformat(),
        }

    def generate_all_signals(self, strategy: str = "rule_based") -> List[Dict[str, Any]]:
        stocks = self.stock_repo.get_all(active_only=True)
        signals = []
        for s in stocks:
            sig = self.generate_signal_for_stock(s.symbol, strategy=strategy)
            if "error" not in sig:
                signals.append(sig)
        return signals
