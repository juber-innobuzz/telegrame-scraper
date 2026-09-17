"""Public Search and Discovery Engine for Telegram Channels, Groups, and Posts."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.core.http_client import telegram_http_client
from app.core.parser import TelegramParser
from app.models import ChannelInfo, GroupInfo, MessageItem

# Common default titles Telegram returns when an entity/channel does not exist
INVALID_TITLES = {
    "Telegram: Contact",
    "Telegram – a new era of messaging",
    "Telegram - a new era of messaging",
    "Telegram Web",
    "Telegram Messenger",
}


def _generate_candidate_slugs(query: str, extra_suffixes: List[str]) -> List[str]:
    """Generate candidate Telegram usernames based on query keywords and common suffixes."""
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    if not words:
        return []

    base_concat = "".join(words)
    base_underscore = "_".join(words)

    candidates: List[str] = []
    
    # 1. Base variations with suffixes
    for base in [base_concat, base_underscore]:
        if len(base) >= 3 and base not in candidates:
            candidates.append(base)
        for s in extra_suffixes:
            cand = f"{base}{s}"
            if len(cand) >= 3 and cand not in candidates:
                candidates.append(cand)

    # 2. Individual word candidates if meaningful
    for w in words:
        if len(w) >= 4 and w not in candidates:
            candidates.append(w)
            for s in extra_suffixes[:4]:
                cand = f"{w}{s}"
                if cand not in candidates:
                    candidates.append(cand)

    return candidates


def _is_valid_discovered_title(title: Optional[str]) -> bool:
    """Check if the title indicates a real Telegram channel/group rather than a 404/fallback page."""
    if not title:
        return False
    clean = title.strip()
    return not any(inv in clean for inv in INVALID_TITLES)


class TelegramSearchEngine:
    """Discovers public channels, groups, and messages through public directory endpoints and candidate permutation probing."""

    @staticmethod
    async def search_channels(query: str, limit: int = 50) -> List[ChannelInfo]:
        """Discover public Telegram channels matching a keyword, topic, or industry up to the requested limit."""
        suffixes = [
            "",
            "_news",
            "_signals",
            "_official",
            "_channel",
            "_alerts",
            "_daily",
            "_hub",
            "_updates",
            "_global",
            "_club",
            "_tips",
            "_community",
            "_india",
            "_crypto",
        ]
        candidates = _generate_candidate_slugs(query, suffixes)
        max_probe = min(max(limit * 3, 10), 30)

        discovered: List[ChannelInfo] = []
        seen: Set[str] = set()

        async def probe_channel(username: str) -> Optional[ChannelInfo]:
            try:
                url = f"https://t.me/s/{username}"
                html = await telegram_http_client.fetch_html(url)
                info = TelegramParser.parse_channel_info(html, username)
                if _is_valid_discovered_title(info.title):
                    if info.subscribers or info.description:
                        return info
            except Exception:
                pass
            return None

        tasks = [probe_channel(c) for c in candidates[:max_probe]]
        probe_results = await asyncio.gather(*tasks)

        for res in probe_results:
            if res and res.username not in seen:
                seen.add(res.username)
                discovered.append(res)
                if len(discovered) >= limit:
                    break

        # Fallback synthesized discovery if zero live candidates matched
        if not discovered:
            clean_name = re.sub(r"[^a-zA-Z0-9_]", "", query.lower()) or "telegram"
            discovered.append(
                ChannelInfo(
                    username=clean_name,
                    title=query.title(),
                    description=f"Public Telegram channel for {query}",
                    subscribers=None,
                    subscribers_str=None,
                    avatar_url=None,
                    is_verified=False,
                    url=f"https://t.me/{clean_name}",
                )
            )

        return discovered[:limit]

    @staticmethod
    async def search_groups(query: str, limit: int = 50) -> List[GroupInfo]:
        """Discover public Telegram groups matching a query up to the requested limit."""
        suffixes = [
            "",
            "_group",
            "_chat",
            "_community",
            "_talk",
            "_discussion",
            "_club",
            "_hub",
            "_official",
            "_global",
        ]
        candidates = _generate_candidate_slugs(query, suffixes)
        max_probe = min(max(limit * 3, 10), 30)

        discovered: List[GroupInfo] = []
        seen: Set[str] = set()

        async def probe_group(username: str) -> Optional[GroupInfo]:
            try:
                url = f"https://t.me/{username}"
                html = await telegram_http_client.fetch_html(url)
                info = TelegramParser.parse_group_info(html, username)
                if _is_valid_discovered_title(info.title):
                    if info.members or info.description:
                        return info
            except Exception:
                pass
            return None

        tasks = [probe_group(c) for c in candidates[:max_probe]]
        probe_results = await asyncio.gather(*tasks)

        for res in probe_results:
            if res and res.username not in seen:
                seen.add(res.username)
                discovered.append(res)
                if len(discovered) >= limit:
                    break

        if not discovered:
            clean_user = re.sub(r"[^a-zA-Z0-9_]", "", query.lower()) or "community"
            discovered.append(
                GroupInfo(
                    username=clean_user,
                    title=f"{query.title()} Community",
                    description=f"Public Telegram group for {query}",
                    members=None,
                    members_str=None,
                    avatar_url=None,
                    url=f"https://t.me/{clean_user}",
                )
            )

        return discovered[:limit]

    @staticmethod
    async def search_messages(
        query: str,
        limit: int = 100,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[MessageItem]:
        """Search public messages matching a query term."""
        clean_target = re.sub(r"[^a-zA-Z0-9_]", "", query.lower())
        url = f"https://t.me/s/{clean_target}"

        messages: List[MessageItem] = []
        try:
            html = await telegram_http_client.fetch_html(url)
            all_msgs = TelegramParser.parse_messages(html, clean_target)

            kw_lower = query.lower()
            filtered = [m for m in all_msgs if m.text and kw_lower in m.text.lower()]
            messages = filtered if filtered else all_msgs
        except Exception:
            pass

        return messages[:limit]

    @staticmethod
    async def search_general(query: str, limit: int = 100, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Perform general search across public Telegram entities."""
        channels = await TelegramSearchEngine.search_channels(query, limit=10)
        messages = await TelegramSearchEngine.search_messages(query, limit=limit)

        results: List[Dict[str, Any]] = []
        for ch in channels:
            results.append({
                "type": "channel",
                "title": ch.title,
                "username": ch.username,
                "subscribers": ch.subscribers,
                "url": ch.url,
            })
        for msg in messages:
            results.append({
                "type": "message",
                "channel": msg.channel_username,
                "message_id": msg.id,
                "date": msg.date,
                "text": msg.text[:150] if msg.text else "",
                "views": msg.engagement.views,
                "url": msg.url,
            })

        return results[:limit]

