"""Force re-sync all stocks — overwrites stale/wrong existing rows with correct yfinance data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging import logger
from app.database.engine import SessionLocal
from app.main import init_db
from app.services.price_data import MarketDataService
from app.database.models import Stock

init_db()
db = SessionLocal()
try:
    service = MarketDataService(db)
    stocks = db.query(Stock).filter(Stock.is_active == True).order_by(Stock.symbol).all()
    print(f"Syncing {len(stocks)} stocks...")
    for stock in stocks:
        print(f"  Syncing {stock.symbol} ({stock.ticker})...")
        result = service.sync_symbol(stock.symbol, period="1y")
        print(f"    status={result['status']} latest={result.get('latest_market_date')} fetched={result.get('records_fetched',0)} inserted={result.get('records_inserted',0)} updated={result.get('records_updated',0)} error={result.get('error')}")
    
    # Final verification
    from app.database.models import PriceHistory
    from sqlalchemy import desc
    print("\nFinal state after sync:")
    for stock in db.query(Stock).filter(Stock.is_active == True).order_by(Stock.symbol).all():
        row = db.query(PriceHistory).filter(PriceHistory.stock_id == stock.id).order_by(desc(PriceHistory.date)).first()
        if row:
            adj = f"{row.adj_close:.2f}" if row.adj_close else "None"
            print(f"  {stock.symbol}: {row.date.date()} close={row.close:.2f} adj_close={adj}")
        else:
            print(f"  {stock.symbol}: NO DATA")
finally:
    db.close()
