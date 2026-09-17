"""Telethon MTProto User Client Manager for Telegram Scraper API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from telethon import TelegramClient, errors, utils
from telethon.sessions import StringSession
from telethon.tl.custom.dialog import Dialog
from telethon.tl.custom.message import Message
from telethon.tl.types import (
    Channel,
    Chat,
    User,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaUnsupported,
)

from app.config import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_CLIENT_ENABLED,
    TELEGRAM_SESSION_STRING,
)
from app.models import (
    ChatDetailResponse,
    DialogLastMessage,
    PrivateMessageItem,
    PrivateMessagesResponse,
    UserDialogItem,
    UserDialogsResponse,
    UserProfileResponse,
)

logger = logging.getLogger("telegram_user_client")


class TelethonClientManager:
    """Manages the persistent MTProto Telegram user client session."""

    def __init__(self) -> None:
        self.client: Optional[TelegramClient] = None
        self._is_connected: bool = False
        self._lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        """Check if required credentials exist in configuration."""
        return bool(TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_SESSION_STRING)

    @property
    def is_connected(self) -> bool:
        """Check if client is currently connected and authorized."""
        return self._is_connected and self.client is not None

    async def start(self) -> bool:
        """Initialize and connect the Telethon user client."""
        if not self.is_configured:
            logger.warning("Telegram User Client is not configured (missing credentials in .env).")
            return False

        async with self._lock:
            if self._is_connected and self.client:
                return True

            try:
                logger.info("Connecting Telegram User Client (MTProto)...")
                self.client = TelegramClient(
                    StringSession(TELEGRAM_SESSION_STRING),
                    TELEGRAM_API_ID,
                    TELEGRAM_API_HASH,
                )
                await self.client.connect()

                if not await self.client.is_user_authorized():
                    logger.error("Telegram Session is invalid or expired. Please regenerate session.")
                    self._is_connected = False
                    return False

                me = await self.client.get_me()
                self._is_connected = True
                logger.info(
                    "Telegram User Client successfully connected as %s (ID: %s)",
                    getattr(me, "first_name", "User"),
                    getattr(me, "id", "Unknown"),
                )
                return True
            except Exception as exc:
                logger.error("Failed to connect Telegram User Client: %s", exc)
                self._is_connected = False
                return False

    async def stop(self) -> None:
        """Disconnect client during application shutdown."""
        async with self._lock:
            if self.client and self.client.is_connected():
                logger.info("Disconnecting Telegram User Client...")
                await self.client.disconnect()
            self._is_connected = False

    def _ensure_connected(self) -> None:
        """Raise an exception if the client is not connected or authorized."""
        if not self.is_configured:
            raise RuntimeError(
                "Telegram User Client is not configured. Please ensure TELEGRAM_API_ID, "
                "TELEGRAM_API_HASH, and TELEGRAM_SESSION_STRING are set in your .env file."
            )
        if not self._is_connected or not self.client:
            raise RuntimeError("Telegram User Client is currently disconnected. Please retry shortly.")

    async def get_profile(self) -> UserProfileResponse:
        """Get the profile of the authenticated user."""
        self._ensure_connected()
        assert self.client is not None

        try:
            me = await self.client.get_me()
            return UserProfileResponse(
                status="success",
                user_id=me.id,
                first_name=getattr(me, "first_name", None),
                last_name=getattr(me, "last_name", None),
                username=getattr(me, "username", None),
                phone=getattr(me, "phone", None),
                is_bot=getattr(me, "bot", False),
                is_premium=getattr(me, "premium", False) or False,
            )
        except errors.FloodWaitError as e:
            raise RuntimeError(f"Rate limited by Telegram. Please wait {e.seconds} seconds.") from e

    async def get_dialogs(
        self,
        limit: int = 50,
        filter_type: Optional[str] = None,
        archived: bool = False,
    ) -> UserDialogsResponse:
        """Retrieve user chats, groups, and channels with optional filtering."""
        self._ensure_connected()
        assert self.client is not None

        dialog_items: List[UserDialogItem] = []
        filter_normalized = (filter_type.lower() if filter_type else None)

        try:
            async for dialog in self.client.iter_dialogs(limit=limit, ignore_migrated=True, folder=1 if archived else 0):
                # Classify chat type
                if dialog.is_user:
                    chat_type = "user"
                elif dialog.is_group:
                    chat_type = "group"
                elif dialog.is_channel:
                    chat_type = "channel"
                else:
                    chat_type = "unknown"

                # Apply filter if provided
                if filter_normalized and filter_normalized != chat_type:
                    continue

                # Parse last message preview
                last_msg_obj = None
                if dialog.message:
                    msg = dialog.message
                    media_type = None
                    if msg.media:
                        media_type = type(msg.media).__name__.replace("MessageMedia", "")

                    last_msg_obj = DialogLastMessage(
                        id=msg.id,
                        date=msg.date.isoformat() if msg.date else None,
                        text=msg.message[:150] if msg.message else ("[" + media_type + "]" if media_type else None),
                        sender_id=msg.sender_id,
                        has_media=bool(msg.media),
                        media_type=media_type,
                    )

                entity_username = getattr(dialog.entity, "username", None)

                item = UserDialogItem(
                    id=dialog.id,
                    title=dialog.name or "Untitled",
                    name=dialog.name or "Untitled",
                    chat_type=chat_type,
                    is_user=dialog.is_user,
                    is_group=dialog.is_group,
                    is_channel=dialog.is_channel,
                    unread_count=dialog.unread_count,
                    pinned=dialog.pinned,
                    archived=dialog.archived,
                    entity_username=entity_username,
                    last_message=last_msg_obj,
                )
                dialog_items.append(item)

            return UserDialogsResponse(
                status="success",
                total_dialogs=len(dialog_items),
                limit=limit,
                filter_type=filter_normalized,
                dialogs=dialog_items,
            )
        except errors.FloodWaitError as e:
            raise RuntimeError(f"Rate limited by Telegram. Please wait {e.seconds} seconds.") from e

    async def get_chat_messages(
        self,
        chat_id: Union[int, str],
        limit: int = 50,
        offset_id: int = 0,
        min_id: int = 0,
        max_id: int = 0,
        search_query: Optional[str] = None,
    ) -> PrivateMessagesResponse:
        """Fetch messages from any private chat, group, or channel."""
        self._ensure_connected()
        assert self.client is not None

        # Format chat peer
        peer: Union[int, str] = chat_id
        if isinstance(chat_id, str):
            if chat_id.lstrip("-").isdigit():
                peer = int(chat_id)
            else:
                peer = chat_id.lstrip("@")

        try:
            entity = await self.client.get_entity(peer)
            chat_title = utils.get_display_name(entity)
        except Exception:
            chat_title = str(chat_id)

        messages_list: List[PrivateMessageItem] = []
        next_offset_id: Optional[int] = None

        try:
            kwargs: Dict[str, Any] = {
                "limit": limit,
            }
            if offset_id > 0:
                kwargs["offset_id"] = offset_id
            if min_id > 0:
                kwargs["min_id"] = min_id
            if max_id > 0:
                kwargs["max_id"] = max_id
            if search_query:
                kwargs["search"] = search_query

            async for msg in self.client.iter_messages(peer, **kwargs):
                if not isinstance(msg, Message):
                    continue

                media_type = None
                if msg.media:
                    media_type = type(msg.media).__name__.replace("MessageMedia", "")

                sender_name = None
                sender_username = None
                if msg.sender:
                    sender_name = utils.get_display_name(msg.sender)
                    sender_username = getattr(msg.sender, "username", None)

                item = PrivateMessageItem(
                    id=msg.id,
                    chat_id=int(getattr(entity, "id", chat_id) if hasattr(entity, "id") else chat_id),
                    date=msg.date.isoformat() if msg.date else None,
                    text=msg.message or "",
                    sender_id=msg.sender_id,
                    sender_name=sender_name,
                    sender_username=sender_username,
                    is_outgoing=msg.out or False,
                    is_reply=bool(msg.is_reply),
                    reply_to_msg_id=msg.reply_to_msg_id,
                    has_media=bool(msg.media),
                    media_type=media_type,
                    views=msg.views,
                    forwards=msg.forwards,
                    pinned=msg.pinned or False,
                )
                messages_list.append(item)
                next_offset_id = msg.id

            has_more = len(messages_list) == limit

            return PrivateMessagesResponse(
                status="success",
                chat_id=int(getattr(entity, "id", 0)) if hasattr(entity, "id") else (peer if isinstance(peer, int) else 0),
                chat_title=chat_title,
                count=len(messages_list),
                limit=limit,
                next_offset_id=next_offset_id if has_more else None,
                has_more=has_more,
                messages=messages_list,
            )
        except errors.FloodWaitError as e:
            raise RuntimeError(f"Rate limited by Telegram. Please wait {e.seconds} seconds.") from e
        except errors.ChannelPrivateError as e:
            raise RuntimeError(f"Cannot access private channel or group. You might not be a member: {e}") from e

    async def get_chat_details(self, chat_id: Union[int, str]) -> ChatDetailResponse:
        """Fetch metadata for a chat or group."""
        self._ensure_connected()
        assert self.client is not None

        peer: Union[int, str] = chat_id
        if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
            peer = int(chat_id)

        try:
            entity = await self.client.get_entity(peer)
            title = utils.get_display_name(entity)
            username = getattr(entity, "username", None)

            if isinstance(entity, User):
                chat_type = "user"
            elif isinstance(entity, Chat):
                chat_type = "group"
            elif isinstance(entity, Channel):
                chat_type = "channel" if entity.broadcast else "supergroup"
            else:
                chat_type = "unknown"

            participants_count = getattr(entity, "participants_count", None)

            return ChatDetailResponse(
                status="success",
                id=entity.id,
                title=title,
                chat_type=chat_type,
                username=username,
                participants_count=participants_count,
                is_creator=getattr(entity, "creator", False) or False,
                is_admin=getattr(entity, "admin_rights", None) is not None,
            )
        except errors.FloodWaitError as e:
            raise RuntimeError(f"Rate limited by Telegram. Please wait {e.seconds} seconds.") from e


# Global singleton instance
telethon_client_manager = TelethonClientManager()
