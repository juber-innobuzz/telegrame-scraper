"""Pagination and History Crawling Engine for Telegram Channels and Groups."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Optional

from dateutil import parser as date_parser

from app.core.http_client import build_channel_web_url, normalize_telegram_target, telegram_http_client
from app.core.parser import TelegramParser
from app.models import MessageItem


class TelegramPaginationCrawler:
    """Crawler engine to paginate through Telegram channel histories using ?before=ID parameters."""

    @staticmethod
    async def crawl_messages(
        target: str,
        limit: int = 100,
        offset_id: Optional[int] = None,
        before_id: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[MessageItem]:
        """Crawl channel messages backwards chronologically up to `limit` or bounded by date range."""
        clean_user = normalize_telegram_target(target)
        if not clean_user:
            return []

        # Parse date bounds if provided
        start_date_str = date_from or from_date
        end_date_str = date_to or to_date
        start_dt = date_parser.parse(start_date_str) if start_date_str else None
        end_dt = date_parser.parse(end_date_str) if end_date_str else None
        if start_dt and start_dt.tzinfo is None:
            start_dt = start_dt.replace(hour=0, minute=0, second=0)
        if end_dt and end_dt.tzinfo is None:
            end_dt = end_dt.replace(hour=23, minute=59, second=59)

        collected_messages: List[MessageItem] = []
        seen_ids = set()
        current_before_id = before_id if before_id is not None else offset_id
        max_pages = max(1, (limit // 20) + 5)

        for page in range(max_pages):
            url = build_channel_web_url(clean_user, before_id=current_before_id)
            try:
                html = await telegram_http_client.fetch_html(url)
            except Exception:
                break

            page_messages = TelegramParser.parse_messages(html, clean_user)
            if not page_messages:
                break

            new_msgs_in_page = 0
            # Telegram returns messages in ascending order on each page
            # To scroll backwards, we look at the oldest message ID on the page
            oldest_id_on_page = page_messages[0].id

            for msg in reversed(page_messages):
                if msg.id in seen_ids:
                    continue
                seen_ids.add(msg.id)
                new_msgs_in_page += 1

                # Check date constraints if applicable
                msg_dt = None
                if msg.date:
                    try:
                        msg_dt = date_parser.parse(msg.date)
                        if msg_dt.tzinfo and start_dt and not start_dt.tzinfo:
                            start_dt = start_dt.astimezone(msg_dt.tzinfo)
                        if msg_dt.tzinfo and end_dt and not end_dt.tzinfo:
                            end_dt = end_dt.astimezone(msg_dt.tzinfo)
                    except Exception:
                        pass

                # If message is newer than end_dt, skip it
                if end_dt and msg_dt and msg_dt > end_dt:
                    continue

                # If message is older than start_dt, we can stop crawling earlier
                if start_dt and msg_dt and msg_dt < start_dt:
                    return collected_messages

                collected_messages.append(msg)
                if len(collected_messages) >= limit:
                    return collected_messages

            # If no new messages were found or we reached the first message
            if new_msgs_in_page == 0 or oldest_id_on_page <= 1:
                break

            # Next request should fetch messages before the oldest one we saw
            current_before_id = oldest_id_on_page
            await asyncio.sleep(0.2)  # courteous crawl delay

        return collected_messages
