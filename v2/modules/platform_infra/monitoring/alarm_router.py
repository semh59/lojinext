from __future__ import annotations

import asyncio
import statistics
import threading as _threading
from typing import TYPE_CHECKING, Awaitable, cast

from v2.modules.platform_infra.logging.logger import get_logger

if TYPE_CHECKING:
    from v2.modules.platform_infra.monitoring.models import ErrorEvent

logger = get_logger(__name__)

_DEDUP_CRITICAL_SECONDS = 900  # 15 min — don't resend same critical within this window
_DEDUP_ERROR_SECONDS = 300  # 5 min — don't resend same error within this window
_DEDUP_WINDOW_SECONDS = _DEDUP_CRITICAL_SECONDS  # backwards-compat alias
_ANOMALY_WINDOW_SIZE = 12  # 12×1h = 12h rolling window (hourly buckets)
_Z_SCORE_THRESHOLD = 3.0
_MIN_SAMPLES = 6  # Need at least 6 data points for meaningful Z-score

# Fix 3: module-level set keeps fire-and-forget tasks alive until completion
_bg_tasks: set[asyncio.Task] = set()


def _on_notify_task_done(task: asyncio.Task) -> None:
    """Done callback for fire-and-forget notify tasks — retrieves any
    exception so it never surfaces as an asyncio "unretrieved" warning,
    then removes the task from the tracking set."""
    _bg_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.debug("notify_error task raised: %s", exc)


async def drain_bg_tasks() -> None:
    """Cancel + await any in-flight notify_error tasks (Sentry LOJINEXT-1C5).

    Nothing awaited these fire-and-forget tasks before app shutdown — if
    engine.dispose()/loop close raced a task still mid-DNS-lookup (e.g.
    telegram-ops-bot unreachable during a container recreate), the
    executor-thread Future backing that lookup would eventually resolve
    with no one left to retrieve it, surfacing as asyncio's default
    "Future exception was never retrieved" handler (reproduced: a real
    event carried a bare gaierror for exactly this reason). Call from the
    app lifespan's shutdown path, before engine.dispose().
    """
    pending = [t for t in list(_bg_tasks) if not t.done()]
    if not pending:
        return
    for t in pending:
        t.cancel()
    results = await asyncio.gather(*pending, return_exceptions=True)
    for t, result in zip(pending, results):
        if isinstance(result, Exception) and not isinstance(
            result, asyncio.CancelledError
        ):
            logger.debug("Dangling notify task raised on shutdown: %s", result)


class AnomalyDetector:
    """Z-score spike detector. Reads 12h rolling window of hourly counters."""

    def _compute_z_score(self, counts: list[int]) -> float | None:
        if len(counts) < _MIN_SAMPLES + 1:
            return None
        baseline = counts[:-1]
        current = counts[-1]
        mean = statistics.mean(baseline)
        try:
            stdev = statistics.stdev(baseline)
        except statistics.StatisticsError:
            return None
        if stdev == 0:
            return 0.0
        return (current - mean) / stdev

    async def check(self, layer: str, category: str) -> bool:
        """Returns True if current window shows a statistical anomaly (Z > 3)."""
        import datetime

        from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

        mgr = get_pubsub_manager()
        # Fix 5 (event_bus): use public .redis property
        if mgr.redis is None:
            return False
        try:
            # Fix 2: use timezone-aware utc datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            # Fix 4: collect all keys first, then fetch in a single mget call
            keys = []
            for h in range(_ANOMALY_WINDOW_SIZE - 1, -1, -1):
                dt = now - datetime.timedelta(hours=h)
                keys.append(
                    f"error:hourly:{layer}:{category}:{dt.strftime('%Y%m%d%H')}"
                )
            vals = await mgr.redis.mget(*keys)  # single RTT
            counts = [int(v) if v else 0 for v in vals]
            z = self._compute_z_score(counts)
            return z is not None and z > _Z_SCORE_THRESHOLD
        except Exception as exc:
            logger.warning("AnomalyDetector check failed: %s", exc)
            return False


