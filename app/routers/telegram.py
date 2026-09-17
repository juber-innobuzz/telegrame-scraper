"""Consolidated and modular router for Telegram Public Scraper API (v2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.batch import router as batch_router
from app.routers.channel import router as channel_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.post import parse_post_target, router as post_router
from app.routers.search import router as search_router
from app.routers.user import router as user_router

router = APIRouter()

# Include sub-routers
router.include_router(channel_router)
router.include_router(post_router)
router.include_router(batch_router)
router.include_router(search_router)
router.include_router(health_router)
router.include_router(user_router)
router.include_router(jobs_router)
router.include_router(auth_router)

__all__ = [
    "router",
    "channel_router",
    "post_router",
    "batch_router",
    "search_router",
    "health_router",
    "user_router",
    "jobs_router",
    "auth_router",
    "parse_post_target",
]
