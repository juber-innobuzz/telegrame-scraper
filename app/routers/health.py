"""Health and Telemetry Endpoint Router."""

from __future__ import annotations

import os
import platform
import sys
import time
from typing import Any, Dict
from fastapi import APIRouter

from app.config import API_NAME, API_VERSION, MAX_CONNECTIONS, MAX_KEEPALIVE_CONNECTIONS, REQUEST_TIMEOUT
from app.models import HealthDetailedResponse

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
    }


@router.get("/health/detailed", response_model=HealthDetailedResponse, summary="Detailed system & resource telemetry")
async def health_detailed() -> Dict[str, Any]:
    """Detailed observability and telemetry health check.
    
    Provides real-time stats on process memory (RAM), system CPU, uptime, and HTTP connection pools.
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
        "http_pool": {
            "request_timeout_sec": REQUEST_TIMEOUT,
            "max_connections": MAX_CONNECTIONS,
            "max_keepalive_connections": MAX_KEEPALIVE_CONNECTIONS,
            "status": "active",
        },
    }
