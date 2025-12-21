"""HTTP client with retry logic and rate limiting."""
import logging
import time
import random
from typing import Callable, Optional

import requests
from requests import Session, Response

from app.scraper.config import ScraperConfig

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP client with built-in retry and rate limiting."""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = self._create_session()
    
    def _create_session(self) -> Session:
        """Create configured requests session."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "az,ru;q=0.9,en;q=0.8",
        })
        return session
    
    def fetch(self, url: str, allow_404: bool = False) -> Optional[str]:
        """
        Fetch URL content with retry logic.
        Returns HTML content or None on failure.
        """
        for attempt in range(self.config.retry_count):
            try:
                resp = self.session.get(url, timeout=self.config.request_timeout)
                
                if resp.status_code == 404:
                    if allow_404:
                        return None
                    logger.debug(f"404 for {url}")
                    return None
                
                if resp.status_code != 200:
                    logger.warning(f"HTTP {resp.status_code} for {url}")
                    if attempt < self.config.retry_count - 1:
                        time.sleep(self.config.retry_delay)
                        continue
                    return None
                
                # Явно указываем UTF-8 для азербайджанских символов (ə, ş, ç, ı, ö, ü, ğ)
                resp.encoding = 'utf-8'
                return resp.text
                
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.config.retry_count}): {url} - {e}")
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))  # exponential backoff
                    continue
                return None
        
        return None
    
    def random_delay(self, min_sec: Optional[float] = None, max_sec: Optional[float] = None) -> None:
        """Sleep for random duration."""
        min_sec = min_sec or self.config.min_delay
        max_sec = max_sec or self.config.max_delay
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def close(self) -> None:
        """Close session."""
        self.session.close()

