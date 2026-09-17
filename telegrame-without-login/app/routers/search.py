"""Search & Discovery Endpoint Router."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status

from app.core.search_engine import TelegramSearchEngine
from app.models import SearchRequest, SearchResponse

router = APIRouter(tags=["Search & Discovery"])


@router.post("/search", response_model=SearchResponse, summary="Discover public Telegram channels and groups by keyword/topic")
async def search_telegram_public(payload: SearchRequest) -> Dict[str, Any]:
    """Discover and search public Telegram channels or communities by topic, keyword, or industry."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search query cannot be empty.")

    channels_data: Optional[List[Dict[str, Any]]] = None
    groups_data: Optional[List[Dict[str, Any]]] = None
    total_count = 0

    if payload.type in ["channel", "all"]:
        channels = await TelegramSearchEngine.search_channels(query, limit=payload.limit)
        channels_data = [c.model_dump() for c in channels]
        total_count += len(channels_data)

    if payload.type in ["group", "all"]:
        groups = await TelegramSearchEngine.search_groups(query, limit=payload.limit)
        groups_data = [g.model_dump() for g in groups]
        total_count += len(groups_data)

    return {
        "status": "success",
        "query": query,
        "type": payload.type,
        "total_results": total_count,
        "channels": channels_data,
        "groups": groups_data,
    }
