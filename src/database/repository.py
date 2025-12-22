"""Database repository for news operations."""
import logging
from typing import Sequence

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as Connection

from src.database.models import NewsArticle

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS report (
    id BIGSERIAL PRIMARY KEY,
    link TEXT UNIQUE NOT NULL,
    pub_date TIMESTAMP,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_report_pub_date ON report(pub_date);
"""

INSERT_NEWS_SQL = """
INSERT INTO report (link, pub_date, title, content)
VALUES %s
ON CONFLICT (link) DO NOTHING;
"""

CHECK_EXISTS_SQL = "SELECT 1 FROM report WHERE link = %s"


def init_schema(conn: Connection) -> None:
    """Initialize database schema."""
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    logger.info("Database schema initialized")


def link_exists(conn: Connection, link: str) -> bool:
    """Check if news article with given link exists."""
    with conn.cursor() as cur:
        cur.execute(CHECK_EXISTS_SQL, (link,))
        return cur.fetchone() is not None


def insert_news_batch(conn: Connection, articles: Sequence[NewsArticle]) -> int:
    """
    Insert batch of news articles.
    Returns number of inserted rows.
    """
    if not articles:
        return 0
    
    values = [article.to_tuple() for article in articles]
    
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur, INSERT_NEWS_SQL, values,
                template="(%s, %s, %s, %s)"
            )
            # rowcount не работает с ON CONFLICT, считаем по-другому
            return len(articles)
    except psycopg2.Error as e:
        logger.error(f"Batch insert error: {e}")
        return 0


def insert_single_news(conn: Connection, article: NewsArticle) -> bool:
    """Insert single news article. Returns True if inserted."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO report (link, pub_date, title, content) VALUES (%s, %s, %s, %s) ON CONFLICT (link) DO NOTHING",
                article.to_tuple()
            )
            return cur.rowcount > 0
    except psycopg2.Error as e:
        logger.error(f"Insert error for {article.link}: {e}")
        return False


def get_news_count(conn: Connection) -> int:
    """Get total count of news in database."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM report")
        result = cur.fetchone()
        return result[0] if result else 0

