#!/usr/bin/env python3
"""Main entry point for trend.az scraper."""
import argparse
import logging

from app.scraper.config import ScraperConfig, DBConfig
from app.scraper.pipeline_trend import TrendScraperPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main function to run the trend.az scraper."""
    parser = argparse.ArgumentParser(description="Scrape news from trend.az (az.trend.az).")
    
    parser.add_argument(
        "--mode",
        type=str,
        default="ajax",
        choices=["rss", "ajax"],
        help="Scraping mode: 'rss' (recent ~25 via RSS), 'ajax' (full pagination)."
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages to scrape in ajax mode (default: all)."
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)."
    )
    
    args = parser.parse_args()
    
    # Update logging level
    logging.getLogger().setLevel(args.log_level)
    logger.info(f"Starting trend.az scraper in '{args.mode}' mode")
    
    scraper_config = ScraperConfig()
    db_config = DBConfig()
    
    pipeline = TrendScraperPipeline(scraper_config, db_config)
    
    try:
        if args.mode == "rss":
            stats = pipeline.run_from_rss()
        elif args.mode == "ajax":
            stats = pipeline.run_ajax_pagination(args.max_pages)
        else:
            logger.error(f"Unknown mode: {args.mode}")
            return
        
        logger.info(f"Scraping complete: {stats}")
        
    except Exception as e:
        logger.critical(f"Trend.az scraper failed: {e}", exc_info=True)
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
