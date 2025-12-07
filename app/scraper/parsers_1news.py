"""HTML parsers for 1news.az pages."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from app.db.models import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class OneNewsListItem:
    """Item from 1news.az listing page."""

    link: str
    title: str | None = None


_DATE_RE = re.compile(r"(\d{2}):(\d{2})\s*-\s*(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})")


def _normalize_link(href: str, base_url: str) -> str:
    return f"{base_url}{href}" if href.startswith("/") else href


def _extract_title_from_holder(holder: Tag) -> str:
    title_tag = holder.find("h3", class_="title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        if title:
            return title

    link_tag = holder.find("a")
    if link_tag:
        aria_label = link_tag.get("aria-label")
        if aria_label:
            return aria_label.strip()
        text = link_tag.get_text(strip=True)
        if text:
            return text

    return ""


def parse_listing_page_1news(html: str, base_url: str) -> list[OneNewsListItem]:
    """Parse listing page and return unique news items."""

    soup = BeautifulSoup(html, "lxml")
    items: dict[str, OneNewsListItem] = {}

    # Main cards
    for holder in soup.select("div.newsItemHolder"):
        link_tag = holder.find("a", href=re.compile(r"^/az/news/"))
        if not link_tag:
            continue

        href = link_tag.get("href")
        if not href:
            continue

        link = _normalize_link(href, base_url)
        title = _extract_title_from_holder(holder) or None

        items.setdefault(link, OneNewsListItem(link=link, title=title))

    # Fallback: capture any direct links to news pages
    for link_tag in soup.find_all("a", href=re.compile(r"^/az/news/")):
        href = link_tag.get("href")
        if not href:
            continue
        link = _normalize_link(href, base_url)
        if link in items:
            continue

        title = link_tag.get_text(strip=True) or None
        items[link] = OneNewsListItem(link=link, title=title)

    return list(items.values())


def parse_article_page_1news(html: str) -> tuple[str, str, datetime | None] | None:
    """Parse 1news.az article page."""

    soup = BeautifulSoup(html, "lxml")
    article = soup.find("article", class_="mainArticle")
    if not article:
        logger.debug("mainArticle not found")
        return None

    title_tag = article.find("h1", class_="title") or article.find("h1")
    if not title_tag:
        logger.debug("No title tag found")
        return None

    title = title_tag.get_text(strip=True)

    content_container = article.find("div", class_="content") or article
    paragraphs = []
    for p in content_container.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    content = "\n\n".join(paragraphs)
    if not content:
        logger.debug("No content paragraphs found")
        return None

    pub_date = _parse_date(article.find("span", class_="date"))

    return title, content, pub_date


def _parse_date(date_tag: Tag | None) -> datetime | None:
    if not date_tag:
        return None

    date_text = date_tag.get_text(" ", strip=True)
    match = _DATE_RE.search(date_text)
    if not match:
        return None

    try:
        hour, minute, day, month, year = map(int, match.groups())
        return datetime(year, month, day, hour, minute)
    except ValueError:
        logger.debug("Failed to parse date: %s", date_text)
        return None
