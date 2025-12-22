"""HTML parsers for report.az pages."""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple

from bs4 import BeautifulSoup, Tag

from src.scrapers.config import AZ_MONTHS
from src.database.models import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class NewsListItem:
    """Item from archive listing page."""
    link: str
    title: str
    pub_date: Optional[datetime]


def parse_az_date(date_str: str, time_str: str) -> Optional[datetime]:
    """
    Parse Azerbaijani date format.
    Example: "01 dekabr, 2024" + "23:43" -> datetime
    """
    try:
        # "01 dekabr, 2024"
        date_str = date_str.strip()
        match = re.match(r'(\d{1,2})\s+([a-zA-Zə]+),?\s*(\d{4})', date_str)
        if not match:
            return None
        
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        
        month = AZ_MONTHS.get(month_name)
        if not month:
            logger.debug(f"Unknown month: {month_name}")
            return None
        
        # "23:43"
        time_str = time_str.strip()
        time_parts = time_str.split(':')
        if len(time_parts) != 2:
            return datetime(year, month, day)
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        return datetime(year, month, day, hour, minute)
    except (ValueError, IndexError) as e:
        logger.debug(f"Date parse error: {date_str} {time_str} - {e}")
        return None


def parse_archive_page(html: str, base_url: str) -> List[NewsListItem]:
    """
    Parse archive listing page.
    Returns list of news items with links, titles, and dates.
    """
    soup = BeautifulSoup(html, "lxml")
    items: List[NewsListItem] = []
    
    # Новая структура: div.index-post-block содержит a.news__item
    news_blocks = soup.find_all('div', class_='index-post-block')
    
    for block in news_blocks:
        try:
            link_tag = block.find('a', class_='news__item')
            if not link_tag or not isinstance(link_tag, Tag):
                continue
            
            href = link_tag.get('href')
            if not href:
                continue
            
            # Формируем полный URL
            link = f"{base_url}{href}" if href.startswith('/') else href
            
            # Заголовок
            title_tag = block.find('h2', class_='news__title')
            title = title_tag.get_text(strip=True) if title_tag else ""
            
            # Дата
            date_list = block.find('ul', class_='news__date')
            pub_date = None
            if date_list:
                li_tags = date_list.find_all('li')
                if len(li_tags) >= 2:
                    date_str = li_tags[0].get_text(strip=True)
                    time_str = li_tags[1].get_text(strip=True)
                    pub_date = parse_az_date(date_str, time_str)
            
            if link and title:
                items.append(NewsListItem(link=link, title=title, pub_date=pub_date))
                
        except Exception as e:
            logger.debug(f"Error parsing news block: {e}")
            continue
    
    # Fallback: старый метод для совместимости со старыми страницами
    if not items:
        items = _parse_archive_page_legacy(soup, base_url)
    
    return items


def _parse_archive_page_legacy(soup: BeautifulSoup, base_url: str) -> List[NewsListItem]:
    """Legacy parser for older archive pages."""
    items: List[NewsListItem] = []
    date_pattern = re.compile(r'(\d{1,2}\s+[^\d,]+,\s*\d{4})\s+(\d{1,2}:\d{2})')
    
    for a in soup.find_all('a', string=date_pattern):
        try:
            href = a.get('href')
            if not href:
                continue
            
            link = f"{base_url}{href}" if href.startswith('/') else href
            text = a.get_text(separator=" ").strip()
            
            match = date_pattern.search(text)
            if match:
                date_str = match.group(1)
                time_str = match.group(2)
                pub_date = parse_az_date(date_str, time_str)
                
                # Извлекаем заголовок из текста до даты
                title = text[:match.start()].strip(" –-:")
            else:
                pub_date = None
                title = text
            
            if link and title:
                items.append(NewsListItem(link=link, title=title, pub_date=pub_date))
                
        except Exception as e:
            logger.debug(f"Legacy parse error: {e}")
            continue
    
    return items


def parse_article_page(html: str) -> Optional[Tuple[str, str]]:
    """
    Parse article page.
    Returns (title, content) or None on failure.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Заголовок
    title_tag = soup.find('h1', class_='section-title') or soup.find('h1')
    if not title_tag:
        logger.debug("No title found in article")
        return None
    title = title_tag.get_text(strip=True)
    
    # Контент
    content_div = soup.find('div', class_='news-detail__desc')
    if not content_div:
        # Fallback: собираем все параграфы
        content_paragraphs = _extract_paragraphs_fallback(soup)
    else:
        content_paragraphs = []
        for p in content_div.find_all('p'):
            text = p.get_text(strip=True)
            if text and not _is_junk_paragraph(text):
                content_paragraphs.append(text)
    
    content = "\n\n".join(content_paragraphs)
    
    if not content:
        logger.debug(f"No content found for article: {title}")
        return None
    
    return title, content


def _extract_paragraphs_fallback(soup: BeautifulSoup) -> List[str]:
    """Fallback paragraph extraction."""
    paragraphs = []
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if text and not _is_junk_paragraph(text):
            paragraphs.append(text)
    return paragraphs


def _is_junk_paragraph(text: str) -> bool:
    """Check if paragraph is junk (social links, etc)."""
    junk_markers = [
        'Telegram', 'Facebook', 'Twitter', 'WhatsApp',
        'Ən son xəbər', 'ən son xəbər',
        'Mənbə:', 'Источник:', 'Source:',
        'Sosial şəbəkələrdə paylaşın'
    ]
    return any(marker in text for marker in junk_markers)

