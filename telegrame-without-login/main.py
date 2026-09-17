"""Telegram Public Scraper Service - Application Entry Point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config import API_BASE_PATH, API_NAME, API_VERSION
from app.core.http_client import telegram_http_client
from app.routers import router as telegram_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and graceful shutdown."""
    yield
    await telegram_http_client.close()


app = FastAPI(
    title=API_NAME,
    version=API_VERSION,
    description="Stateless, high-performance public Telegram channel & post scraper API. No login or credentials required.",
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

# Mount primary unified Telegram router with Swagger docs
app.include_router(telegram_router, prefix=API_BASE_PATH)

# Path aliases for full backwards compatibility
app.include_router(telegram_router, prefix="/api", include_in_schema=False)
app.include_router(telegram_router, prefix="/telegram", include_in_schema=False)
app.include_router(telegram_router, prefix="", include_in_schema=False)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to Swagger UI documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
