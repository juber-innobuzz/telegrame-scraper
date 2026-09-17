"""Routers package for Public Telegram Scraper Service."""

from fastapi import APIRouter

from app.routers.batch import router as batch_router
from app.routers.channel import router as channel_router
from app.routers.health import router as health_router
from app.routers.post import parse_post_target, router as post_router
from app.routers.search import router as search_router

router = APIRouter()

router.include_router(channel_router)
router.include_router(post_router)
router.include_router(batch_router)
router.include_router(search_router)
router.include_router(health_router)

__all__ = [
    "router",
    "channel_router",
    "post_router",
    "batch_router",
    "search_router",
    "health_router",
    "parse_post_target",
]
