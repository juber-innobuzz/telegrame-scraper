"""Telegram API Routers package."""

from app.routers.auth import router as auth_router
from app.routers.batch import router as batch_router
from app.routers.channel import router as channel_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.post import router as post_router
from app.routers.search import router as search_router
from app.routers.telegram import router
from app.routers.user import router as user_router

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
]
