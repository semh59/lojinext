"""
Central event bus with typed contract compatibility.
"""

import asyncio
import hashlib
import inspect
import json
import os
import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    cast,
)

import redis

from app.infrastructure.events.event_types import EventType
from app.infrastructure.logging.logger import get_logger
from v2.modules.platform_infra.cache.redis_cache import get_redis_cache

logger = get_logger(__name__)


def _log_task_exception(handler_name: str) -> Callable[["asyncio.Task[None]"], None]:
    """Fire-and-forget task done-callback: logs unhandled exceptions from async handlers."""

    def _on_done(t: "asyncio.Task[None]") -> None:
        if not t.cancelled() and t.exception():
            logger.error(
                "Async event handler %s raised: %s", handler_name, t.exception()
            )

    return _on_done


def publishes(event_type):
    """Attach published event metadata to a function."""

    def decorator(fn):
        setattr(fn, "_publishes", event_type)
        return fn

    return decorator


@dataclass
class Event:
    """Legacy event object kept for compatibility."""

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    event_id: Optional[str] = None
    correlation_id: Optional[str] = None
    version: str = "1.0"

    def __str__(self):
        return f"Event({self.type.value}, source={self.source})"


class EventBus:
    """
    Singleton event bus.
    Supports subscribe/unsubscribe/publish, Redis-backed idempotency and DLQ.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._event_history: List[Event] = []
        self._failed_events: List[Tuple[Event, str, str, datetime]] = []
        self._processed_events: OrderedDict[str, None] = OrderedDict()
        self._max_history = 100
        self._max_dlq_size = 100
        self._max_processed_cache = 1000
        self._max_payload_size = 1024 * 1024
        self._enabled = True
        self._initialized = True

        self._dlq_key = os.getenv("EVENT_DLQ_KEY", "events:dlq")
        self._dedup_ttl = int(os.getenv("EVENT_IDEMPOTENCY_TTL", "86400"))
        self._redis = None
        # Strong-ref set to keep fire-and-forget tasks alive until completion.
        self._bg_tasks: Set[asyncio.Task] = set()  # type: ignore[type-arg]
        self._connect_redis()

    def _connect_redis(self):
        is_testing = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")

        try:
            cache = get_redis_cache()
            if cache.is_redis_available:
                self._redis = cache._redis_client
                return
        except Exception:
            self._redis = None

        from app.config import settings as _s

        if is_testing and not (
            os.getenv("CELERY_BROKER_URL")
            or os.getenv("REDIS_URL")
            or _s.REDIS_USE_SENTINEL
        ):
            self._redis = None
            return

        socket_timeout = float(os.getenv("EVENT_BUS_REDIS_TIMEOUT_SECONDS", "1.0"))
        try:
            if _s.REDIS_USE_SENTINEL:
                # Tier E madde 31 — Sentinel açıkken ham env-var URL fallback'i
                # kullanma (yanlış/tek-instans hedefe düşer); factory'nin
                # Sentinel-farkında yolunu izle.
                from v2.modules.platform_infra.cache.redis_client_factory import (
                    get_sync_redis_client,
                )

                self._redis = get_sync_redis_client(
                    socket_connect_timeout=socket_timeout,
                    socket_timeout=socket_timeout,
                    health_check_interval=0,
                )
            else:
                redis_url = os.getenv("CELERY_BROKER_URL") or os.getenv(
                    "REDIS_URL", "redis://localhost:6379/0"
                )
                self._redis = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=socket_timeout,
                    socket_timeout=socket_timeout,
                    health_check_interval=0,
                )
            self._redis.ping()
        except Exception as exc:
            logger.warning(f"Redis connection for EventBus failed, fallback: {exc}")
            self._redis = None

    def _validate_event(self, event: Event):
        if not event or not event.type:
            raise ValueError("Invalid event: Event must have a type")
        if event.data is None:
            event.data = {}
        payload_size = sys.getsizeof(str(event.data))
        if payload_size > self._max_payload_size:
            raise ValueError(
                f"Event payload too large: {payload_size} bytes (max {self._max_payload_size})"
            )

    def _get_event_id(self, event: Event) -> str:
        if getattr(event, "event_id", None):
            return event.event_id
        data_str = (
            f"{event.type.value}:{event.timestamp.isoformat()}:{str(event.data)[:100]}"
        )
        return hashlib.md5(data_str.encode()).hexdigest()[:16]

    def _is_duplicate(self, event: Event) -> bool:
        event_id = self._get_event_id(event)
        if self._redis:
            try:
                added = self._redis.set(
                    f"events:processed:{event_id}", 1, ex=self._dedup_ttl, nx=True
                )
                if not added:
                    logger.debug(f"Duplicate event detected (redis): {event_id}")
                    return True
            except Exception as exc:
                logger.warning(f"Redis dedup failed, fallback to memory: {exc}")

        if event_id in self._processed_events:
            logger.debug(f"Duplicate event detected (memory): {event_id}")
            return True

        self._processed_events[event_id] = None
        while len(self._processed_events) > self._max_processed_cache:
            self._processed_events.popitem(last=False)
        return False

    def _handle_failure(self, event: Event, callback_name: str, error: str):
        if len(self._failed_events) >= self._max_dlq_size:
            self._failed_events.pop(0)
        self._failed_events.append(
            (event, callback_name, error, datetime.now(timezone.utc))
        )
        if self._redis:
            try:
                payload = {
                    "event_id": self._get_event_id(event),
                    "callback": callback_name,
                    "error": error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": {
                        "type": event.type.value,
                        "data": event.data,
                        "source": event.source,
                        "correlation_id": event.correlation_id,
                    },
                }
                self._redis.lpush(
                    self._dlq_key, json.dumps(payload, ensure_ascii=False)
                )
            except Exception as exc:
                logger.error(f"Failed to push event to DLQ: {exc}")

    def subscribe(
        self, event_type: EventType, callback: Callable[[Event], None]
    ) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)

    def unsubscribe(
        self, event_type: EventType, callback: Callable[[Event], None]
    ) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb != callback
            ]

    def publish(self, event: Event):
        self._validate_event(event)
        if self._is_duplicate(event):
            return

        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        callbacks = self._subscribers.get(event.type, [])
        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        logger.warning(
                            "No running event loop — async handler %s skipped for %s",
                            cb.__name__,
                            event.type.value,
                        )
                        continue
                    task: "asyncio.Task[None]" = loop.create_task(
                        cast(Coroutine[Any, Any, None], cb(event))
                    )
                    self._bg_tasks.add(task)
                    task.add_done_callback(self._bg_tasks.discard)
                    task.add_done_callback(_log_task_exception(cb.__name__))
                else:
                    cb(event)
            except Exception as exc:
                logger.exception(f"Event handler failed: {cb.__name__}: {exc}")
                self._handle_failure(event, cb.__name__, str(exc))

    async def publish_async(self, event: Event):
        self._validate_event(event)
        if self._is_duplicate(event):
            return

        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        callbacks = self._subscribers.get(event.type, [])
        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    await cast("Awaitable[Any]", cb(event))
                else:
                    cb(event)
            except Exception as exc:
                logger.exception(f"Event handler failed: {cb.__name__}: {exc}")
                self._handle_failure(event, cb.__name__, str(exc))

    async def publish_simple_async(
        self,
        event_type: "EventType",
        **data: Any,
    ) -> None:
        """Convenience wrapper: build an Event from keyword args and publish async."""
        await self.publish_async(Event(type=event_type, data=dict(data)))

    def clear_history(self):
        self._event_history.clear()

    def reset_all_for_tests(self):
        self._subscribers.clear()
        self._event_history.clear()
        self._failed_events.clear()
        self._processed_events.clear()
        # Redis dedup keys de temizlenmeli (aksi halde aynı event_id'li
        # publish suite'in başka bir testinde duplicate sayılır).
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter("events:processed:*"):
                    self._redis.delete(key)
                self._redis.delete(self._dlq_key)
            except Exception as exc:
                logger.warning(f"EventBus Redis reset failed: {exc}")


def get_event_bus() -> EventBus:
    return EventBus()
