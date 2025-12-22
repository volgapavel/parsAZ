"""Parsers for trend.az (az.trend.az) news website."""
import logging
import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from app.db.models import NewsArticle

logger = logging.getLogger(__name__)

# Azerbaijani month names
MONTHS_AZ = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5,
    "iyun": 6, "iyul": 7, "avqust": 8, "sentyabr": 9,
    "oktyabr": 10, "noyabr": 11, "dekabr": 12
}


def parse_trend_date(date_text: str) -> Optional[datetime]:
    """
    Parses trend.az date format.
    Examples:
      - "6 Dekabr 2025 15:49 (UTC +04:00)"
      - "15:49 (UTC+04)"
    """
    # Full date format: "6 Dekabr 2025 15:49 (UTC +04:00)"
    full_pattern = re.compile(r'(\d{1,2})\s+(\w+)\s+(\d{4})\s+(\d{1,2}):(\d{2})')
    match = full_pattern.search(date_text)
    if match:
        day = int(match.group(1))
        month_str = match.group(2).lower()
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))
        
        month = MONTHS_AZ.get(month_str)
        if month:
            try:
                return datetime(year, month, day, hour, minute)
            except ValueError:
                logger.warning(f"Invalid date components: {date_text}")
                return None
    
    # Short time format: "15:49 (UTC+04)" - need current date
    time_pattern = re.compile(r'(\d{1,2}):(\d{2})')
    match = time_pattern.search(date_text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        now = datetime.now()
        try:
            return datetime(now.year, now.month, now.day, hour, minute)
        except ValueError:
            return None
    
    return None


def parse_listing_page_trend(html: str, base_url: str = "https://az.trend.az") -> List[NewsArticle]:
    """
    Parses a news listing page from az.trend.az and extracts news metadata.
    Used for initial discovery and RSS-like parsing.
    """
    soup = BeautifulSoup(html, "lxml")
    news_items: List[NewsArticle] = []

    # News list selector: ul.news-list > li > a
    news_list = soup.find('ul', class_='news-list')
    if not news_list:
        logger.debug("No news-list found on page")
        return []

    for li in news_list.find_all('li'):
        link_tag = li.find('a')
        if not link_tag:
            continue

        href = link_tag.get('href')
        if not href:
            continue

        # Already full URL on trend.az
        link = href if href.startswith('http') else base_url + href

        # Title: h4 inside the link
        title_tag = link_tag.find('h4')
        title = title_tag.get_text().strip() if title_tag else "No Title"

        # Date: span.date-time
        date_tag = link_tag.find('span', class_='date-time')
        pub_dt: Optional[datetime] = None
        if date_tag:
            date_str = date_tag.get_text().strip()
            pub_dt = parse_trend_date(date_str)

        if link and title:
            news_items.append(NewsArticle(link=link, pub_date=pub_dt, title=title, content=""))

    return news_items


def parse_article_page_trend(html: str, article_url: str) -> tuple[str, str, Optional[datetime]]:
    """
    Parses an individual news article page from az.trend.az.
    Returns: (content, title, pub_date)
    """
    soup = BeautifulSoup(html, "lxml")
    content_paragraphs: List[str] = []

    # Extract title
    title_tag = soup.find('h1')
    title = title_tag.get_text().strip() if title_tag else ""

    # Extract date from meta tag (more reliable)
    pub_dt: Optional[datetime] = None
    date_meta = soup.find('meta', {'itemprop': 'datePublished'})
    if date_meta and date_meta.get('content'):
        try:
            # Format: 2025-12-06T15:49:00+04:00
            date_str = date_meta['content']
            # Remove timezone for simpler parsing
            date_str = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)
            pub_dt = datetime.fromisoformat(date_str)
        except (ValueError, AttributeError):
            pass

    # Fallback: parse from visible date
    if not pub_dt:
        date_span = soup.find('span', class_='date-time')
        if date_span:
            pub_dt = parse_trend_date(date_span.get_text())

    # Content: div.article-content
    content_div = soup.find('div', class_='article-content')
    if content_div:
        for p in content_div.find_all('p'):
            p_text = p.get_text().strip()
            if not p_text:
                continue
            # Skip service lines
            skip_keywords = [
                'Telegram', 'Facebook', 'Twitter', 'Trend-i buradan',
                'Whatsapp', 'Google News', '@trend', 'trend.az'
            ]
            if any(kw.lower() in p_text.lower() for kw in skip_keywords):
                continue
            content_paragraphs.append(p_text)
    else:
        logger.warning(f"Could not find article-content div for: {article_url}")

    content = "\n\n".join(content_paragraphs)
    return content, title, pub_dt


def extract_article_id_from_url(url: str) -> Optional[int]:
    """
    Extracts numeric article ID from trend.az URL.
    Example: https://az.trend.az/azerbaijan/politics/4126680.html -> 4126680
    """
    match = re.search(r'/(\d+)\.html', url)
    if match:
        return int(match.group(1))
    return None


def build_article_url(article_id: int, base_url: str = "https://az.trend.az") -> str:
    """
    Builds a minimal article URL for checking existence.
    The actual category path doesn't matter for direct ID access.
    We'll follow redirects if needed.
    """
    # Trend.az URLs need category path, but we can try to fetch directly
    # and the server might redirect or return the article
    return f"{base_url}/azerbaijan/politics/{article_id}.html"

