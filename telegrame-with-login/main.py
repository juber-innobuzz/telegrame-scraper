"""Telegram MTProto & Auth Service - Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import API_BASE_PATH, API_NAME, API_VERSION, TELEGRAM_CLIENT_ENABLED
from app.core.queue import job_queue_manager
from app.core.session_pool import session_pool_manager
from app.core.telethon_client import telethon_client_manager
from app.routers import router as auth_service_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and graceful shutdown."""
    if TELEGRAM_CLIENT_ENABLED:
        try:
            # Initialize primary synchronous user client
            await telethon_client_manager.start()
            # Initialize multi-account session pool
            await session_pool_manager.initialize_from_config()
            # Start background async worker pool
            await job_queue_manager.start()
        except Exception as exc:
            print(f"Warning: Telegram background services initialization failed: {exc}")

    yield

    # Graceful shutdown of workers and sessions
    await job_queue_manager.stop()
    await session_pool_manager.stop_all()
    await telethon_client_manager.stop()


app = FastAPI(
    title=API_NAME,
    version=API_VERSION,
    description="Enterprise Telegram MTProto Authentication, Multi-Account Session Pool, and Private Scraping API.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount primary router with Swagger docs
app.include_router(auth_service_router, prefix=API_BASE_PATH)

# Path aliases for backwards compatibility
app.include_router(auth_service_router, prefix="/api", include_in_schema=False)
app.include_router(auth_service_router, prefix="/telegram", include_in_schema=False)
app.include_router(auth_service_router, prefix="", include_in_schema=False)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to Swagger UI documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
