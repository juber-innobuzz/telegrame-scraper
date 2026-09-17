"""API endpoints for authenticated Telegram user operations (private chats, dialogs, messages)."""

from __future__ import annotations

from typing import Optional, Union
from fastapi import APIRouter, HTTPException, Query, status

from app.core.telethon_client import telethon_client_manager
from app.models import (
    ChatDetailResponse,
    PrivateMessagesResponse,
    UserDialogsResponse,
    UserProfileResponse,
)

router = APIRouter(prefix="/user", tags=["Telegram User & Private Chats API"])


def _check_client_availability() -> None:
    """Validate that Telethon client is configured and ready."""
    if not telethon_client_manager.is_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Telegram User Client is not configured. Please ensure TELEGRAM_API_ID, "
                "TELEGRAM_API_HASH, and TELEGRAM_SESSION_STRING are set in your .env file."
            ),
        )
    if not telethon_client_manager.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram User Client is currently connecting or disconnected. Please try again shortly.",
        )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get Authenticated User Profile",
    description="Returns account details of the currently logged-in Telegram user.",
)
async def get_my_profile() -> UserProfileResponse:
    """Return profile details for the logged-in user account."""
    _check_client_availability()
    try:
        return await telethon_client_manager.get_profile()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/dialogs",
    response_model=UserDialogsResponse,
    summary="List User Dialogs & Private Chats",
    description="Retrieve personal direct messages (DMs), private groups, and channels the user is part of.",
)
async def list_user_dialogs(
    limit: int = Query(default=50, ge=1, le=500, description="Max number of dialogs to return"),
    chat_type: Optional[str] = Query(
        default=None,
        pattern="^(user|group|channel)$",
        description="Filter by chat type: 'user' (DMs), 'group' (groups), or 'channel' (channels)",
    ),
    archived: bool = Query(default=False, description="Include archived dialogs folder"),
) -> UserDialogsResponse:
    """Fetch user's dialog list with last message snippet and unread counts."""
    _check_client_availability()
    try:
        return await telethon_client_manager.get_dialogs(limit=limit, filter_type=chat_type, archived=archived)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/chats/{chat_id}/messages",
    response_model=PrivateMessagesResponse,
    summary="Fetch Messages from Private Chat or Group",
    description="Retrieve message history from any private 1-on-1 chat, group, or channel by chat ID or username.",
)
async def get_chat_messages(
    chat_id: str,
    limit: int = Query(default=50, ge=1, le=500, description="Max messages to fetch per batch"),
    offset_id: int = Query(default=0, ge=0, description="Message ID cursor to fetch older messages from"),
    min_id: int = Query(default=0, ge=0, description="Fetch only messages newer than this ID"),
    max_id: int = Query(default=0, ge=0, description="Fetch only messages older than this ID"),
    search: Optional[str] = Query(default=None, description="Optional search keyword filter"),
) -> PrivateMessagesResponse:
    """Retrieve message history from a private chat."""
    _check_client_availability()
    try:
        return await telethon_client_manager.get_chat_messages(
            chat_id=chat_id,
            limit=limit,
            offset_id=offset_id,
            min_id=min_id,
            max_id=max_id,
            search_query=search,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/chats/{chat_id}",
    response_model=ChatDetailResponse,
    summary="Get Chat / Group Metadata",
    description="Retrieve metadata, permissions, and participants count for a specific chat.",
)
async def get_chat_details(chat_id: str) -> ChatDetailResponse:
    """Fetch metadata for a chat or group."""
    _check_client_availability()
    try:
        return await telethon_client_manager.get_chat_details(chat_id=chat_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
