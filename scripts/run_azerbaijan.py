#!/usr/bin/env python3
"""Main entry point for azerbaijan.az news scraper."""

import logging
import argparse

from app.scraper.config import ScraperConfig
from app.scraper.pipeline_azerbaijan import run_azerbaijan_scraper


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Azerbaijan.az News Scraper")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages to scrape (default: all)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50, help="Batch size for DB inserts"
    )

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    config = ScraperConfig(batch_size=args.batch_size)

    logger.info(f"Starting azerbaijan.az scraper (max_pages={args.max_pages})")

    try:
        stats = run_azerbaijan_scraper(config, max_pages=args.max_pages)
        logger.info(f"Scraping complete: {stats}")
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.exception(f"Scraping failed: {e}")
        raise


if __name__ == "__main__":
    main()
