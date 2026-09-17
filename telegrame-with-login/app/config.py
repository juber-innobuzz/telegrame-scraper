"""Configuration and settings for the Telegram Auth & MTProto Service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SERVICE_DIR.parent

if (SERVICE_DIR / ".env").exists():
    load_dotenv(dotenv_path=SERVICE_DIR / ".env")
elif (ROOT_DIR / ".env").exists():
    load_dotenv(dotenv_path=ROOT_DIR / ".env")

API_NAME: str = "Telegram MTProto & Auth Service"
API_VERSION: str = "1.0.0"
API_BASE_PATH: str = "/api/v1/telegram"

# Telegram MTProto User Client configuration
TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "").strip()
TELEGRAM_SESSION_STRING: str = os.getenv("TELEGRAM_SESSION_STRING", "").strip()
TELEGRAM_CLIENT_ENABLED: bool = bool(TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_SESSION_STRING)

# Redis Task Queue configuration
REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)
REDIS_ENABLED: bool = bool(REDIS_URL)

DEFAULT_SCRAPE_LIMIT: int = 100
MAX_SCRAPE_LIMIT: int = 2000
