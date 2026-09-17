"""FastAPI Router for Telegram Authentication Lifecycle (Send OTP, Verify Code, 2FA, Logout)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from app.config import TELEGRAM_API_HASH, TELEGRAM_API_ID
from app.core.session_pool import session_pool_manager
from app.models import (
    AuthLogoutRequest,
    AuthSendCodeRequest,
    AuthSendCodeResponse,
    AuthStatusResponse,
    AuthVerify2FARequest,
    AuthVerifyCodeRequest,
    AuthVerifyResponse,
)

logger = logging.getLogger("telegram_auth_router")

router = APIRouter(prefix="/auth", tags=["Telegram Authentication API"])

# In-flight login state store: auth_session_id -> {client, phone, phone_code_hash, timestamp}
_in_flight_auth: Dict[str, Dict[str, Any]] = {}
_auth_lock = asyncio.Lock()


def _clean_expired_in_flight() -> None:
    """Clean up auth attempts older than 10 minutes."""
    now = time.time()
    expired = [k for k, v in _in_flight_auth.items() if now - v.get("timestamp", 0) > 600]
    for k in expired:
        entry = _in_flight_auth.pop(k, None)
        if entry and entry.get("client") and entry["client"].is_connected():
            asyncio.create_task(entry["client"].disconnect())


@router.post(
    "/send-code",
    response_model=AuthSendCodeResponse,
    summary="Request Telegram OTP Login Code",
    description="Initiates login flow by sending a verification code to the user's Telegram app or SMS.",
)
async def send_login_code(payload: AuthSendCodeRequest) -> AuthSendCodeResponse:
    """Send OTP code to Telegram phone number."""
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured in .env file.",
        )

    phone = payload.phone_number.strip()
    if not phone.startswith("+"):
        if len(phone) == 10 and phone.isdigit():
            phone = f"+91{phone}"
        else:
            phone = f"+{phone}"

    _clean_expired_in_flight()

    client = TelegramClient(StringSession(), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.connect()

    try:
        sent_code = await client.send_code_request(phone)
        auth_session_id = str(uuid.uuid4())

        async with _auth_lock:
            _in_flight_auth[auth_session_id] = {
                "client": client,
                "phone": phone,
                "phone_code_hash": sent_code.phone_code_hash,
                "timestamp": time.time(),
            }

        return AuthSendCodeResponse(
            status="code_sent",
            auth_session_id=auth_session_id,
            phone_number=phone,
            phone_code_hash=sent_code.phone_code_hash,
            is_code_via_app=getattr(sent_code.type, "__class__", None).__name__ != "SentCodeTypeSms",
            timeout=getattr(sent_code, "timeout", 120) or 120,
            message="Verification code sent to your Telegram app or SMS.",
        )

    except errors.PhoneNumberInvalidError:
        await client.disconnect()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The phone number is invalid. Ensure it includes country code (e.g. +91XXXXXXXXXX).",
        )
    except errors.FloodWaitError as e:
        await client.disconnect()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Telegram rate limited code requests. Please wait {e.seconds} seconds.",
        )
    except Exception as exc:
        await client.disconnect()
        logger.error("Failed to send login code: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/verify-code",
    response_model=AuthVerifyResponse,
    summary="Submit OTP Code to Complete Login",
    description="Submits the received OTP code. If 2FA is enabled on the account, returns 2fa_required. Otherwise completes login and registers session.",
)
async def verify_login_code(payload: AuthVerifyCodeRequest) -> AuthVerifyResponse:
    """Verify submitted OTP code."""
    async with _auth_lock:
        auth_entry = _in_flight_auth.get(payload.auth_session_id)

    if not auth_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth_session_id. Please request a new code via /auth/send-code.",
        )

    client: TelegramClient = auth_entry["client"]
    phone = payload.phone_number or auth_entry["phone"]
    phone_code_hash = payload.phone_code_hash or auth_entry["phone_code_hash"]

    try:
        await client.sign_in(phone=phone, code=payload.code, phone_code_hash=phone_code_hash)
    except errors.SessionPasswordNeededError:
        if payload.password:
            try:
                await client.sign_in(password=payload.password)
            except errors.PasswordHashInvalidError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid 2-Step Verification password.",
                )
        else:
            return AuthVerifyResponse(
                status="2fa_required",
                auth_session_id=payload.auth_session_id,
                message="2-Step Verification (cloud password) is enabled on this account. Please submit password to /auth/verify-2fa.",
            )
    except errors.PhoneCodeInvalidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is incorrect.",
        )
    except errors.PhoneCodeExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code has expired. Please request a new code.",
        )
    except Exception as exc:
        logger.error("Error verifying code: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Successful login
    session_string = client.session.save()
    me = await client.get_me()
    session_id = f"account_{me.id}"
    session_name = payload.session_name or f"{me.first_name} (@{me.username or me.id})"

    # Auto add to multi-account session pool
    if payload.auto_add_to_pool:
        await session_pool_manager.add_session(
            session_id=session_id,
            session_string=session_string,
            name=session_name,
        )

    async with _auth_lock:
        _in_flight_auth.pop(payload.auth_session_id, None)

    return AuthVerifyResponse(
        status="authenticated",
        session_id=session_id,
        session_string=session_string,
        message="Successfully authenticated and added to active Session Pool!",
        user={
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
            "is_premium": getattr(me, "premium", False) or False,
        },
    )


@router.post(
    "/verify-2fa",
    response_model=AuthVerifyResponse,
    summary="Submit 2-Step Verification Password",
    description="Submits 2FA cloud password if /auth/verify-code returned 2fa_required.",
)
async def verify_2fa_password(payload: AuthVerify2FARequest) -> AuthVerifyResponse:
    """Submit 2FA password to finalize authentication."""
    async with _auth_lock:
        auth_entry = _in_flight_auth.get(payload.auth_session_id)

    if not auth_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired auth_session_id.",
        )

    client: TelegramClient = auth_entry["client"]

    try:
        await client.sign_in(password=payload.password)
    except errors.PasswordHashInvalidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 2-Step Verification password.",
        )
    except Exception as exc:
        logger.error("Error verifying 2FA password: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    session_string = client.session.save()
    me = await client.get_me()
    session_id = f"account_{me.id}"
    session_name = payload.session_name or f"{me.first_name} (@{me.username or me.id})"

    if payload.auto_add_to_pool:
        await session_pool_manager.add_session(
            session_id=session_id,
            session_string=session_string,
            name=session_name,
        )

    async with _auth_lock:
        _in_flight_auth.pop(payload.auth_session_id, None)

    return AuthVerifyResponse(
        status="authenticated",
        session_id=session_id,
        session_string=session_string,
        message="Successfully authenticated with 2FA and added to Session Pool!",
        user={
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
            "is_premium": getattr(me, "premium", False) or False,
        },
    )


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Get Authentication Status Overview",
    description="Returns list of all authenticated Telegram sessions active in the server.",
)
async def get_auth_status() -> AuthStatusResponse:
    """Check authentication status across all accounts."""
    pool_data = session_pool_manager.get_pool_status()
    accounts = pool_data.get("accounts", [])
    return AuthStatusResponse(
        status="success",
        is_authenticated=len(accounts) > 0,
        total_accounts=len(accounts),
        accounts=accounts,
    )


@router.post(
    "/logout",
    summary="Log Out and Remove Session",
    description="Disconnects and removes an account from the session pool.",
)
async def logout_session(payload: AuthLogoutRequest) -> Dict[str, Any]:
    """Disconnect and remove a session."""
    success = await session_pool_manager.remove_session(payload.session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID '{payload.session_id}' not found in active pool.",
        )

    return {
        "status": "success",
        "message": f"Session '{payload.session_id}' successfully disconnected and removed from pool.",
        "remaining_accounts": session_pool_manager.total_sessions,
    }
