#!/usr/bin/env python3
"""Main entry point for 1news.az scraper."""
import argparse
import logging

from app.scraper.config import ScraperConfig
from app.scraper.pipeline_onenews import run_onenews_scraper


def setup_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="1news.az scraper")
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Batch size for DB inserts",
    )

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    config = ScraperConfig(batch_size=args.batch_size)
    logger.info("Starting 1news.az scraper")

    try:
        stats = run_onenews_scraper(config)
        logger.info("Scraping complete: %s", stats)
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception:
        logger.exception("Scraping failed")
        raise


if __name__ == "__main__":
    main()
