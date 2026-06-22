"""
Async background job manager.

Job state is stored in Redis so status is visible across all workers
and survives short worker restarts. Keys auto-expire after 24 h
(no manual cleanup needed). In-process _tasks dict is kept for
awaiting task completion in tests/callers that need it.
"""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_JOB_KEY_PREFIX = "bg_job:"
_JOB_TTL_SECONDS = 86400  # 24 h


class BackgroundJobManager:
    _instance: Optional["BackgroundJobManager"] = None
    _cls_lock = threading.Lock()
    _redis_override: Any = None  # injectable fake for unit tests

    # mypy: instance-level attributes
    _tasks: Dict[str, "asyncio.Task[Any]"]
    _redis: Any

    def __new__(cls) -> "BackgroundJobManager":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._tasks = {}
                    if cls._redis_override is not None:
                        inst._redis = cls._redis_override
                    else:
                        import redis as redis_lib

                        from app.config import settings

                        inst._redis = redis_lib.from_url(
                            settings.REDIS_URL, decode_responses=True
                        )
                    cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Internal Redis helpers
    # ------------------------------------------------------------------

    def _key(self, job_id: str) -> str:
        return f"{_JOB_KEY_PREFIX}{job_id}"

    def _read_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        raw = self._redis.get(self._key(job_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def _write_job(self, job_id: str, data: Dict[str, Any]) -> None:
        self._redis.set(self._key(job_id), json.dumps(data), ex=_JOB_TTL_SECONDS)

    def _update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        existing = self._read_job(job_id) or {}
        existing.update(updates)
        self._write_job(job_id, existing)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(self, func: Callable, *args, **kwargs) -> str:
        """
        Submit a job for background execution.

        Returns:
            str: Unique job identifier (UUID).
        """
        job_id = str(uuid.uuid4())
        self._write_job(
            job_id,
            {
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": None,
            },
        )

        async def _wrapper() -> None:
            self._update_job(job_id, {"status": "running"})
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                try:
                    safe_result: Any = json.loads(json.dumps(result, default=str))
                except (TypeError, ValueError):
                    safe_result = str(result)

                self._update_job(
                    job_id,
                    {
                        "status": "completed",
                        "result": safe_result,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                logger.info("Background job %s completed successfully.", job_id)
            except Exception as exc:
                logger.error("Background job %s failed: %s", job_id, exc)
                self._update_job(
                    job_id,
                    {
                        "status": "failed",
                        "error": str(exc),
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

        task = asyncio.create_task(_wrapper())
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Return the current job status snapshot."""
        data = self._read_job(job_id)
        if data is None:
            return {
                "id": job_id,
                "status": "unknown",
                "result": None,
                "error": None,
                "created_at": None,
                "finished_at": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "id": job_id,
            "status": data.get("status", "unknown"),
            "result": data.get("result"),
            "error": data.get("error"),
            "created_at": data.get("created_at"),
            "finished_at": data.get("finished_at"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def cleanup(self, max_age_seconds: int = 3600) -> None:
        """No-op: Redis TTL (24 h) handles automatic expiry for all workers."""


def get_job_manager() -> BackgroundJobManager:
    """Return the process-wide background job manager singleton."""
    return BackgroundJobManager()
