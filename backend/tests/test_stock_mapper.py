from app.services.stock_mapper import stock_mapper, StockEntityMapper

def test_exact_ticker_and_name_match():
    text = "Reliance Industries reported high Q4 EBITDA and Jio added 10 million subscribers."
    matches = stock_mapper.map_text_to_stocks(text)
    symbols = [m["symbol"] for m in matches]
    assert "RELIANCE" in symbols

def test_multiple_stocks_mapping():
    text = "Tata Consultancy Services (TCS) and Infosys announced AI collaboration in cloud banking."
    matches = stock_mapper.map_text_to_stocks(text)
    symbols = {m["symbol"] for m in matches}
    assert "TCS" in symbols
    assert "INFY" in symbols

def test_boundary_protection_no_false_positives():
    # 'ITC' should not match inside words like 'witch' or 'pitch'
    text = "A major glitch occurred in the switchboard causing electricity cutoff."
    matches = stock_mapper.map_text_to_stocks(text)
    symbols = [m["symbol"] for m in matches]
    assert "ITC" not in symbols
    assert "LT" not in symbols

def test_confidence_scoring():
    text = "RELIANCE quarterly profits surge."
    matches = stock_mapper.map_text_to_stocks(text)
    reliance_match = next(m for m in matches if m["symbol"] == "RELIANCE")
    assert reliance_match["confidence"] == 1.0
