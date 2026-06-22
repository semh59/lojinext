from __future__ import annotations

import sys
import time

try:
    import resource as _resource  # Unix only

    _RESOURCE_AVAILABLE = True
except ImportError:  # Windows
    _resource = None  # type: ignore[assignment]
    _RESOURCE_AVAILABLE = False

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

# Stale entry budama: worker SIGKILL alırsa task_postrun fire etmez; bu
# dict şişebilir. Bounded cleanup: yeni başlangıçta 10 dakikadan eski
# entry'leri eveict eden lazy purge. Concurrent task sayısı pratikte düşük
# (worker_prefetch_multiplier=1) — risk teorik.
_TASK_ENTRY_TTL_SECONDS = 600  # 10 dk
_task_start_times: dict[str, float] = {}


def _purge_stale_task_entries(now: float) -> None:
    """task_start_times'ten 10dk+ entry'leri sil (lazy GC)."""
    stale = [
        k for k, t in _task_start_times.items() if now - t > _TASK_ENTRY_TTL_SECONDS
    ]
    for k in stale:
        _task_start_times.pop(k, None)


_SLOW_TASK_WARN_MS = 30_000  # 30s
_SLOW_TASK_ERROR_MS = 120_000  # 2min
_MEMORY_ERROR_MB = 800

BEAT_EXPECTED_TASKS: dict[str, int] = {
    "infrastructure.relay_outbox_events": 120,
    "monitoring.error_digest": 600,
    "monitoring.db_health_check": 600,
    "prediction.drain_dlq": 180,
}


def _record_heartbeat_key(task_name: str) -> str:
    return f"beat:last_run:{task_name}"


def setup_celery_probe() -> None:
    """Connect Celery signals. Call once at startup."""
    from celery.signals import (
        task_failure,
        task_postrun,
        task_prerun,
        task_retry,
        task_revoked,
    )

    @task_prerun.connect
    def on_prerun(task_id: str, task, **_):
        if len(_task_start_times) > 1000:
            # Evict oldest — dict is insertion-ordered in Python 3.7+
            try:
                oldest_key = next(iter(_task_start_times))
                _task_start_times.pop(oldest_key, None)
            except StopIteration:
                pass
        now = time.monotonic()
        # Periyodik lazy purge: her N. prerun'da stale entry temizliği
        if len(_task_start_times) % 64 == 0:
            _purge_stale_task_entries(now)
        _task_start_times[task_id] = now

    @task_postrun.connect
    def on_postrun(task_id: str, task, state: str, **_):
        start = _task_start_times.pop(task_id, None)
        if start is not None:
            elapsed_ms = (time.monotonic() - start) * 1000
            if elapsed_ms > _SLOW_TASK_WARN_MS:
                sev = (
                    ErrorSeverity.ERROR
                    if elapsed_ms > _SLOW_TASK_ERROR_MS
                    else ErrorSeverity.WARNING
                )
                from app.infrastructure.monitoring import emit

                emit(
                    ErrorEvent(
                        layer=ErrorLayer.CELERY,
                        category="slow_task",
                        severity=sev,
                        message=(f"Task {task.name} took {elapsed_ms / 1000:.1f}s"),
                        metadata={
                            "task": task.name,
                            "duration_ms": round(elapsed_ms),
                            "state": state,
                        },
                    )
                )

        if state == "SUCCESS":
            _write_heartbeat_sync(task.name)

        try:
            if not _RESOURCE_AVAILABLE:
                raise RuntimeError("resource module not available")
            rss_raw = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss  # type: ignore[attr-defined]
            mem_mb = (
                rss_raw / (1024 * 1024) if sys.platform == "darwin" else rss_raw / 1024
            )
            if mem_mb > _MEMORY_ERROR_MB:
                from app.infrastructure.monitoring import emit

                emit(
                    ErrorEvent(
                        layer=ErrorLayer.CELERY,
                        category="worker_memory_pressure",
                        severity=ErrorSeverity.ERROR,
                        message=(f"Worker RSS {mem_mb:.0f}MB after task {task.name}"),
                        metadata={"rss_mb": round(mem_mb), "task": task.name},
                    )
                )
        except Exception:
            pass

    @task_failure.connect
    def on_failure(task_id: str, exception, traceback, sender, **_):
        _task_start_times.pop(task_id, None)
        max_retries = sender.max_retries
        if max_retries is None:
            # Unlimited retries — escalate after a high retry count
            is_final = sender.request.retries >= 10
        else:
            is_final = sender.request.retries >= max_retries
        from app.infrastructure.monitoring import emit

        exc_name = type(exception).__name__
        emit(
            ErrorEvent(
                layer=ErrorLayer.CELERY,
                category=("task_failure_final" if is_final else "task_failure"),
                severity=(ErrorSeverity.CRITICAL if is_final else ErrorSeverity.ERROR),
                message=(f"{sender.name}: {exc_name}: {str(exception)[:200]}"),
                metadata={
                    "task": sender.name,
                    "retries": sender.request.retries,
                    "max_retries": sender.max_retries,
                    "exception_type": exc_name,
                    "is_final_failure": is_final,
                },
            )
        )

    @task_retry.connect
    def on_retry(request, reason, einfo, **_):
        from app.infrastructure.monitoring import emit

        emit(
            ErrorEvent(
                layer=ErrorLayer.CELERY,
                category="task_retry",
                severity=ErrorSeverity.WARNING,
                message=(
                    f"{request.task}: retry #{request.retries} — {str(reason)[:200]}"
                ),
                metadata={
                    "task": request.task,
                    "retry_count": request.retries,
                    "reason": str(reason)[:200],
                },
            )
        )

    @task_revoked.connect
    def on_revoked(request, terminated, signum, expired, **_):
        from app.infrastructure.monitoring import emit

        emit(
            ErrorEvent(
                layer=ErrorLayer.CELERY,
                category="task_revoked",
                severity=ErrorSeverity.WARNING,
                message=(
                    f"Task {request.task} revoked"
                    f" (terminated={terminated}, expired={expired})"
                ),
                metadata={
                    "task": request.task,
                    "terminated": terminated,
                    "signum": signum,
                    "expired": expired,
                },
            )
        )

    logger.info("Celery probe activated")


