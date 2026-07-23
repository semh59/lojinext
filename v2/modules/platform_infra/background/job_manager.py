"""
Async background job manager.

`app/infrastructure/background/job_manager.py`'den dalga 17 (platform_infra)
denetiminde taşındı — 4 bağımsız modül + app/api/deps.py tarafından
kullanılıyor, zaten platform_infra'nın cache/database iç mekanizmalarına
bağımlıydı.

Job state is stored in Redis so status is visible across all workers
and survives short worker restarts. Keys auto-expire after 24 h
(no manual cleanup needed). In-process _tasks dict is kept for
awaiting task completion in tests/callers that need it.
"""

import asyncio
import contextlib
import contextvars
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class AsyncJobStatus(str, Enum):
    """Public-facing async-job status contract returned to clients.

    2026-07-01 prod-grade denetimi P2 (Tier B madde 9): bu 3 değer eskiden
    `admin_predictions.py`/`fuel.py`/`trips.py`'de (6 yerde) ayrı ayrı
    string literal olarak tekrarlanıyordu, merkezi bir tanım yoktu.

    NOT: bu, `BackgroundJobManager`'ın kendi İÇ durum vokabüleriyle
    (pending/running/completed/failed, Redis'te saklanan) KASITLI olarak
    farklı — bu enum sadece 202-submission ve polling yanıtlarındaki
    PUBLIC sözleşmeyi temsil ediyor. `get_status()`'un iç `data["status"]`
    değerini bu enum'a çeviren normalizasyon (`trips.py::get_task_status`)
    kasıtlı bırakıldı, DEĞİŞTİRİLMEDİ.
    """

    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


_JOB_KEY_PREFIX = "bg_job:"
_JOB_TTL_SECONDS = 86400  # 24 h
_HEARTBEAT_INTERVAL_SECONDS = 30
# 2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 17): job durumu sadece
# in-process asyncio task'a bağlıydı — worker restart olduğunda Redis'teki
# kayıt sonsuza dek "running" kalıyor, frontend useTaskStatus sonsuz poll
# ediyordu. Heartbeat bu eşikten daha eskiyse worker'ın öldüğü varsayılır.
_STALE_RUNNING_SECONDS = 300


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
                        from app.config import settings
                        from v2.modules.platform_infra.cache.redis_client_factory import (
                            get_sync_redis_client,
                        )

                        inst._redis = get_sync_redis_client(
                            decode_responses=True, url=settings.REDIS_URL
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
                "heartbeat_at": None,
            },
        )

        async def _heartbeat_loop() -> None:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)
                self._update_job(
                    job_id, {"heartbeat_at": datetime.now(timezone.utc).isoformat()}
                )

        async def _wrapper() -> None:
            self._update_job(
                job_id,
                {
                    "status": "running",
                    "heartbeat_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            heartbeat_task = asyncio.create_task(_heartbeat_loop())
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
            finally:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task

        # asyncio.create_task() copies the CALLER's context by default —
        # since the request handler's UnitOfWork is still active (its
        # _session_ctx contextvar is set) at the moment submit() runs, the
        # background task would otherwise "re-enter" and REUSE the
        # request's AsyncSession (see UnitOfWork.__aenter__'s reuse-on-
        # re-entry logic) instead of opening its own. That request session
        # gets torn down once the endpoint returns, while this task keeps
        # running concurrently on it — asyncpg raises "cannot perform
        # operation: another operation is in progress" (caught live in CI,
        # run 29192467229: GET /trips/{id}/cost-analysis's reconcile_costs).
        # Copy the context (keeps correlation_id/user_id/request_path for
        # audit-log attribution) but reset _session_ctx to its default
        # (None) so func's own UnitOfWork opens a fresh, independent
        # session instead of inheriting the request's.
        from v2.modules.platform_infra.database.db_session import _session_ctx

        task_ctx = contextvars.copy_context()
        task_ctx.run(_session_ctx.set, None)
        task = asyncio.create_task(_wrapper(), context=task_ctx)
        self._tasks[job_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Return the current job status snapshot.

        Bir job "running" durumundayken heartbeat'i `_STALE_RUNNING_SECONDS`
        eşiğinden daha eskiyse, worker'ın (crash/redeploy ile) job'ı
        bitirmeden öldüğü varsayılır — kayıt kendiliğinden "failed"e
        çevrilir, aksi halde frontend sonsuza dek "running" görüp poll
        etmeye devam ederdi.
        """
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

        if data.get("status") == "running":
            heartbeat_raw = data.get("heartbeat_at") or data.get("created_at")
            is_stale = True
            if heartbeat_raw:
                try:
                    heartbeat_at = datetime.fromisoformat(heartbeat_raw)
                    age = datetime.now(timezone.utc) - heartbeat_at
                    is_stale = age > timedelta(seconds=_STALE_RUNNING_SECONDS)
                except ValueError:
                    is_stale = True
            if is_stale:
                data = {
                    **data,
                    "status": "failed",
                    "error": (
                        "Worker restarted mid-job (stale heartbeat) — "
                        "job'ın gerçek sonucu bilinmiyor, yeniden tetikleyin."
                    ),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
                self._write_job(job_id, data)

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
