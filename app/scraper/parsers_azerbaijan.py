"""HTML parsers for azerbaijan.az pages."""
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from app.db.models import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class AzNewsListItem:
    """Item from news listing page."""
    link: str
    title: str
    pub_date: datetime | None


def parse_az_date_dmy(date_str: str) -> datetime | None:
    """Parse date in DD.MM.YYYY format."""
    try:
        date_str = date_str.strip()
        return datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        return None


def parse_az_date_ymd(date_str: str) -> datetime | None:
    """Parse date in YYYY-MM-DD format."""
    try:
        date_str = date_str.strip()
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def parse_news_list_page(html: str, base_url: str) -> list[AzNewsListItem]:
    """
    Parse news listing page from azerbaijan.az.
    Returns list of news items with links, titles, and dates.
    """
    soup = BeautifulSoup(html, "lxml")
    items: list[AzNewsListItem] = []
    
    # Новости в div.other-news-container
    news_blocks = soup.find_all('div', class_='other-news-container')
    
    for block in news_blocks:
        try:
            link_tag = block.find('a')
            if not link_tag or not isinstance(link_tag, Tag):
                continue
            
            href = link_tag.get('href')
            if not href or not href.startswith('/news/'):
                continue
            
            # Формируем полный URL
            link = f"{base_url}{href}"
            
            # Заголовок
            title_div = block.find('div', class_='other-news-title')
            if title_div:
                p_tag = title_div.find('p')
                title = p_tag.get_text(strip=True) if p_tag else ""
            else:
                title = ""
            
            # Дата
            date_div = block.find('div', class_='news-date-index')
            pub_date = None
            if date_div:
                date_str = date_div.get_text(strip=True)
                pub_date = parse_az_date_dmy(date_str)
            
            if link and title:
                items.append(AzNewsListItem(link=link, title=title, pub_date=pub_date))
                
        except Exception as e:
            logger.debug(f"Error parsing news block: {e}")
            continue
    
    return items


def get_next_page_url(html: str, base_url: str) -> str | None:
    """Get next page URL from pagination."""
    soup = BeautifulSoup(html, "lxml")
    
    pagination = soup.find('ul', class_='pagination')
    if not pagination:
        return None
    
    next_li = pagination.find('li', class_='next')
    if not next_li or 'disabled' in next_li.get('class', []):
        return None
    
    next_link = next_li.find('a')
    if next_link and next_link.get('href'):
        href = next_link.get('href')
        return f"{base_url}{href}" if href.startswith('/') else href
    
    return None


def parse_article_page_az(html: str) -> tuple[str, str, datetime | None] | None:
    """
    Parse article page from azerbaijan.az.
    Returns (title, content, pub_date) or None on failure.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Заголовок
    title_div = soup.find('div', class_='news-view-title')
    if not title_div:
        logger.debug("No title found in article")
        return None
    
    p_tag = title_div.find('p')
    title = p_tag.get_text(strip=True) if p_tag else ""
    
    if not title:
        return None
    
    # Контент
    content_div = soup.find('div', class_='news-view-body')
    content_paragraphs = []
    
    if content_div:
        for p in content_div.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                content_paragraphs.append(text)
    
    content = "\n\n".join(content_paragraphs)
    
    if not content:
        logger.debug(f"No content found for article: {title}")
        return None
    
    # Дата - ищем после news-view-body
    pub_date = None
    container = soup.find('div', class_='news-view-container-left')
    if container:
        # Дата обычно в последнем div внутри контейнера
        divs = container.find_all('div', recursive=False)
        for div in reversed(divs):
            if not div.get('class'):  # div без класса - скорее всего дата
                date_text = div.get_text(strip=True)
                pub_date = parse_az_date_ymd(date_text)
                if pub_date:
                    break
    
    return title, content, pub_date