_sync_redis: object = None
_sync_redis_lock = None


def _get_sync_redis():
    global _sync_redis, _sync_redis_lock
    import threading

    if _sync_redis_lock is None:
        _sync_redis_lock = threading.Lock()
    if _sync_redis is None:
        with _sync_redis_lock:
            if _sync_redis is None:
                import redis as _r

                from app.config import settings

                globals()["_sync_redis"] = _r.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                    max_connections=2,
                )
    return _sync_redis


def _write_heartbeat_sync(task_name: str) -> None:
    """Write heartbeat to Redis using sync redis-py (Celery prefork, no event loop)."""
    _write_heartbeat_sync_redis(task_name)


def _write_heartbeat_sync_redis(task_name: str) -> None:
    try:
        key = _record_heartbeat_key(task_name)
        r = _get_sync_redis()
        r.set(key, time.time(), ex=7200)
    except Exception as exc:
        logger.debug("Heartbeat sync-redis write failed for %s: %s", task_name, exc)


async def _write_heartbeat_async(key: str) -> None:
    from app.infrastructure.cache.redis_pubsub import set_redis_val

    await set_redis_val(key, time.time(), expire=7200)


async def check_beat_health() -> None:
    """Check all expected beat tasks fired within their window.

    Called by digest task.
    """
    from app.infrastructure.cache.redis_pubsub import get_redis_val
    from app.infrastructure.monitoring import aemit

    for task_name, max_silence_sec in BEAT_EXPECTED_TASKS.items():
        last_val = await get_redis_val(_record_heartbeat_key(task_name))
        last_run = float(last_val) if last_val else None
        if last_run is None or (time.time() - last_run) > max_silence_sec:
            elapsed = round(time.time() - last_run) if last_run else None
            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.CELERY,
                    category="beat_missed",
                    severity=ErrorSeverity.CRITICAL,
                    message=(
                        f"Beat task '{task_name}' not seen for "
                        f"{elapsed or '?'}s (max {max_silence_sec}s)"
                    ),
                    metadata={
                        "task": task_name,
                        "max_silence_sec": max_silence_sec,
                        "last_run_ago_sec": elapsed,
                    },
                )
            )
