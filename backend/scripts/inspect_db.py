"""Inspect DB schema and confirm all required columns exist."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.engine import engine
from sqlalchemy import inspect as sa_inspect

insp = sa_inspect(engine)
tables = insp.get_table_names()
print("Tables:", tables)

if "price_history" in tables:
    cols = {c["name"] for c in insp.get_columns("price_history")}
    print("price_history columns:", sorted(cols))
    required = {"adj_close", "close", "open", "high", "low", "volume", "ma_20", "ma_50", "rsi_14"}
    missing = required - cols
    if missing:
        print("MISSING columns:", missing)
    else:
        print("All required columns present OK")

if "market_data_syncs" in tables:
    cols2 = {c["name"] for c in insp.get_columns("market_data_syncs")}
    print("market_data_syncs columns:", sorted(cols2))
else:
    print("market_data_syncs table MISSING - needs migration")
