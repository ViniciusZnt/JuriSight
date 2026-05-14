from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# --- PostgreSQL ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jurisight",
)

# --- Scrapy core ---
BOT_NAME = "jurisight"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"
ROBOTSTXT_OBEY = False
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# --- Throttle e retry (defaults globais — cada spider pode sobrescrever via custom_settings) ---
AUTOTHROTTLE_ENABLED          = False
RETRY_TIMES                   = 2
RETRY_HTTP_CODES              = [500, 502, 503, 504]  # 429 nunca deve ser retentado
LOG_LEVEL                     = "INFO"
DOWNLOAD_TIMEOUT              = 30
