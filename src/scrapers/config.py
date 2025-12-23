"""Configuration for scraper."""
import os
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict


@dataclass
class DBConfig:
    """Database connection configuration."""
    host: str = os.getenv('DB_HOST', 'db')
    port: int = int(os.getenv('DB_PORT', '5432'))
    name: str = os.getenv('DB_NAME', 'newsdb')
    user: str = os.getenv('DB_USER', 'myuser')
    password: str = os.getenv('DB_PASSWORD', 'mypass')

    @property
    def dsn(self) -> str:
        return f"host={self.host} port={self.port} dbname={self.name} user={self.user} password={self.password}"


@dataclass
class ScraperConfig:
    """Scraper configuration."""
    base_url: str = "https://report.az"
    start_date: date = date(2014, 1, 1)
    end_date: Optional[date] = None  # None = today
    request_timeout: int = 15
    retry_count: int = 3
    retry_delay: float = 5.0
    min_delay: float = 1.0
    max_delay: float = 3.0
    day_delay_min: float = 2.0
    day_delay_max: float = 5.0
    batch_size: int = 50
    user_agent: str = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"

    def __post_init__(self) -> None:
        if self.end_date is None:
            self.end_date = date.today()


# Месяцы на азербайджанском
AZ_MONTHS: Dict[str, int] = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5,
    "iyun": 6, "iyul": 7, "avqust": 8, "sentyabr": 9,
    "oktyabr": 10, "noyabr": 11, "dekabr": 12
}

