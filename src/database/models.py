"""Data models for news articles."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple


@dataclass
class NewsArticle:
    """News article data model."""
    link: str
    title: str
    content: str
    pub_date: Optional[datetime] = None

    def to_tuple(self) -> Tuple[str, Optional[datetime], str, str]:
        """Convert to tuple for database insertion."""
        return (self.link, self.pub_date, self.title, self.content)

