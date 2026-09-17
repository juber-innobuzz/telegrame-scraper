"""Asynchronous Task Queue & Background Worker Pool with Redis & In-Memory Fallback."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Union

from telethon import errors

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from app.config import REDIS_ENABLED, REDIS_URL
from app.core.session_pool import session_pool_manager
from app.models import PrivateMessageItem

logger = logging.getLogger("telegram_job_queue")

REDIS_QUEUE_KEY = "telegram:job_queue"
REDIS_JOB_PREFIX = "telegram:job:"
REDIS_RESULT_PREFIX = "telegram:job_result:"


class ScrapeJob:
    """Represents an asynchronous scraping job."""

    def __init__(
        self,
        job_id: str,
        chat_id: Union[int, str],
        limit: int = 100,
        search_query: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> None:
        self.job_id: str = job_id
        self.chat_id: Union[int, str] = chat_id
        self.limit: int = limit
        self.search_query: Optional[str] = search_query

        # Status & Progress
        self.status: str = "queued"  # queued | processing | completed | failed | rate_limited_retry
        self.progress_percent: float = 0.0
        self.messages_scraped: int = 0
        self.assigned_session_id: Optional[str] = None
        self.error_message: Optional[str] = None

        # Timing
        self.created_at: str = created_at or datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None

        # Results buffer
        self.results: List[PrivateMessageItem] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert job state to JSON serializable dictionary (without heavy payload)."""
        return {
            "job_id": self.job_id,
            "chat_id": self.chat_id,
            "target_limit": self.limit,
            "search_query": self.search_query,
            "status": self.status,
            "progress_percent": round(self.progress_percent, 2),
            "messages_scraped": self.messages_scraped,
            "assigned_session_id": self.assigned_session_id,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScrapeJob:
        """Construct ScrapeJob from dictionary."""
        job = cls(
            job_id=data["job_id"],
            chat_id=data["chat_id"],
            limit=data.get("target_limit", 100),
            search_query=data.get("search_query"),
            created_at=data.get("created_at"),
        )
        job.status = data.get("status", "queued")
        job.progress_percent = data.get("progress_percent", 0.0)
        job.messages_scraped = data.get("messages_scraped", 0)
        job.assigned_session_id = data.get("assigned_session_id")
        job.error_message = data.get("error_message")
        job.started_at = data.get("started_at")
        job.completed_at = data.get("completed_at")
        return job


class JobQueueManager:
    """Manages asynchronous scraping job queuing, Redis storage, and distributed worker execution."""

    def __init__(self, concurrency: int = 3) -> None:
        self.concurrency: int = concurrency
        self._memory_queue: asyncio.Queue[str] = asyncio.Queue()
        self._memory_jobs: Dict[str, ScrapeJob] = {}
        self._workers: List[asyncio.Task] = []
        self._is_running: bool = False
        self.redis_client: Optional[Any] = None

    async def start(self) -> None:
        """Start the background worker tasks and connect to Redis if configured."""
        if self._is_running:
            return

        # Attempt Redis connection if REDIS_URL is provided
        if REDIS_ENABLED and REDIS_URL and redis:
            try:
                self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                await self.redis_client.ping()
                logger.info("Connected to Redis task queue at %s", REDIS_URL)
            except Exception as exc:
                logger.warning("Failed to connect to Redis (%s). Falling back to In-Memory Queue.", exc)
                self.redis_client = None

        self._is_running = True
        self._workers = [
            asyncio.create_task(self._worker_loop(worker_idx=i + 1))
            for i in range(self.concurrency)
        ]
        logger.info(
            "JobQueueManager started with %d concurrent background workers (Backend: %s).",
            self.concurrency,
            "Redis" if self.redis_client else "In-Memory",
        )

    async def stop(self) -> None:
        """Gracefully stop worker tasks and close Redis."""
        self._is_running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None

        logger.info("JobQueueManager stopped.")

    async def enqueue(
        self,
        chat_id: Union[int, str],
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> str:
        """Create and enqueue a new scraping job. Returns job_id."""
        job_id = str(uuid.uuid4())
        job = ScrapeJob(job_id=job_id, chat_id=chat_id, limit=limit, search_query=search_query)

        # Store state
        self._memory_jobs[job_id] = job
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"{REDIS_JOB_PREFIX}{job_id}",
                    json.dumps(job.to_dict()),
                    ex=86400,  # 24 hour TTL
                )
                await self.redis_client.lpush(REDIS_QUEUE_KEY, job_id)
            except Exception as e:
                logger.error("Redis enqueue error (%s). Using in-memory queue fallback.", e)
                await self._memory_queue.put(job_id)
        else:
            await self._memory_queue.put(job_id)

        logger.info("Enqueued scrape job %s for chat %s (target: %d messages)", job_id, chat_id, limit)
        return job_id

    async def _save_job_state(self, job: ScrapeJob) -> None:
        """Save job state to Redis and in-memory cache."""
        self._memory_jobs[job.job_id] = job
        if self.redis_client:
            try:
                await self.redis_client.set(
                    f"{REDIS_JOB_PREFIX}{job.job_id}",
                    json.dumps(job.to_dict()),
                    ex=86400,
                )
                if job.status == "completed" and job.results:
                    # Save results in Redis with TTL
                    results_json = json.dumps([msg.model_dump() for msg in job.results])
                    await self.redis_client.set(
                        f"{REDIS_RESULT_PREFIX}{job.job_id}",
                        results_json,
                        ex=86400,
                    )
            except Exception as e:
                logger.error("Failed to persist job %s state to Redis: %s", job.job_id, e)

    def get_job(self, job_id: str) -> Optional[ScrapeJob]:
        """Retrieve job state by ID (from memory cache)."""
        return self._memory_jobs.get(job_id)

    def get_all_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve latest jobs summary."""
        all_jobs = list(self._memory_jobs.values())
        all_jobs.reverse()
        return [j.to_dict() for j in all_jobs[:limit]]

    async def _worker_loop(self, worker_idx: int) -> None:
        """Continuous worker loop processing queued jobs."""
        logger.info("Worker #%d started and listening for jobs...", worker_idx)
        while self._is_running:
            try:
                job_id = None
                if self.redis_client:
                    try:
                        # Blocking pop with 1s timeout from Redis queue
                        res = await self.redis_client.brpop(REDIS_QUEUE_KEY, timeout=1)
                        if res:
                            job_id = res[1]
                    except Exception as e:
                        logger.error("Redis pop error: %s", e)
                        await asyncio.sleep(1.0)
                else:
                    try:
                        job_id = await asyncio.wait_for(self._memory_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue

                if not job_id:
                    continue

                job = self._memory_jobs.get(job_id)
                if not job and self.redis_client:
                    # Fetch from Redis if not in local worker memory
                    raw = await self.redis_client.get(f"{REDIS_JOB_PREFIX}{job_id}")
                    if raw:
                        job = ScrapeJob.from_dict(json.loads(raw))
                        self._memory_jobs[job_id] = job

                if not job:
                    if not self.redis_client:
                        self._memory_queue.task_done()
                    continue

                await self._process_job(job, worker_idx)
                if not self.redis_client:
                    self._memory_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unhandled error in worker #%d: %s", worker_idx, exc)
                await asyncio.sleep(1.0)

    async def _process_job(self, job: ScrapeJob, worker_idx: int) -> None:
        """Process a single scraping job with chunking, pacing, and automatic session rotation."""
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc).isoformat()
        await self._save_job_state(job)

        logger.info("Worker #%d processing job %s (Target: %d messages from %s)", worker_idx, job.job_id, job.limit, job.chat_id)

        peer: Union[int, str] = job.chat_id
        if isinstance(job.chat_id, str) and job.chat_id.lstrip("-").isdigit():
            peer = int(job.chat_id)

        offset_id = 0
        total_needed = job.limit

        while len(job.results) < total_needed and self._is_running:
            # 1. Lease an available session from the pool
            session = await session_pool_manager.lease_session()
            if not session:
                job.status = "rate_limited_retry"
                await self._save_job_state(job)
                await asyncio.sleep(2.0)
                continue

            job.assigned_session_id = session.session_id
            chunk_limit = min(100, total_needed - len(job.results))

            try:
                # 2. Safely fetch chunk using the leased account
                messages, count, next_offset = await session_pool_manager.safe_fetch_chunk(
                    session=session,
                    peer=peer,
                    limit=chunk_limit,
                    offset_id=offset_id,
                    search_query=job.search_query,
                )

                if count == 0:
                    break

                job.results.extend(messages)
                job.messages_scraped = len(job.results)
                job.progress_percent = min(100.0, (job.messages_scraped / total_needed) * 100.0)
                await self._save_job_state(job)

                if next_offset:
                    offset_id = next_offset

                if count < chunk_limit:
                    break

            except errors.FloodWaitError as e:
                logger.warning(
                    "FloodWait on session %s during job %s (%ds). Rotating account...",
                    session.session_id,
                    job.job_id,
                    e.seconds,
                )
                job.status = "rate_limited_retry"
                await self._save_job_state(job)
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error("Error scraping chunk for job %s: %s", job.job_id, e)
                job.error_message = str(e)
                job.status = "failed"
                await self._save_job_state(job)
                await session_pool_manager.release_session(session)
                return

            finally:
                await session_pool_manager.release_session(session)

        # Mark job completed
        job.status = "completed"
        job.progress_percent = 100.0
        job.completed_at = datetime.now(timezone.utc).isoformat()
        await self._save_job_state(job)
        logger.info(
            "Job %s completed successfully! Scraped %d messages from chat %s.",
            job.job_id,
            job.messages_scraped,
            job.chat_id,
        )


# Global singleton queue manager
job_queue_manager = JobQueueManager(concurrency=3)
