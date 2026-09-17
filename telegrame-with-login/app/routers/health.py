"""Health and Telemetry Endpoint Router for MTProto & Auth Service."""

from __future__ import annotations

import os
import platform
import sys
import time
from typing import Any, Dict
from fastapi import APIRouter

from app.config import API_NAME, API_VERSION, TELEGRAM_CLIENT_ENABLED, REDIS_ENABLED
from app.core.session_pool import session_pool_manager

router = APIRouter(tags=["Health & Telemetry"])

# Record start time for uptime calculation
START_TIME = time.time()


@router.get("/health", summary="Basic Health check endpoint")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": API_NAME,
        "version": API_VERSION,
        "telegram_client_configured": TELEGRAM_CLIENT_ENABLED,
        "redis_configured": REDIS_ENABLED,
    }


@router.get("/health/detailed", summary="Detailed system & resource telemetry")
async def health_detailed() -> Dict[str, Any]:
    """Detailed observability and telemetry health check.
    
    Provides real-time stats on process memory (RAM), system CPU, uptime, and MTProto session pool.
    """
    uptime = round(time.time() - START_TIME, 2)

    # Gather memory stats
    memory_stats: Dict[str, Any] = {}
    cpu_stats: Dict[str, Any] = {}

    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        sys_mem = psutil.virtual_memory()

        memory_stats = {
            "process_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "process_vms_mb": round(mem_info.vms / (1024 * 1024), 2),
            "system_total_gb": round(sys_mem.total / (1024 * 1024 * 1024), 2),
            "system_available_gb": round(sys_mem.available / (1024 * 1024 * 1024), 2),
            "system_memory_used_percent": sys_mem.percent,
        }

        cpu_stats = {
            "process_cpu_percent": process.cpu_percent(interval=None),
            "cpu_cores_logical": psutil.cpu_count(logical=True),
            "cpu_cores_physical": psutil.cpu_count(logical=False),
            "system_cpu_percent": psutil.cpu_percent(interval=None),
        }
    except Exception as e:
        memory_stats = {"note": f"psutil metrics unavailable: {str(e)}"}
        cpu_stats = {"note": f"psutil metrics unavailable: {str(e)}"}

    # Gather pool stats
    pool_stats = session_pool_manager.get_pool_status()

    return {
        "status": "healthy",
        "service": API_NAME,
        "version": API_VERSION,
        "uptime_seconds": uptime,
        "system": {
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": sys.version.split()[0],
            "pid": os.getpid(),
        },
        "memory": memory_stats,
        "cpu": cpu_stats,
        "session_pool": pool_stats,
    }
