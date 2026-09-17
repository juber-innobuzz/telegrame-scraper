"""Single Post Scraper Endpoint Router."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, status

from app.core.http_client import (
    build_message_embed_url,
    normalize_telegram_target,
    telegram_http_client,
)
from app.core.pagination import TelegramPaginationCrawler
from app.core.parser import TelegramParser
from app.core.slicer import build_flat_response_rows, build_response_slices
from app.models import MessageItem, PostScrapeRequest, PostScrapeResponse

router = APIRouter(tags=["Post Scraper"])


def parse_post_target(url_or_target: Optional[str], username: Optional[str], message_id: Optional[int]) -> tuple[str, int]:
    """Parse username and message ID from either direct URL or explicit fields."""
    if url_or_target:
        clean_url = url_or_target.strip()
        parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            if parts[0] == "s" and len(parts) >= 3:
                return parts[1], int(parts[2])
            elif parts[0] != "s":
                try:
                    return parts[0], int(parts[1])
                except ValueError:
                    pass
    if username and message_id:
        return normalize_telegram_target(username), int(message_id)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Must provide a valid Telegram post URL (e.g. https://t.me/durov/1) or both username and message_id.",
    )


@router.post("/post", response_model=Union[PostScrapeResponse, List[Dict[str, Any]]], summary="Scrape single public post with dynamic data slices")
async def scrape_post_sliced(payload: PostScrapeRequest) -> Any:
    """Single public post scraper.
    
    Extracts derived intelligence (leads, prices, media, products) for a single post.
    Pass `format: 'flat'` to get exact data.json/Apify flat array format.
    """
    username, msg_id = parse_post_target(payload.url, payload.username, payload.message_id)

    # 1. Fetch post embed widget HTML
    embed_url = build_message_embed_url(username, msg_id)
    post_item: Optional[MessageItem] = None
    try:
        html = await telegram_http_client.fetch_html(embed_url)
        parsed_msgs = TelegramParser.parse_messages(html, username)
        for m in parsed_msgs:
            if m.id == msg_id:
                post_item = m
                break
        if not post_item and parsed_msgs and len(parsed_msgs) == 1:
            post_item = parsed_msgs[0]
    except Exception:
        pass

    # 2. Fallback to channel history crawl if widget embed was not rendered
    if not post_item:
        channel_msgs = await TelegramPaginationCrawler.crawl_messages(username, limit=30, before_id=msg_id + 1)
        for m in channel_msgs:
            if m.id == msg_id:
                post_item = m
                break

    if not post_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message #{msg_id} in channel @{username} not found or is private.",
        )

    # 3. If flat format requested
    if payload.format == "flat":
        return build_flat_response_rows(target=username, channel_info=None, messages=[post_item])

    # 4. Generate dynamic response slices
    sliced_result = build_response_slices(
        target=username,
        channel_info=None,
        messages=[post_item],
        include=payload.include,
        options=payload.options,
    )
    sliced_result["status"] = "success"
    sliced_result["url"] = post_item.url
    sliced_result["username"] = username
    sliced_result["message_id"] = msg_id
    return sliced_result
