"""Database repository for trend.az news articles."""
import logging
from typing import List, Optional

import psycopg2.extras
from psycopg2.extensions import connection as Connection

from app.db.connection import get_cursor
from app.db.models import NewsArticle

logger = logging.getLogger(__name__)


class TrendNewsRepository:
    """Handles database operations for news articles from trend.az."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def initialize_schema(self) -> None:
        """Create the trend table if it doesn't exist."""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trend (
                    id SERIAL PRIMARY KEY,
                    link TEXT UNIQUE NOT NULL,
                    pub_date TIMESTAMP,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
        logger.info("Database schema for trend initialized")

    def insert_news_batch(self, news_list: List[NewsArticle]) -> int:
        """Insert a batch of news articles into the trend table, skipping duplicates."""
        if not news_list:
            return 0

        data = [(str(news.link), news.pub_date, news.title, news.content) for news in news_list]

        with get_cursor(self.conn) as cur:
            try:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO trend (link, pub_date, title, content)
                    VALUES %s
                    ON CONFLICT (link) DO NOTHING;
                    """,
                    data,
                    page_size=len(data)
                )
                inserted_count = cur.rowcount
                logger.debug(f"Attempted to insert {len(news_list)} trend.az articles, {inserted_count} new articles inserted.")
                return inserted_count
            except Exception as e:
                logger.error(f"Error during batch insert for trend.az: {e}")
                return 0

    def get_max_article_id(self) -> Optional[int]:
        """Get the maximum article ID already stored in the database."""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT link FROM trend 
                WHERE link ~ '/\\d+\\.html$'
                ORDER BY created_at DESC
                LIMIT 100
            """)
            rows = cur.fetchall()
            if not rows:
                return None
            
            import re
            max_id = 0
            for (link,) in rows:
                match = re.search(r'/(\d+)\.html', link)
                if match:
                    article_id = int(match.group(1))
                    if article_id > max_id:
                        max_id = article_id
            
            return max_id if max_id > 0 else None

    def link_exists(self, link: str) -> bool:
        """Check if a link already exists in the database."""
        with get_cursor(self.conn) as cur:
            cur.execute("SELECT 1 FROM trend WHERE link = %s LIMIT 1", (link,))
            return cur.fetchone() is not None

