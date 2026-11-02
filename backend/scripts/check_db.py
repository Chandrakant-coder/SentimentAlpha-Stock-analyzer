"""Quick DB inspection script."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.engine import SessionLocal
from app.database.models import PriceHistory, MarketDataSync, Stock
from sqlalchemy import func

db = SessionLocal()
try:
    total_prices = db.query(PriceHistory).count()
    stocks_with_prices = db.query(func.count(func.distinct(PriceHistory.stock_id))).scalar()
    syncs = db.query(MarketDataSync).all()
    print(f"Total price rows: {total_prices}")
    print(f"Stocks with prices: {stocks_with_prices}")
    print(f"Sync rows: {len(syncs)}")
    for s in syncs[:5]:
        stock = db.query(Stock).filter(Stock.id == s.stock_id).first()
        print(f"  {stock.symbol if stock else '?'}: status={s.status} latest={s.latest_market_date} last_success={s.last_success_at}")
    # Check adj_close data
    sample = db.query(PriceHistory).filter(PriceHistory.adj_close.isnot(None)).first()
    if sample:
        stock = db.query(Stock).filter(Stock.id == sample.stock_id).first()
        print(f"Sample row: {stock.symbol if stock else '?'} date={sample.date} close={sample.close} adj_close={sample.adj_close}")
        diff = sample.close - sample.adj_close if sample.adj_close else 0
        print(f"  Diff (close - adj_close): {diff:.4f}")
        if abs(diff) < 0.001:
            print("  NOTE: close == adj_close -- data was ingested with old auto_adjust=True OR migration copied close->adj_close")
            print("  A re-sync will fetch unadjusted close and correct adj_close separately")
    else:
        print("No rows with adj_close populated yet")
    # Show latest row per stock
    print("\nLatest price per symbol (from PriceHistory):")
    from sqlalchemy import desc
    for stock in db.query(Stock).filter(Stock.is_active == True).order_by(Stock.symbol).all():
        row = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).order_by(desc(PriceHistory.date)).first()
        if row:
            print(f"  {stock.symbol}: {row.date.date()} close={row.close:.2f} adj_close={row.adj_close}")
finally:
    db.close()
