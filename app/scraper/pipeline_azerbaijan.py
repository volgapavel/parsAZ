"""Scraping pipeline for azerbaijan.az."""
import logging

from psycopg2.extensions import connection as Connection

from app.scraper.config import ScraperConfig
from app.scraper.client import HttpClient
from app.scraper.parsers_azerbaijan import (
    parse_news_list_page, 
    parse_article_page_az, 
    get_next_page_url,
    AzNewsListItem
)
from app.db.models import NewsArticle
from app.db import repository_azerbaijan as repository

logger = logging.getLogger(__name__)


class AzerbaijanPipeline:
    """Scraping pipeline for azerbaijan.az."""
    
    def __init__(self, config: ScraperConfig, conn: Connection):
        self.config = config
        self.conn = conn
        self.client = HttpClient(config)
        self.stats = {"processed": 0, "inserted": 0, "skipped": 0, "errors": 0}
        self.base_url = "https://azerbaijan.az"
    
    def run(self, max_pages: int | None = None) -> dict:
        """
        Run scraping pipeline.
        max_pages: limit number of pages to scrape (None = all pages)
        """
        logger.info(f"Starting azerbaijan.az scraper")
        
        try:
            current_url = f"{self.base_url}/news"
            page_num = 1
            
            while current_url:
                if max_pages and page_num > max_pages:
                    logger.info(f"Reached max pages limit: {max_pages}")
                    break
                
                logger.info(f"Processing page {page_num}: {current_url}")
                
                html = self.client.fetch(current_url)
                if not html:
                    logger.warning(f"Failed to fetch page: {current_url}")
                    break
                
                news_items = parse_news_list_page(html, self.base_url)
                if not news_items:
                    logger.info("No more news items found")
                    break
                
                logger.info(f"Found {len(news_items)} items on page {page_num}")
                
                batch: list[NewsArticle] = []
                
                for item in news_items:
                    article = self._process_article(item)
                    if article:
                        batch.append(article)
                        
                        if len(batch) >= self.config.batch_size:
                            self._flush_batch(batch)
                            batch = []
                    
                    self.client.random_delay()
                
                # Flush remaining
                if batch:
                    self._flush_batch(batch)
                
                # Get next page
                current_url = get_next_page_url(html, self.base_url)
                page_num += 1
                
                self.client.random_delay(self.config.day_delay_min, self.config.day_delay_max)
                
        finally:
            self.client.close()
        
        logger.info(f"Scraping completed. Stats: {self.stats}")
        return self.stats
    
    def _process_article(self, item: AzNewsListItem) -> NewsArticle | None:
        """Process single article."""
        self.stats["processed"] += 1
        
        # Check if already exists
        if repository.link_exists(self.conn, item.link):
            self.stats["skipped"] += 1
            return None
        
        # Fetch article page
        html = self.client.fetch(item.link)
        if not html:
            self.stats["errors"] += 1
            return None
        
        # Parse content
        result = parse_article_page_az(html)
        if not result:
            self.stats["errors"] += 1
            logger.warning(f"Failed to parse article: {item.link}")
            return None
        
        title, content, pub_date = result
        
        # Use parsed date if available, fallback to listing date
        return NewsArticle(
            link=item.link,
            title=title or item.title,
            content=content,
            pub_date=pub_date or item.pub_date
        )
    
    def _flush_batch(self, batch: list[NewsArticle]) -> None:
        """Flush batch to database."""
        count = repository.insert_news_batch(self.conn, batch)
        self.stats["inserted"] += count
        logger.debug(f"Flushed batch of {len(batch)} articles")


def run_azerbaijan_scraper(config: ScraperConfig | None = None, max_pages: int | None = None) -> dict:
    """Entry point for azerbaijan.az scraper."""
    from app.scraper.config import DBConfig
    from app.db.connection import create_connection
    
    config = config or ScraperConfig()
    db_config = DBConfig()
    
    conn = create_connection(db_config)
    repository.init_schema(conn)
    
    try:
        pipeline = AzerbaijanPipeline(config, conn)
        return pipeline.run(max_pages=max_pages)
    finally:
        conn.close()


