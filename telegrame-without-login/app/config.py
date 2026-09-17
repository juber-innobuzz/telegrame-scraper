"""Configuration and settings for the Telegram Public Scraper Service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

API_NAME: str = "Telegram Public Scraper API"
API_VERSION: str = "1.0.0"
API_BASE_PATH: str = "/api/v1/telegram"

REQUEST_TIMEOUT: int = int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "15"))
MAX_RETRIES: int = int(os.getenv("TELEGRAM_MAX_RETRIES", "3"))
BACKOFF_FACTOR: float = float(os.getenv("TELEGRAM_BACKOFF_FACTOR", "1.5"))
MAX_CONNECTIONS: int = int(os.getenv("TELEGRAM_MAX_CONNECTIONS", "50"))
MAX_KEEPALIVE_CONNECTIONS: int = int(os.getenv("TELEGRAM_MAX_KEEPALIVE_CONNECTIONS", "20"))
DEFAULT_SCRAPE_LIMIT: int = 100
MAX_SCRAPE_LIMIT: int = 2000

USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
