"""Coverage tests for app/infrastructure/monitoring/celery_probe.py"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _purge_stale_task_entries
# ---------------------------------------------------------------------------


def test_purge_removes_old_entries():
    from app.infrastructure.monitoring import celery_probe as cp

    cp._task_start_times.clear()
    old_time = time.monotonic() - 700  # older than 600s TTL
    cp._task_start_times["stale-id"] = old_time
    cp._task_start_times["fresh-id"] = time.monotonic()

    cp._purge_stale_task_entries(time.monotonic())

    assert "stale-id" not in cp._task_start_times
    assert "fresh-id" in cp._task_start_times
    cp._task_start_times.clear()


def test_purge_empty_dict():
    from app.infrastructure.monitoring import celery_probe as cp

    cp._task_start_times.clear()
    # Should not raise
    cp._purge_stale_task_entries(time.monotonic())
    assert cp._task_start_times == {}


def test_purge_all_fresh():
    from app.infrastructure.monitoring import celery_probe as cp

    cp._task_start_times.clear()
    now = time.monotonic()
    cp._task_start_times["a"] = now
    cp._task_start_times["b"] = now
    cp._purge_stale_task_entries(now)
    assert "a" in cp._task_start_times
    assert "b" in cp._task_start_times
    cp._task_start_times.clear()


# ---------------------------------------------------------------------------
# _record_heartbeat_key
# ---------------------------------------------------------------------------


def test_heartbeat_key_format():
    from app.infrastructure.monitoring.celery_probe import _record_heartbeat_key

    assert _record_heartbeat_key("foo.bar") == "beat:last_run:foo.bar"


def test_heartbeat_key_all_expected_tasks():
    from app.infrastructure.monitoring.celery_probe import (
        BEAT_EXPECTED_TASKS,
        _record_heartbeat_key,
    )

    for task_name in BEAT_EXPECTED_TASKS:
        key = _record_heartbeat_key(task_name)
        assert key.startswith("beat:last_run:")
        assert task_name in key


# ---------------------------------------------------------------------------
# BEAT_EXPECTED_TASKS constants
# ---------------------------------------------------------------------------


def test_beat_expected_tasks_has_required_tasks():
    from app.infrastructure.monitoring.celery_probe import BEAT_EXPECTED_TASKS

    assert "infrastructure.relay_outbox_events" in BEAT_EXPECTED_TASKS
    assert "monitoring.error_digest" in BEAT_EXPECTED_TASKS
    assert "monitoring.db_health_check" in BEAT_EXPECTED_TASKS
    assert "prediction.drain_dlq" in BEAT_EXPECTED_TASKS


def test_beat_expected_tasks_values_are_positive():
    from app.infrastructure.monitoring.celery_probe import BEAT_EXPECTED_TASKS

    for task, secs in BEAT_EXPECTED_TASKS.items():
        assert secs > 0, f"{task} has non-positive silence window"


# ---------------------------------------------------------------------------
# _write_heartbeat_sync_redis — Redis write failure is silently swallowed
# ---------------------------------------------------------------------------


def test_write_heartbeat_sync_redis_swallows_error(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp

    monkeypatch.setattr(
        cp, "_get_sync_redis", MagicMock(side_effect=RuntimeError("redis down"))
    )
    # Should not raise
    cp._write_heartbeat_sync_redis("some.task")


def test_write_heartbeat_sync_calls_set(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp

    fake_redis = MagicMock()
    monkeypatch.setattr(cp, "_get_sync_redis", lambda: fake_redis)
    cp._write_heartbeat_sync_redis("infrastructure.relay_outbox_events")
    fake_redis.set.assert_called_once()
    args = fake_redis.set.call_args
    # First positional arg is the key
    assert "relay_outbox_events" in args[0][0]


def test_write_heartbeat_sync_delegates():
    from app.infrastructure.monitoring import celery_probe as cp

    with patch.object(cp, "_write_heartbeat_sync_redis") as mock_fn:
        cp._write_heartbeat_sync("some.task.name")
        mock_fn.assert_called_once_with("some.task.name")


# ---------------------------------------------------------------------------
# _get_sync_redis — singleton pattern
# ---------------------------------------------------------------------------


def test_get_sync_redis_initialises_once(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp

    cp._sync_redis = None
    cp._sync_redis_lock = None

    fake_redis = MagicMock()
    fake_redis_mod = MagicMock()
    fake_redis_mod.from_url.return_value = fake_redis

    with patch.dict("sys.modules", {"redis": fake_redis_mod}):
        r1 = cp._get_sync_redis()
        r2 = cp._get_sync_redis()

    assert r1 is r2  # singleton
    cp._sync_redis = None
    cp._sync_redis_lock = None


# ---------------------------------------------------------------------------
# check_beat_health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_beat_health_emits_for_missing_task(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp

    # Return None for all tasks → all tasks should trigger aemit
    async def fake_get_redis_val(_key):
        return None

    emitted_events = []

    async def fake_aemit(event):
        emitted_events.append(event)

    # The functions are imported inside check_beat_health; patch at source
    with (
        patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_redis_val", fake_get_redis_val
        ),
        patch("app.infrastructure.monitoring.aemit", fake_aemit),
    ):
        await cp.check_beat_health()

    # At least one event emitted (task not seen)
    assert len(emitted_events) >= 1
    for evt in emitted_events:
        assert evt.category == "beat_missed"


@pytest.mark.asyncio
async def test_check_beat_health_no_emit_for_recent_task(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp

    # Return a very recent timestamp for all tasks
    recent_ts = str(time.time())

    async def fake_get_redis_val(_key):
        return recent_ts

    emitted_events = []

    async def fake_aemit(event):
        emitted_events.append(event)

    with (
        patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_redis_val", fake_get_redis_val
        ),
        patch("app.infrastructure.monitoring.aemit", fake_aemit),
    ):
        await cp.check_beat_health()

    # No events for tasks that ran recently
    assert len(emitted_events) == 0


@pytest.mark.asyncio
async def test_check_beat_health_emits_for_expired_task(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp
    from app.infrastructure.monitoring.celery_probe import BEAT_EXPECTED_TASKS

    # Return an old timestamp — older than the shortest silence window
    old_ts = str(time.time() - 9999)

    async def fake_get_redis_val(_key):
        return old_ts

    emitted_events = []

    async def fake_aemit(event):
        emitted_events.append(event)

    with (
        patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_redis_val", fake_get_redis_val
        ),
        patch("app.infrastructure.monitoring.aemit", fake_aemit),
    ):
        await cp.check_beat_health()

    assert len(emitted_events) == len(BEAT_EXPECTED_TASKS)


# ---------------------------------------------------------------------------
# _write_heartbeat_async
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_heartbeat_async_calls_set_redis_val(monkeypatch):
    from app.infrastructure.monitoring import celery_probe as cp

    calls = []

    async def fake_set_redis_val(key, val, expire=None):
        calls.append((key, val, expire))

    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.set_redis_val", fake_set_redis_val
    ):
        await cp._write_heartbeat_async("beat:last_run:test.task")

    assert len(calls) == 1
    key, val, expire = calls[0]
    assert "test.task" in key
    assert expire == 7200


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------


def test_slow_task_thresholds():
    from app.infrastructure.monitoring.celery_probe import (
        _SLOW_TASK_ERROR_MS,
        _SLOW_TASK_WARN_MS,
    )

    assert _SLOW_TASK_WARN_MS < _SLOW_TASK_ERROR_MS
    assert _SLOW_TASK_WARN_MS == 30_000
    assert _SLOW_TASK_ERROR_MS == 120_000


def test_memory_error_threshold():
    from app.infrastructure.monitoring.celery_probe import _MEMORY_ERROR_MB

    assert _MEMORY_ERROR_MB == 800


def test_task_entry_ttl():
    from app.infrastructure.monitoring.celery_probe import _TASK_ENTRY_TTL_SECONDS

    assert _TASK_ENTRY_TTL_SECONDS == 600
