"""FastAPI Router for Enterprise Asynchronous Scraping Jobs and Session Pool Management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.queue import job_queue_manager
from app.core.session_pool import session_pool_manager
from app.models import (
    AddSessionRequest,
    BatchJobSubmitRequest,
    BatchJobSubmitResponse,
    JobResultResponse,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    PoolStatusResponse,
)

router = APIRouter(tags=["Enterprise Asynchronous Queue & Session Pool"])


@router.post(
    "/jobs/scrape-chat",
    response_model=JobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Async Scraping Job",
    description="Asynchronously queue a scraping job for a private or public chat. Returns immediately with a tracking job_id.",
)
async def submit_scrape_job(payload: JobSubmitRequest, request: Request) -> JobSubmitResponse:
    """Enqueue a new scraping job into the asynchronous worker queue."""
    if session_pool_manager.total_sessions == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session pool has 0 accounts configured. Please ensure .env has valid credentials.",
        )

    job_id = await job_queue_manager.enqueue(
        chat_id=payload.chat_id,
        limit=payload.limit,
        search_query=payload.search_query,
    )

    base_url = str(request.base_url).rstrip("/")
    status_url = f"{base_url}/api/v1/telegram/jobs/{job_id}"

    return JobSubmitResponse(
        status="queued",
        job_id=job_id,
        chat_id=payload.chat_id,
        target_limit=payload.limit,
        message="Job successfully queued. Check status via status_url.",
        status_url=status_url,
    )


@router.post(
    "/jobs/scrape-batch",
    response_model=BatchJobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Batch of Scraping Jobs",
    description="Queue multiple chats to be scraped concurrently across available sessions.",
)
async def submit_batch_scrape_jobs(payload: BatchJobSubmitRequest, request: Request) -> BatchJobSubmitResponse:
    """Enqueue multiple chat scraping jobs in one request."""
    if session_pool_manager.total_sessions == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session pool has 0 accounts configured.",
        )

    base_url = str(request.base_url).rstrip("/")
    queued_jobs = []

    for chat in payload.chats:
        job_id = await job_queue_manager.enqueue(
            chat_id=chat,
            limit=payload.limit_per_chat,
        )
        queued_jobs.append({
            "job_id": job_id,
            "chat_id": chat,
            "target_limit": payload.limit_per_chat,
            "status_url": f"{base_url}/api/v1/telegram/jobs/{job_id}",
        })

    return BatchJobSubmitResponse(
        status="queued",
        total_jobs=len(queued_jobs),
        jobs=queued_jobs,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get Job Status & Progress",
    description="Check the current progress, status, and metrics of a submitted scraping job.",
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Retrieve job execution progress."""
    job = job_queue_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scrape job with ID '{job_id}' not found.",
        )

    return JobStatusResponse(**job.to_dict())


@router.get(
    "/jobs/{job_id}/result",
    response_model=JobResultResponse,
    summary="Get Completed Job Dataset",
    description="Retrieve the complete array of scraped messages once the job is marked 'completed'.",
)
async def get_job_result(job_id: str) -> JobResultResponse:
    """Retrieve full message dataset for a completed job."""
    job = job_queue_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scrape job with ID '{job_id}' not found.",
        )

    if job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job failed: {job.error_message}",
        )

    return JobResultResponse(
        status="success",
        job_id=job.job_id,
        chat_id=job.chat_id,
        total_messages=len(job.results),
        completed_at=job.completed_at,
        messages=job.results,
    )


@router.get(
    "/jobs",
    summary="List Recent Scraping Jobs",
    description="Retrieve a summary list of all recent background jobs and their states.",
)
async def list_recent_jobs(
    limit: int = Query(default=50, ge=1, le=200, description="Max jobs to return")
) -> List[Dict[str, Any]]:
    """List recent scraping jobs."""
    return job_queue_manager.get_all_jobs(limit=limit)


@router.get(
    "/pool/status",
    response_model=PoolStatusResponse,
    summary="Get Multi-Account Pool Health",
    description="Returns real-time health metrics of all active and sleeping Telegram accounts in the session pool.",
)
async def get_pool_status() -> PoolStatusResponse:
    """Check multi-account session pool state and cooldowns."""
    return PoolStatusResponse(**session_pool_manager.get_pool_status())


@router.post(
    "/pool/add-session",
    summary="Add Session to Multi-Account Pool",
    description="Dynamically register a new Telegram account session into the pool at runtime without restarting the server.",
)
async def add_session_to_pool(payload: AddSessionRequest) -> Dict[str, Any]:
    """Register and connect a new account session."""
    success = await session_pool_manager.add_session(
        session_id=payload.session_id,
        session_string=payload.session_string,
        name=payload.name,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect session. Please verify that the session string is valid.",
        )

    return {
        "status": "success",
        "message": f"Session '{payload.session_id}' ({payload.name}) successfully added to active pool.",
        "pool_status": session_pool_manager.get_pool_status(),
    }
