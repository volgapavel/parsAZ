"""Main scraping pipeline."""
import logging
from datetime import date, timedelta
from typing import Generator, Optional, List

from psycopg2.extensions import connection as Connection

from src.scrapers.config import ScraperConfig
from src.scrapers.client import HttpClient
from src.scrapers.parsers.base import parse_archive_page, parse_article_page, NewsListItem
from src.database.models import NewsArticle
from src.database import repository

logger = logging.getLogger(__name__)


class ScrapingPipeline:
    """Main scraping orchestrator."""
    
    def __init__(self, config: ScraperConfig, conn: Connection):
        self.config = config
        self.conn = conn
        self.client = HttpClient(config)
        self.stats = {"processed": 0, "inserted": 0, "skipped": 0, "errors": 0}
    
    def run(self) -> dict:
        """Run full scraping pipeline."""
        logger.info(f"Starting scrape from {self.config.start_date} to {self.config.end_date}")
        
        try:
            for current_date in self._date_range():
                self._process_day(current_date)
                self.client.random_delay(self.config.day_delay_min, self.config.day_delay_max)
        finally:
            self.client.close()
        
        logger.info(f"Scraping completed. Stats: {self.stats}")
        return self.stats
    
    def _date_range(self) -> Generator[date, None, None]:
        """Generate dates from start to end."""
        current = self.config.start_date
        end = self.config.end_date or date.today()
        while current <= end:
            yield current
            current += timedelta(days=1)
    
    def _process_day(self, current_date: date) -> None:
        """Process single day archive."""
        archive_url = f"{self.config.base_url}/archive/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}"
        
        html = self.client.fetch(archive_url, allow_404=True)
        if not html:
            logger.debug(f"No archive for {current_date}")
            return
        
        news_items = parse_archive_page(html, self.config.base_url)
        if not news_items:
            logger.debug(f"No news found for {current_date}")
            return
        
        logger.info(f"Processing {current_date}: {len(news_items)} items")
        
        batch: List[NewsArticle] = []
        
        for item in news_items:
            article = self._process_article(item)
            if article:
                batch.append(article)
                
                # Flush batch if full
                if len(batch) >= self.config.batch_size:
                    self._flush_batch(batch)
                    batch = []
            
            self.client.random_delay()
        
        # Flush remaining
        if batch:
            self._flush_batch(batch)
    
    def _process_article(self, item: NewsListItem) -> Optional[NewsArticle]:
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
        result = parse_article_page(html)
        if not result:
            self.stats["errors"] += 1
            logger.warning(f"Failed to parse article: {item.link}")
            return None
        
        title, content = result
        
        # Use parsed title if available, fallback to listing title
        return NewsArticle(
            link=item.link,
            title=title or item.title,
            content=content,
            pub_date=item.pub_date
        )
    
    def _flush_batch(self, batch: List[NewsArticle]) -> None:
        """Flush batch to database."""
        count = repository.insert_news_batch(self.conn, batch)
        self.stats["inserted"] += count
        logger.debug(f"Flushed batch of {len(batch)} articles")


def run_scraper(config: Optional[ScraperConfig] = None) -> dict:
    """Entry point for scraper."""
    from src.scrapers.config import DBConfig
    from src.database.connection import create_connection
    
    config = config or ScraperConfig()
    db_config = DBConfig()
    
    conn = create_connection(db_config)
    repository.init_schema(conn)
    
    try:
        pipeline = ScrapingPipeline(config, conn)
        return pipeline.run()
    finally:
        conn.close()

