"""Batch Channels Scraper Endpoint Router."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Union
from fastapi import APIRouter

from app.core.http_client import (
    build_channel_web_url,
    normalize_telegram_target,
    telegram_http_client,
)
from app.core.pagination import TelegramPaginationCrawler
from app.core.parser import TelegramParser
from app.core.slicer import build_flat_response_rows, build_response_slices
from app.models import BatchScrapeRequest, BatchScrapeResponse

router = APIRouter(tags=["Batch Scraper"])


@router.post("/batch", response_model=Union[BatchScrapeResponse, List[Dict[str, Any]]], summary="Scrape multiple public channels with shared slices")
async def scrape_batch_sliced(payload: BatchScrapeRequest) -> Any:
    """Batch scraper across multiple Telegram channels with rate-limiting backoff and watermark filtering.
    
    Pass `format: 'flat'` to get exact data.json/Apify flat array across all channels.
    """
    results = []
    flat_rows: List[Dict[str, Any]] = []
    successful = 0
    failed = 0

    for i, raw_target in enumerate(payload.usernames):
        target = normalize_telegram_target(raw_target)
        if not target:
            failed += 1
            results.append({"username": raw_target, "status": "error", "error": "Invalid username"})
            continue

        try:
            channel_info = None
            if "info" in payload.include or "all" in payload.include or payload.format == "flat":
                url = build_channel_web_url(target)
                html = await telegram_http_client.fetch_html(url)
                channel_info = TelegramParser.parse_channel_info(html, target)

            messages = await TelegramPaginationCrawler.crawl_messages(
                target=target,
                limit=payload.limit_per_channel,
                date_from=payload.date_from,
                date_to=payload.date_to,
            )

            # Apply since_message_id watermark if provided
            if payload.since_message_id and target in payload.since_message_id:
                watermark = payload.since_message_id[target]
                messages = [m for m in messages if m.id > watermark]

            # Apply query filter
            if payload.query:
                q = payload.query.lower()
                messages = [m for m in messages if m.text and q in m.text.lower()]

            if payload.format == "flat":
                channel_flat = build_flat_response_rows(target=target, channel_info=channel_info, messages=messages)
                flat_rows.extend(channel_flat)
            else:
                sliced = build_response_slices(
                    target=target,
                    channel_info=channel_info,
                    messages=messages,
                    include=payload.include,
                    options=payload.options,
                )
                sliced["status"] = "success"
                results.append(sliced)

            successful += 1

        except Exception as e:
            failed += 1
            results.append({
                "username": target,
                "status": "error",
                "error": str(e),
            })

        # Anti-flood delay between multiple channels
        if i < len(payload.usernames) - 1 and payload.delay_sec > 0:
            await asyncio.sleep(payload.delay_sec)

    if payload.format == "flat":
        return flat_rows

    return {
        "status": "success",
        "total_channels": len(payload.usernames),
        "successful": successful,
        "failed": failed,
        "results": results,
    }
