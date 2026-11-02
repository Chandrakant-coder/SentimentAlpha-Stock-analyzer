import datetime
from app.database.models import Stock, Article, SentimentResult, PipelineJob
from app.database.repositories import StockRepository, ArticleRepository, SentimentRepository, JobRepository

def test_stock_repository(db):
    repo = StockRepository(db)
    stock = repo.add_or_update(
        symbol="TESTSTOCK",
        ticker="TESTSTOCK.NS",
        company_name="Test Stock Limited",
        sector="Technology",
    )
    assert stock.id is not None
    assert stock.symbol == "TESTSTOCK"

    # Fetch
    fetched = repo.get_by_symbol("TESTSTOCK")
    assert fetched is not None
    assert fetched.company_name == "Test Stock Limited"

def test_article_deduplication(db):
    repo = ArticleRepository(db)
    url = "https://example.com/finance/1"
    fp = "abc123fingerprint"
    dt = datetime.datetime.utcnow()

    # First insert
    art1 = repo.create("Stock rallies 10%", "Good news", url, "ET", dt, fp)
    assert art1 is not None

    # Duplicate insert with same URL
    art2 = repo.create("Different title", "Same URL", url, "ET", dt, "diff_fp")
    assert art2 is None

    # Duplicate insert with same fingerprint
    art3 = repo.create("Stock rallies 10%", "Good news", "https://example.com/finance/2", "ET", dt, fp)
    assert art3 is None

def test_job_repository_lifecycle(db):
    repo = JobRepository(db)
    job = repo.create_job("job_test_1", "sentiment")
    assert job.status == "queued"
    assert job.progress_pct == 0

    # Update to running
    repo.update_job("job_test_1", status="running", progress_pct=50, message="Processing...")
    updated = repo.get_job("job_test_1")
    assert updated.status == "running"
    assert updated.progress_pct == 50

    # Complete
    repo.update_job("job_test_1", status="completed", progress_pct=100)
    completed = repo.get_job("job_test_1")
    assert completed.status == "completed"
    assert completed.completed_at is not None
