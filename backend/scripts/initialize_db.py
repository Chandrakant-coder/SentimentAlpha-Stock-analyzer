import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import init_db
from app.core.logging import logger

if __name__ == "__main__":
    logger.info("Running manual database initialization...")
    init_db()
    logger.info("Database initialized successfully.")
