#!/usr/bin/env python3
"""Main entry point for report.az news scraper."""
import logging
import argparse
import sys
from datetime import date

# Add current directory and /src to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/src')

from src.scrapers.config import ScraperConfig
from src.scrapers.pipelines.main import run_scraper


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def parse_date(date_str: str) -> date:
    """Parse date string YYYY-MM-DD."""
    return date.fromisoformat(date_str)


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Report.az News Scraper")
    parser.add_argument(
        "--start-date", type=parse_date, default=None,
        help="Start date (YYYY-MM-DD), default: 2014-01-01"
    )
    parser.add_argument(
        "--end-date", type=parse_date, default=None,
        help="End date (YYYY-MM-DD), default: today"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Batch size for DB inserts"
    )
    
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    config = ScraperConfig(
        start_date=args.start_date or date(2014, 1, 1),
        end_date=args.end_date,
        batch_size=args.batch_size
    )
    
    logger.info(f"Starting scraper: {config.start_date} -> {config.end_date}")
    
    try:
        stats = run_scraper(config)
        logger.info(f"Scraping complete: {stats}")
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.exception(f"Scraping failed: {e}")
        raise


if __name__ == "__main__":
    main()

