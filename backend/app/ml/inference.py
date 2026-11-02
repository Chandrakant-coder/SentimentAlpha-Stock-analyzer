import datetime
from typing import List, Dict, Any, Union
import torch
from app.config import settings
from app.core.logging import logger
from app.ml.finbert_loader import finbert_loader, ModelStatus

class FinBERTInferenceEngine:
    """
    Production-grade local batched inference for ProsusAI/finbert.
    """
    def __init__(self):
        self.loader = finbert_loader

    def predict_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Runs batch inference on a list of texts.
        Returns a list of dicts with:
          sentiment_label, positive_probability, negative_probability, neutral_probability,
          sentiment_score, model_name, model_version, inference_timestamp, inference_status
        """
        if not texts:
            return []

        # Clean and sanitize input texts
        sanitized_texts = [t.strip() if (t and isinstance(t, str)) else "" for t in texts]

        # 1. Lightweight mode branch for testing/dev without downloading weights
        if settings.LIGHTWEIGHT_MODE:
            return self._predict_lightweight_heuristics(sanitized_texts)

        # 2. Production FinBERT local model inference
        tokenizer, model = self.loader.load_model()
        results: List[Dict[str, Any]] = []

        batch_size = max(1, settings.FINBERT_BATCH_SIZE)

        for i in range(0, len(sanitized_texts), batch_size):
            chunk = sanitized_texts[i : i + batch_size]
            # Replace empty text with a neutral placeholder so tokenizer doesn't error
            safe_chunk = [t if t else "No financial text provided." for t in chunk]

            try:
                inputs = tokenizer(
                    safe_chunk,
                    padding=True,
                    truncation=True,
                    max_length=settings.FINBERT_MAX_LENGTH,
                    return_tensors="pt",
                )
                inputs = {k: v.to(self.loader.device) for k, v in inputs.items()}

                with torch.inference_mode():
                    outputs = model(**inputs)
                    probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()

                label_indices = {name: idx for idx, name in enumerate(self.loader.labels)}
                pos_idx = label_indices.get("positive", 0)
                neg_idx = label_indices.get("negative", 1)
                neu_idx = label_indices.get("neutral", 2)

                for orig_text, prob_row in zip(chunk, probs):
                    if not orig_text:
                        # Empty article text
                        results.append({
                            "sentiment_label": "neutral",
                            "positive_probability": 0.0,
                            "negative_probability": 0.0,
                            "neutral_probability": 1.0,
                            "sentiment_score": 0.0,
                            "model_name": self.loader.model_name,
                            "model_version": self.loader.version,
                            "inference_timestamp": datetime.datetime.utcnow(),
                            "inference_status": "ready",
                        })
                        continue

                    pos_p = float(prob_row[pos_idx])
                    neg_p = float(prob_row[neg_idx])
                    neu_p = float(prob_row[neu_idx])
                    score = float(pos_p - neg_p)

                    # Determine label
                    max_idx = int(prob_row.argmax())
                    label = self.loader.labels[max_idx]

                    results.append({
                        "sentiment_label": label,
                        "positive_probability": round(pos_p, 4),
                        "negative_probability": round(neg_p, 4),
                        "neutral_probability": round(neu_p, 4),
                        "sentiment_score": round(score, 4),
                        "model_name": self.loader.model_name,
                        "model_version": self.loader.version,
                        "inference_timestamp": datetime.datetime.utcnow(),
                        "inference_status": "ready",
                    })

            except Exception as e:
                logger.error(f"Inference error in batch {i}: {e}", exc_info=True)
                for _ in chunk:
                    results.append({
                        "sentiment_label": "failed",
                        "positive_probability": 0.0,
                        "negative_probability": 0.0,
                        "neutral_probability": 0.0,
                        "sentiment_score": 0.0,
                        "model_name": self.loader.model_name,
                        "model_version": self.loader.version,
                        "inference_timestamp": datetime.datetime.utcnow(),
                        "inference_status": "failed",
                        "error_message": str(e),
                    })

        return results

    def _predict_lightweight_heuristics(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Deterministic keyword-based sentiment for tests without downloading weights"""
        bullish_words = {"profit", "surge", "gain", "growth", "high", "upgrade", "beat", "positive", "strong", "bull", "jump", "record", "expansion", "dividend"}
        bearish_words = {"loss", "drop", "fall", "decline", "low", "downgrade", "miss", "negative", "weak", "bear", "slump", "fraud", "probe", "investigation"}

        results = []
        for text in texts:
            if not text:
                results.append({
                    "sentiment_label": "neutral",
                    "positive_probability": 0.0,
                    "negative_probability": 0.0,
                    "neutral_probability": 1.0,
                    "sentiment_score": 0.0,
                    "model_name": "ProsusAI/finbert-lightweight-sim",
                    "model_version": "1.0.0-test",
                    "inference_timestamp": datetime.datetime.utcnow(),
                    "inference_status": "ready",
                })
                continue

            words = set(text.lower().split())
            pos_matches = len(words.intersection(bullish_words))
            neg_matches = len(words.intersection(bearish_words))

            if pos_matches > neg_matches:
                pos_p, neg_p, neu_p = 0.82, 0.08, 0.10
                label = "positive"
            elif neg_matches > pos_matches:
                pos_p, neg_p, neu_p = 0.08, 0.82, 0.10
                label = "negative"
            else:
                pos_p, neg_p, neu_p = 0.15, 0.15, 0.70
                label = "neutral"

            score = pos_p - neg_p
            results.append({
                "sentiment_label": label,
                "positive_probability": pos_p,
                "negative_probability": neg_p,
                "neutral_probability": neu_p,
                "sentiment_score": score,
                "model_name": "ProsusAI/finbert-lightweight-sim",
                "model_version": "1.0.0-test",
                "inference_timestamp": datetime.datetime.utcnow(),
                "inference_status": "ready",
            })
        return results

inference_engine = FinBERTInferenceEngine()
