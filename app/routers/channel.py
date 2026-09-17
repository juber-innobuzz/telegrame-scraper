"""Channel Scraper and Enterprise Endpoints Router."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, Query, status

from app.core.http_client import (
    build_channel_web_url,
    normalize_telegram_target,
    telegram_http_client,
)
from app.core.pagination import TelegramPaginationCrawler
from app.core.parser import TelegramParser
from app.core.slicer import build_flat_response_rows, build_response_slices
from app.models import (
    ChannelPostsCursorResponse,
    ChannelScrapeRequest,
    ChannelScrapeResponse,
    ChannelValidateRequest,
    ChannelValidateResponse,
)

router = APIRouter(tags=["Channel Scraper & Management"])


@router.post("/channel", response_model=Union[ChannelScrapeResponse, List[Dict[str, Any]]], summary="Scrape public channel with dynamic data slices")
async def scrape_channel_sliced(payload: ChannelScrapeRequest) -> Any:
    """Single public-channel scraper.
    
    Pass requested slice names in `include` (e.g. ['info', 'messages', 'leads', 'products']) or ['all'].
    Pass `format: 'flat'` to get exact data.json/Apify flat array format.
    """
    target = normalize_telegram_target(payload.username)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram username or URL",
        )

    # 1. Fetch channel header info if requested or in flat mode
    channel_info = None
    if "info" in payload.include or "all" in payload.include or payload.format == "flat":
        try:
            url = build_channel_web_url(target)
            html = await telegram_http_client.fetch_html(url)
            channel_info = TelegramParser.parse_channel_info(html, target)
        except Exception:
            channel_info = None

    # 2. Crawl messages using cursor-based pagination and date filtering
    messages = await TelegramPaginationCrawler.crawl_messages(
        target=target,
        limit=payload.limit,
        before_id=payload.before_message_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )

    # 3. Apply optional text query filter
    if payload.query:
        q = payload.query.lower()
        messages = [m for m in messages if m.text and q in m.text.lower()]

    # 4. If flat output format requested
    if payload.format == "flat":
        return build_flat_response_rows(target=target, channel_info=channel_info, messages=messages)

    # 5. Generate dynamic response slices
    sliced_result = build_response_slices(
        target=target,
        channel_info=channel_info,
        messages=messages,
        include=payload.include,
        options=payload.options,
    )
    sliced_result["status"] = "success"
    return sliced_result


@router.get(
    "/channel/{username}/posts",
    response_model=Union[ChannelPostsCursorResponse, List[Dict[str, Any]]],
    summary="Cursor-based message pagination (Infinite Scroll / Batch sync)",
)
async def get_channel_posts_cursor(
    username: str,
    cursor: Optional[int] = Query(default=None, description="Message ID cursor (fetches posts older than this ID)"),
    limit: int = Query(default=20, ge=1, le=100, description="Page size limit (max 100 per page)"),
    format: str = Query(default="sliced", description="'sliced' for structured JSON or 'flat' for tabular rows"),
    query: Optional[str] = Query(default=None, description="Optional keyword filter"),
) -> Any:
    """Cursor-based message pagination endpoint.
    
    Loads messages in chunks using Telegram message ID cursor.
    Returns `next_cursor` and `has_more` to easily power infinite scrolling or background sync workers.
    """
    target = normalize_telegram_target(username)
    if not target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel username or URL")

    # Fetch channel header info if flat format requested
    channel_info = None
    if format == "flat":
        try:
            url = build_channel_web_url(target)
            html = await telegram_http_client.fetch_html(url)
            channel_info = TelegramParser.parse_channel_info(html, target)
        except Exception:
            channel_info = None

    # Fetch messages before cursor
    messages = await TelegramPaginationCrawler.crawl_messages(
        target=target,
        limit=limit,
        before_id=cursor,
    )

    if query:
        q = query.lower()
        messages = [m for m in messages if m.text and q in m.text.lower()]

    if format == "flat":
        return build_flat_response_rows(target=target, channel_info=channel_info, messages=messages)

    # Compute next pagination cursor
    has_more = len(messages) >= limit
    next_cursor = messages[-1].id if messages and has_more else None

    return {
        "status": "success",
        "username": target,
        "limit": limit,
        "cursor": cursor,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "count": len(messages),
        "messages": [m.model_dump() for m in messages],
    }


@router.post(
    "/channel/validate",
    response_model=ChannelValidateResponse,
    summary="Pre-flight validation: check if channel is public, private, or not found",
)
async def validate_channel(payload: ChannelValidateRequest) -> Dict[str, Any]:
    """Validate a Telegram channel before scraping.
    
    Returns 200 with detailed status ('public', 'private_or_restricted', 'not_found').
    """
    target = normalize_telegram_target(payload.username)
    canonical_url = f"https://t.me/{target}" if target else payload.username

    if not target:
        return {
            "status": "error",
            "username": payload.username,
            "is_valid": False,
            "exists": False,
            "is_public": False,
            "channel_status": "invalid",
            "title": None,
            "subscribers": None,
            "subscribers_str": None,
            "avatar_url": None,
            "is_verified": False,
            "url": canonical_url,
            "error": "Invalid Telegram username or URL format",
        }

    try:
        url = build_channel_web_url(target)
        html = await telegram_http_client.fetch_html(url)

        # Check for missing/non-existent channel indicators
        if "tgme_page_title" not in html and "tgme_channel_info" not in html:
            return {
                "status": "success",
                "username": target,
                "is_valid": True,
                "exists": False,
                "is_public": False,
                "channel_status": "not_found",
                "title": None,
                "subscribers": None,
                "subscribers_str": None,
                "avatar_url": None,
                "is_verified": False,
                "url": canonical_url,
                "error": "Channel does not exist on Telegram",
            }

        # Parse channel metadata
        info = TelegramParser.parse_channel_info(html, target)

        # Check if preview is blocked / private
        is_private = "If you have Telegram, you can view and join" in html and not info.subscribers_str and not info.description

        if is_private:
            return {
                "status": "success",
                "username": target,
                "is_valid": True,
                "exists": True,
                "is_public": False,
                "channel_status": "private_or_restricted",
                "title": info.title,
                "subscribers": None,
                "subscribers_str": None,
                "avatar_url": info.avatar_url,
                "is_verified": info.is_verified,
                "url": canonical_url,
                "error": "Channel is private or requires invite link to view",
            }

        return {
            "status": "success",
            "username": target,
            "is_valid": True,
            "exists": True,
            "is_public": True,
            "channel_status": "public",
            "title": info.title,
            "description": info.description,
            "subscribers": info.subscribers,
            "subscribers_str": info.subscribers_str,
            "avatar_url": info.avatar_url,
            "is_verified": info.is_verified,
            "url": canonical_url,
            "error": None,
        }

    except Exception as e:
        return {
            "status": "error",
            "username": target,
            "is_valid": True,
            "exists": False,
            "is_public": False,
            "channel_status": "not_found",
            "title": None,
            "subscribers": None,
            "subscribers_str": None,
            "avatar_url": None,
            "is_verified": False,
            "url": canonical_url,
            "error": str(e),
        }
