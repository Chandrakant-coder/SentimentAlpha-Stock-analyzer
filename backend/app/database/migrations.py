"""Lightweight SQLite-safe migrations. Never drops the database."""

from sqlalchemy import inspect, text
from app.core.logging import logger


def apply_sqlite_migrations(engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "price_history" not in tables:
        return

    cols = {c["name"] for c in inspector.get_columns("price_history")}
    with engine.begin() as conn:
        if "adj_close" not in cols:
            logger.info("Migrating price_history: add adj_close column")
            conn.execute(text("ALTER TABLE price_history ADD COLUMN adj_close FLOAT"))
            # Existing rows were ingested with yfinance auto_adjust=True, so
            # close already equalled adjusted close. Copy until the next sync
            # overwrites close with unadjusted OHLC and adj_close separately.
            conn.execute(text("UPDATE price_history SET adj_close = close WHERE adj_close IS NULL"))

        # Collapse duplicate calendar dates (timezone/time-of-day variants)
        # then normalize remaining timestamps to midnight.
        conn.execute(
            text(
                """
                DELETE FROM price_history
                WHERE id NOT IN (
                    SELECT MIN(id) FROM price_history GROUP BY stock_id, date(date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE price_history
                SET date = datetime(strftime('%Y-%m-%d', date) || ' 00:00:00')
                """
            )
        )
    logger.info("SQLite market-data migrations applied.")
