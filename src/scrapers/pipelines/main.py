from src.scrapers.pipelines.base import ScrapingPipeline
from src.database.connection import create_connection
from src.scrapers.config import DBConfig, ScraperConfig

def run_scraper(config: ScraperConfig):
    db_config = DBConfig()
    conn = create_connection(db_config)
    pipeline = ScrapingPipeline(config, conn)
    return pipeline.run()
