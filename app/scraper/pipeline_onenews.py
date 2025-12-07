"""Scraping pipeline for 1news.az."""
import logging
from typing import Optional

from psycopg2.extensions import connection as Connection

from app.scraper.client import HttpClient
from app.scraper.config import ScraperConfig
from app.scraper.parsers_1news import (
    parse_listing_page_1news,
    parse_article_page_1news,
    OneNewsListItem,
)
from app.db.models import NewsArticle
from app.db import repository_1news as repository

logger = logging.getLogger(__name__)


class OneNewsPipeline:
    """Scraping pipeline for 1news.az."""

    def __init__(self, config: ScraperConfig, conn: Connection):
        self.config = config
        self.conn = conn
        self.client = HttpClient(config)
        self.base_url = "https://1news.az"
        self.listing_url = f"{self.base_url}/az/news"
        self.stats = {"processed": 0, "inserted": 0, "skipped": 0, "errors": 0}

    def run(self, max_pages: Optional[int] = None) -> dict:
        """Run scraping pipeline."""
        logger.info("Starting 1news.az scraper")

        try:
            html = self.client.fetch(self.listing_url)
            if not html:
                logger.warning("Failed to fetch listing page")
                return self.stats

            news_items = parse_listing_page_1news(html, self.base_url)
            logger.info("Found %d items on listing page", len(news_items))

            batch: list[NewsArticle] = []
            for item in news_items:
                article = self._process_article(item)
                if article:
                    batch.append(article)

                if len(batch) >= self.config.batch_size:
                    self._flush_batch(batch)
                    batch = []

                self.client.random_delay()

            if batch:
                self._flush_batch(batch)

        finally:
            self.client.close()

        logger.info("Scraping completed. Stats: %s", self.stats)
        return self.stats

    def _process_article(self, item: OneNewsListItem) -> NewsArticle | None:
        self.stats["processed"] += 1

        if repository.link_exists(self.conn, item.link):
            self.stats["skipped"] += 1
            return None

        html = self.client.fetch(item.link)
        if not html:
            self.stats["errors"] += 1
            return None

        parsed = parse_article_page_1news(html)
        if not parsed:
            self.stats["errors"] += 1
            logger.warning("Failed to parse article: %s", item.link)
            return None

        title, content, pub_date = parsed
        return NewsArticle(
            link=item.link,
            title=title or item.title or "",
            content=content,
            pub_date=pub_date,
        )

    def _flush_batch(self, batch: list[NewsArticle]) -> None:
        inserted = repository.insert_news_batch(self.conn, batch)
        self.stats["inserted"] += inserted
        logger.debug("Flushed batch of %d articles", len(batch))


def run_onenews_scraper(config: ScraperConfig | None = None) -> dict:
    """Entry point for 1news.az scraper."""
    from app.scraper.config import DBConfig
    from app.db.connection import create_connection

    config = config or ScraperConfig()
    db_config = DBConfig()

    conn = create_connection(db_config)
    repository.init_schema(conn)

    try:
        pipeline = OneNewsPipeline(config, conn)
        return pipeline.run()
    finally:
        conn.close()