class AlarmRouter:
    """Routes ErrorEvents to Telegram / Sentry based on severity + anomaly detection."""

    def __init__(self) -> None:
        self._anomaly = AnomalyDetector()
        self._sent_critical: dict[str, float] = {}  # fingerprint → sent_at monotonic
        self._sent_error: dict[str, float] = {}  # fingerprint → sent_at monotonic

    async def route(self, event: ErrorEvent) -> None:
        import time

        from v2.modules.platform_infra.monitoring.models import ErrorSeverity

        # Prune stale dedup entries to prevent unbounded growth
        now_mono = time.monotonic()
        self._sent_critical = {
            k: v
            for k, v in self._sent_critical.items()
            if now_mono - v < 2 * _DEDUP_CRITICAL_SECONDS
        }
        self._sent_error = {
            k: v
            for k, v in self._sent_error.items()
            if now_mono - v < 2 * _DEDUP_ERROR_SECONDS
        }

        is_anomaly = await self._anomaly.check(event.layer.value, event.category)
        effective_severity = event.severity

        if is_anomaly and effective_severity != ErrorSeverity.CRITICAL:
            effective_severity = ErrorSeverity.CRITICAL
            logger.warning(
                "Anomaly detected (Z>3) for %s/%s — escalating to CRITICAL",
                event.layer.value,
                event.category,
            )

        if effective_severity == ErrorSeverity.CRITICAL:
            last_sent = self._sent_critical.get(event.fingerprint)
            if (
                last_sent is None
                or time.monotonic() - last_sent > _DEDUP_CRITICAL_SECONDS
            ):
                await self._send_immediate(event, is_anomaly=is_anomaly)
                self._sent_critical[event.fingerprint] = time.monotonic()
        elif effective_severity == ErrorSeverity.ERROR:
            last_sent = self._sent_error.get(event.fingerprint)
            if last_sent is None or time.monotonic() - last_sent > _DEDUP_ERROR_SECONDS:
                await self._send_immediate(event, is_anomaly=False)
                self._sent_error[event.fingerprint] = time.monotonic()
            await self._increment_digest_counter(event)
        elif (
            effective_severity == ErrorSeverity.WARNING
            and self._warning_notify_enabled()
        ):
            await self._increment_digest_counter(event)
        # INFO: stored in DB by EventBus only

    @staticmethod
    def _warning_notify_enabled() -> bool:
        try:
            from app.config import settings

            return settings.NOTIFY_MIN_LEVEL.lower() == "warning"
        except Exception:
            return False

    async def _send_immediate(
        self, event: ErrorEvent, is_anomaly: bool = False
    ) -> None:
        prefix = "🔺 ANOMALİ " if is_anomaly else ""
        layer_emoji = {
            "db": "🗄️",
            "celery": "⚙️",
            "api": "🌐",
            "service": "🔧",
            "frontend": "🖥️",
            "external": "🔌",
            "security": "🔒",
            "ml": "🤖",
        }.get(event.layer.value, "❗")

        msg = (
            f"{prefix}{layer_emoji} **{event.layer.value.upper()}**"
            f" {event.severity.value}\n"
            f"`{event.category}` — {event.message[:300]}\n"
            f"trace: `{event.trace_id or 'n/a'}`"
        )
        from v2.modules.notification.public import notify_error

        task = asyncio.create_task(
            notify_error(
                level=event.severity.value,
                message=msg,
                path=event.path,
                trace_id=event.trace_id,
            )
        )
        _bg_tasks.add(task)
        task.add_done_callback(_on_notify_task_done)

        # Skip Sentry for events that originated from Sentry to prevent a feedback loop:
        # capture_message → _sentry_before_send emits sentry_capture CRITICAL → here again.
        if event.category != "sentry_capture":
            try:
                import sentry_sdk

                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("layer", event.layer.value)
                    scope.set_tag("category", event.category)
                    scope.set_context("error_event", event.to_dict())
                    sentry_sdk.capture_message(event.message, level="fatal")
            except Exception as exc:
                logger.debug("Sentry capture failed: %s", exc)

    async def _increment_digest_counter(self, event: ErrorEvent) -> None:
        from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

        mgr = get_pubsub_manager()
        # Fix 5 (event_bus): use public .redis property
        if mgr.redis is None:
            return
        try:
            key = f"error:digest:{event.layer.value}:{event.category}"
            await cast("Awaitable[int]", mgr.redis.hincrby(key, "count", 1))
            await cast(
                "Awaitable[int]",
                mgr.redis.hset(
                    key,
                    mapping={
                        "severity": event.severity.value,
                        "message_sample": event.message[:200],
                    },
                ),
            )
            await mgr.redis.expire(key, 600)  # 10 min TTL — cleared after digest sends
        except Exception as exc:
            logger.warning("AlarmRouter digest counter failed: %s", exc)


_router: AlarmRouter | None = None
_router_lock = _threading.Lock()


def get_alarm_router() -> AlarmRouter:
    global _router
    if _router is None:
        with _router_lock:
            if _router is None:
                _router = AlarmRouter()
    return _router
