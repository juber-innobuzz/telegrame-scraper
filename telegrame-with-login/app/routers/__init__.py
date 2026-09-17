"""Routers package for Telegram MTProto & Auth Service."""

from fastapi import APIRouter

from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.user import router as user_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(user_router)
router.include_router(jobs_router)
router.include_router(health_router)

__all__ = [
    "router",
    "auth_router",
    "user_router",
    "jobs_router",
    "health_router",
]
