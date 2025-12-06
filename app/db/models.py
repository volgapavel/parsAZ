"""Data models for news articles."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsArticle:
    """News article data model."""
    link: str
    title: str
    content: str
    pub_date: datetime | None = None

    def to_tuple(self) -> tuple[str, datetime | None, str, str]:
        """Convert to tuple for database insertion."""
        return (self.link, self.pub_date, self.title, self.content)

