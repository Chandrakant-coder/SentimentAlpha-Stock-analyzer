def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "SentimentAlpha"

def test_system_status_endpoint(client):
    res = client.get("/api/system/status")
    assert res.status_code == 200
    data = res.json()
    assert "finbert_status" in data
    assert "database_connected" in data

def test_stocks_endpoint(client, db):
    from app.database.repositories import StockRepository
    repo = StockRepository(db)
    repo.add_or_update("HDFCBANK", "HDFCBANK.NS", "HDFC Bank")

    res = client.get("/api/stocks")
    assert res.status_code == 200
    stocks = res.json()
    symbols = [s["symbol"] for s in stocks]
    assert "HDFCBANK" in symbols

def test_news_endpoint(client, db):
    from app.database.repositories import ArticleRepository
    import datetime
    repo = ArticleRepository(db)
    repo.create(
        "RBI keeps repo rate unchanged",
        "Monetary policy update",
        "https://example.com/rbi",
        "Livemint",
        datetime.datetime.utcnow(),
        "fp_rbi",
    )

    res = client.get("/api/news")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert data["items"][0]["title"] == "RBI keeps repo rate unchanged"
