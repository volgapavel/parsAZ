"""Scraping pipeline for trend.az (az.trend.az)."""
import logging
import re
from typing import Dict, Optional, List

from app.db.connection import create_connection
from app.db.repository_trend import TrendNewsRepository
from app.db.models import NewsArticle
from app.scraper.client import HttpClient
from app.scraper.config import ScraperConfig, DBConfig
from app.scraper.parsers_trend import (
    parse_listing_page_trend,
    parse_article_page_trend,
)

logger = logging.getLogger(__name__)


class TrendScraperPipeline:
    """Orchestrates the scraping and data storage process for trend.az."""

    def __init__(self, scraper_config: ScraperConfig, db_config: DBConfig):
        self.scraper_config = scraper_config
        self.db_config = db_config
        self.http_client = HttpClient(scraper_config)
        self.db_conn = create_connection(db_config)
        self.news_repo = TrendNewsRepository(self.db_conn)
        self.news_repo.initialize_schema()
        self.base_url = "https://az.trend.az"

    def _extract_next_date(self, html: str) -> Optional[int]:
        """Extract next pagination date from AJAX response."""
        match = re.search(r'currentNewsList\.date\s*=\s*(\d+)', html)
        if match:
            return int(match.group(1))
        return None

    def run_ajax_pagination(self, max_pages: Optional[int] = None) -> Dict[str, int]:
        """
        Run scraper using AJAX pagination - the most efficient method.
        
        Args:
            max_pages: Maximum number of pages to scrape (None = all)
        """
        logger.info(f"Starting trend.az AJAX scraper (max_pages={max_pages})")
        stats = {'processed': 0, 'inserted': 0, 'skipped': 0, 'errors': 0, 'pages': 0}
        
        current_date: Optional[int] = None  # Start with no date (first page)
        consecutive_empty = 0
        max_consecutive_empty = 3
        
        while True:
            stats['pages'] += 1
            
            # Build URL
            if current_date:
                url = f"{self.base_url}/latest/?ajax=1&date={current_date}"
            else:
                url = f"{self.base_url}/latest/"
            
            logger.info(f"Fetching page {stats['pages']}: {url}")
            self.http_client.random_delay(min_sec=1.5, max_sec=3.0)
            
            html = self.http_client.fetch(url)
            if not html:
                logger.warning(f"Failed to fetch page {stats['pages']}")
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    logger.info("Too many empty pages, stopping")
                    break
                continue
            
            consecutive_empty = 0
            
            # Parse news from page
            news_meta_list = parse_listing_page_trend(html, self.base_url)
            
            if not news_meta_list:
                logger.info(f"No news found on page {stats['pages']}, stopping")
                break
            
            logger.info(f"Found {len(news_meta_list)} articles on page {stats['pages']}")
            
            # Process articles
            batch_to_insert: List[NewsArticle] = []
            
            for news_meta in news_meta_list:
                stats['processed'] += 1
                
                # Check if already exists
                if self.news_repo.link_exists(news_meta.link):
                    stats['skipped'] += 1
                    continue
                
                self.http_client.random_delay(min_sec=0.8, max_sec=1.5)
                article_html = self.http_client.fetch(news_meta.link)
                
                if article_html is None:
                    logger.warning(f"Failed to fetch: {news_meta.link}")
                    stats['errors'] += 1
                    continue
                
                content, title, pub_dt = parse_article_page_trend(article_html, news_meta.link)
                
                if not title:
                    title = news_meta.title
                if not pub_dt:
                    pub_dt = news_meta.pub_date
                
                news_meta.content = content
                news_meta.title = title
                news_meta.pub_date = pub_dt
                
                batch_to_insert.append(news_meta)
                
                if len(batch_to_insert) >= self.scraper_config.batch_size:
                    inserted = self.news_repo.insert_news_batch(batch_to_insert)
                    stats['inserted'] += inserted
                    logger.info(f"Batch: {inserted}/{len(batch_to_insert)} inserted (total: {stats['inserted']})")
                    batch_to_insert = []
            
            # Insert remaining
            if batch_to_insert:
                inserted = self.news_repo.insert_news_batch(batch_to_insert)
                stats['inserted'] += inserted
                logger.info(f"Batch: {inserted}/{len(batch_to_insert)} inserted (total: {stats['inserted']})")
            
            # Get next page date
            next_date = self._extract_next_date(html)
            if not next_date or next_date == current_date:
                logger.info("No more pages (no next date)")
                break
            
            current_date = next_date
            
            # Check max pages limit
            if max_pages and stats['pages'] >= max_pages:
                logger.info(f"Reached max pages limit: {max_pages}")
                break
        
        logger.info(f"AJAX scraping completed. Stats: {stats}")
        return stats

    def run_from_rss(self) -> Dict[str, int]:
        """
        Run scraper using RSS feed for recent news.
        Quick method for getting latest ~25 articles.
        """
        import xml.etree.ElementTree as ET
        
        logger.info("Starting trend.az RSS scraper")
        stats = {'processed': 0, 'inserted': 0, 'skipped': 0, 'errors': 0}
        
        rss_url = f"{self.base_url}/feeds/index.rss"
        xml_content = self.http_client.fetch(rss_url)
        
        if not xml_content:
            logger.error("Failed to fetch RSS feed")
            return stats
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse RSS: {e}")
            return stats
        
        batch_to_insert: List[NewsArticle] = []
        
        for item in root.findall('.//item'):
            stats['processed'] += 1
            
            link_elem = item.find('link')
            title_elem = item.find('title')
            pub_date_elem = item.find('pubDate')
            
            if link_elem is None or link_elem.text is None:
                continue
            
            link = link_elem.text.strip()
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
            
            # Parse RSS date: Sat, 06 Dec 2025 18:22:00 +0400
            pub_dt = None
            if pub_date_elem is not None and pub_date_elem.text:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_dt = parsedate_to_datetime(pub_date_elem.text)
                    pub_dt = pub_dt.replace(tzinfo=None)
                except Exception:
                    pass
            
            # Check if already exists
            if self.news_repo.link_exists(link):
                stats['skipped'] += 1
                continue
            
            self.http_client.random_delay()
            article_html = self.http_client.fetch(link)
            
            if article_html is None:
                stats['errors'] += 1
                continue
            
            content, parsed_title, parsed_dt = parse_article_page_trend(article_html, link)
            
            news_item = NewsArticle(
                link=link,
                pub_date=parsed_dt or pub_dt,
                title=parsed_title or title,
                content=content
            )
            batch_to_insert.append(news_item)
            
            if len(batch_to_insert) >= self.scraper_config.batch_size:
                inserted = self.news_repo.insert_news_batch(batch_to_insert)
                stats['inserted'] += inserted
                batch_to_insert = []
        
        if batch_to_insert:
            inserted = self.news_repo.insert_news_batch(batch_to_insert)
            stats['inserted'] += inserted
        
        logger.info(f"RSS scraping completed. Stats: {stats}")
        return stats

    def close(self) -> None:
        """Close HTTP client and DB connection."""
        self.http_client.close()
        self.db_conn.close()
