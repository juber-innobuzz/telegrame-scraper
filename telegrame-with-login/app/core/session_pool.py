"""Multi-Account Session Pool & Load Balancer for Telegram MTProto Client."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from telethon import TelegramClient, errors, utils
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message

from app.config import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_SESSION_STRING,
)
from app.models import PrivateMessageItem

logger = logging.getLogger("telegram_session_pool")


class AccountSession:
    """Represents a single authenticated Telegram account in the pool."""

    def __init__(self, session_id: str, session_string: str, name: str = "Primary Account") -> None:
        self.session_id: str = session_id
        self.session_string: str = session_string
        self.name: str = name
        self.client: Optional[TelegramClient] = None
        
        # State tracking
        self.is_connected: bool = False
        self.is_busy: bool = False
        self.sleep_until: float = 0.0  # Unix timestamp until which this account is sleeping (cooldown)
        self.last_request_time: float = 0.0
        self.total_requests: int = 0
        self.total_messages_scraped: int = 0
        self.flood_wait_count: int = 0
        
        # User details
        self.user_id: Optional[int] = None
        self.first_name: Optional[str] = None
        self.username: Optional[str] = None
        self.phone: Optional[str] = None

    @property
    def is_sleeping(self) -> bool:
        """Check if account is currently in a FloodWait cooldown."""
        return time.time() < self.sleep_until

    @property
    def cooldown_remaining_seconds(self) -> int:
        """Return remaining seconds of cooldown."""
        rem = self.sleep_until - time.time()
        return max(0, int(rem))

    @property
    def is_available(self) -> bool:
        """Check if account is connected, not busy, and not sleeping."""
        return self.is_connected and not self.is_busy and not self.is_sleeping

    async def connect(self, api_id: int, api_hash: str) -> bool:
        """Initialize and connect the Telethon client for this session."""
        try:
            self.client = TelegramClient(
                StringSession(self.session_string),
                api_id,
                api_hash,
            )
            # Instruct Telethon to automatically sleep if wait is under 15 seconds
            self.client.flood_sleep_threshold = 15
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.error("Session %s (%s) is unauthorized or expired.", self.session_id, self.name)
                self.is_connected = False
                return False

            me = await self.client.get_me()
            self.user_id = me.id
            self.first_name = me.first_name
            self.username = me.username
            self.phone = me.phone
            self.is_connected = True
            logger.info("Session %s connected as %s (ID: %s)", self.session_id, me.first_name, me.id)
            return True
        except Exception as exc:
            logger.error("Failed to connect session %s: %s", self.session_id, exc)
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect this session."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        self.is_connected = False
        self.is_busy = False

    def mark_sleeping(self, seconds: int) -> None:
        """Put account into cooldown sleep for specified seconds."""
        self.sleep_until = time.time() + seconds
        self.flood_wait_count += 1
        self.is_busy = False
        logger.warning(
            "Account %s (%s) rate-limited. Put on cooldown for %d seconds.",
            self.session_id,
            self.name,
            seconds,
        )


class SessionPoolManager:
    """Manages a dynamic pool of Telegram account sessions with load balancing and rate pacing."""

    def __init__(self) -> None:
        self.sessions: Dict[str, AccountSession] = {}
        self._lock = asyncio.Lock()
        self.min_request_interval: float = 1.0  # Pacing: minimum 1s between requests per account

    @property
    def total_sessions(self) -> int:
        return len(self.sessions)

    @property
    def active_sessions_count(self) -> int:
        return sum(1 for s in self.sessions.values() if s.is_available)

    async def initialize_from_config(self) -> None:
        """Load primary session from environment variables."""
        if TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_SESSION_STRING:
            await self.add_session(
                session_id="primary",
                session_string=TELEGRAM_SESSION_STRING,
                name="Primary Environment Account",
            )

    async def add_session(self, session_id: str, session_string: str, name: str = "Telegram Account") -> bool:
        """Register and connect a new session into the pool."""
        async with self._lock:
            if session_id in self.sessions:
                logger.info("Session %s already in pool. Updating connection...", session_id)
                await self.sessions[session_id].disconnect()

            session = AccountSession(session_id=session_id, session_string=session_string, name=name)
            success = await session.connect(TELEGRAM_API_ID, TELEGRAM_API_HASH)
            if success:
                self.sessions[session_id] = session
                return True
            return False

    async def remove_session(self, session_id: str) -> bool:
        """Disconnect and remove a session from the pool."""
        async with self._lock:
            if session_id in self.sessions:
                await self.sessions[session_id].disconnect()
                del self.sessions[session_id]
                return True
            return False

    async def lease_session(self) -> Optional[AccountSession]:
        """Lease the best available account from the pool (Least-Busy / Round-Robin)."""
        async with self._lock:
            available_sessions = [s for s in self.sessions.values() if s.is_available]
            if not available_sessions:
                return None

            # Pick the session with the lowest total requests to distribute evenly
            selected = min(available_sessions, key=lambda s: s.total_requests)
            selected.is_busy = True
            return selected

    async def release_session(self, session: AccountSession) -> None:
        """Release a leased session back to the pool."""
        async with self._lock:
            if session.session_id in self.sessions:
                session.is_busy = False
                session.last_request_time = time.time()

    async def safe_fetch_chunk(
        self,
        session: AccountSession,
        peer: Any,
        limit: int = 100,
        offset_id: int = 0,
        min_id: int = 0,
        search_query: Optional[str] = None,
    ) -> Tuple[List[PrivateMessageItem], int, Optional[int]]:
        """Fetch a chunk of messages using a leased account with token-bucket pacing."""
        # Enforce rate-limit interval pacing per account
        time_since_last = time.time() - session.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)

        assert session.client is not None
        messages_list: List[PrivateMessageItem] = []
        next_offset_id: Optional[int] = None

        try:
            kwargs: Dict[str, Any] = {"limit": limit}
            if offset_id > 0:
                kwargs["offset_id"] = offset_id
            if min_id > 0:
                kwargs["min_id"] = min_id
            if search_query:
                kwargs["search"] = search_query

            async for msg in session.client.iter_messages(peer, **kwargs):
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
                    chat_id=int(getattr(peer, "id", 0) if hasattr(peer, "id") else (peer if isinstance(peer, int) else 0)),
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

            session.total_requests += 1
            session.total_messages_scraped += len(messages_list)
            session.last_request_time = time.time()
            return messages_list, len(messages_list), next_offset_id

        except errors.FloodWaitError as e:
            session.mark_sleeping(e.seconds + 2)
            raise e

    def get_pool_status(self) -> Dict[str, Any]:
        """Return comprehensive status metrics for all accounts in the pool."""
        pool_metrics = []
        for s in self.sessions.values():
            status_str = "ACTIVE"
            if not s.is_connected:
                status_str = "DISCONNECTED"
            elif s.is_sleeping:
                status_str = f"SLEEPING ({s.cooldown_remaining_seconds}s remaining)"
            elif s.is_busy:
                status_str = "BUSY (Executing Task)"

            pool_metrics.append({
                "session_id": s.session_id,
                "name": s.name,
                "status": status_str,
                "user_id": s.user_id,
                "first_name": s.first_name,
                "username": s.username,
                "phone": s.phone,
                "is_available": s.is_available,
                "total_requests": s.total_requests,
                "total_messages_scraped": s.total_messages_scraped,
                "flood_wait_count": s.flood_wait_count,
                "cooldown_remaining_seconds": s.cooldown_remaining_seconds,
            })

        return {
            "total_accounts": len(self.sessions),
            "available_accounts": self.active_sessions_count,
            "accounts": pool_metrics,
        }

    async def stop_all(self) -> None:
        """Gracefully disconnect all sessions in the pool."""
        async with self._lock:
            for s in self.sessions.values():
                await s.disconnect()
            self.sessions.clear()


# Global singleton session pool
session_pool_manager = SessionPoolManager()
