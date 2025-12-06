"""Database connection management."""
import logging
import time
from typing import Generator
from contextlib import contextmanager

import psycopg2
from psycopg2.extensions import connection as Connection

from app.scraper.config import DBConfig

logger = logging.getLogger(__name__)


def create_connection(config: DBConfig, max_retries: int = 5, retry_delay: float = 5.0) -> Connection:
    """Create database connection with retry logic."""
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(config.dsn)
            conn.set_client_encoding('UTF8')
            conn.autocommit = True
            logger.info("Database connection established (UTF-8)")
            return conn
        except psycopg2.Error as e:
            logger.warning(f"DB connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    raise ConnectionError(f"Failed to connect to database after {max_retries} attempts")


@contextmanager
def get_cursor(conn: Connection) -> Generator:
    """Context manager for database cursor."""
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()

