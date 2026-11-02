from app.ml.inference import inference_engine

def test_score_calculation_formula():
    results = inference_engine.predict_batch([
        "Record breaking profit and massive quarterly revenue growth announced.",
        "Devastating loss and severe fraud investigation triggered by regulators.",
    ])
    assert len(results) == 2

    # Score must strictly equal positive_probability - negative_probability
    for r in results:
        expected_score = round(r["positive_probability"] - r["negative_probability"], 4)
        assert round(r["sentiment_score"], 4) == expected_score
        assert r["positive_probability"] >= 0.0
        assert r["negative_probability"] >= 0.0
        assert r["neutral_probability"] >= 0.0

def test_empty_article_handling():
    results = inference_engine.predict_batch(["", None, "   "])
    assert len(results) == 3
    for r in results:
        assert r["inference_status"] == "ready"
        assert r["sentiment_score"] == 0.0
        assert r["neutral_probability"] == 1.0

def test_sentiment_direction():
    bullish = inference_engine.predict_batch(["Massive surge in net profits, dividend declared."])[0]
    assert bullish["sentiment_score"] > 0
    assert bullish["sentiment_label"] == "positive"

    bearish = inference_engine.predict_batch(["Catastrophic losses, heavy debt downgrade and credit default."])[0]
    assert bearish["sentiment_score"] < 0
    assert bearish["sentiment_label"] == "negative"
