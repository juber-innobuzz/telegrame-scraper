"""Resilient HTTP client with User-Agent rotation, backoff, and Telegram URL normalization."""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.config import (
    BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    USER_AGENTS,
)


def normalize_telegram_target(target: str) -> str:
    """Extract clean username from string, @handle, or any variant of t.me URL.
    
    Examples:
        - '@durov' -> 'durov'
        - 'https://t.me/durov' -> 'durov'
        - 'https://t.me/s/durov' -> 'durov'
        - 'https://t.me/s/durov/123' -> 'durov'
        - 't.me/joinchat/...' -> 'joinchat/...'
    """
    if not target:
        return ""
    target = target.strip()
    
    # Handle @handle
    if target.startswith("@"):
        return target[1:].strip()
    
    # Handle full URLs
    if "t.me" in target or "telegram.me" in target:
        parsed = urlparse(target if "://" in target else f"https://{target}")
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if not path_parts:
            return ""
        if path_parts[0] == "s" and len(path_parts) > 1:
            return path_parts[1]
        return path_parts[0]
        
    return target.strip("/")


def build_channel_web_url(username: str, before_id: Optional[int] = None, after_id: Optional[int] = None) -> str:
    """Construct Telegram public web preview URL (https://t.me/s/<username>)."""
    clean_user = normalize_telegram_target(username)
    base_url = f"https://t.me/s/{clean_user}"
    params = []
    if before_id:
        params.append(f"before={before_id}")
    if after_id:
        params.append(f"after={after_id}")
    if params:
        return f"{base_url}?{'&'.join(params)}"
    return base_url


def build_message_embed_url(username: str, message_id: int) -> str:
    """Construct Telegram post widget embed URL (https://t.me/<username>/<id>?embed=1)."""
    clean_user = normalize_telegram_target(username)
    return f"https://t.me/{clean_user}/{message_id}?embed=1"


def get_random_headers() -> Dict[str, str]:
    """Return headers with randomly rotated realistic User-Agent."""
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    return headers


class TelegramHttpClient:
    """Async HTTP Client dedicated to scraping Telegram public endpoints with anti-throttle backoff."""

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def get_client(self) -> httpx.AsyncClient:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._client is None or self._client.is_closed or self._loop != current_loop:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
            self._loop = current_loop
        return self._client

    async def fetch_html(self, url: str, custom_headers: Optional[Dict[str, str]] = None) -> str:
        """Fetch raw HTML string from target URL with retry and exponential backoff."""
        client = await self.get_client()
        headers = get_random_headers()
        if custom_headers:
            headers.update(custom_headers)

        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.get(url, headers=headers)
                
                # If rate limited (HTTP 429) or temporary gateway error
                if response.status_code in (429, 502, 503, 504):
                    wait_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0.5, 1.5)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.text

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_err = exc
                wait_time = (BACKOFF_FACTOR ** attempt) + random.uniform(0.2, 0.8)
                await asyncio.sleep(wait_time)

        if last_err:
            raise last_err
        raise httpx.RequestError(f"Failed to fetch {url} after {MAX_RETRIES} retries")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global client instance
telegram_http_client = TelegramHttpClient()
