"""Error digest Celery task tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.platform_infra.background.error_digest import (
    _drain_sync_fallback,
    _run_digest,
    error_digest,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_drain_sync_fallback_empty_queue():
    """Test sync fallback drain with empty queue."""
    redis = AsyncMock()
    redis.lrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock()

    await _drain_sync_fallback(redis)

    redis.lrange.assert_called_once_with("error:sync_fallback", 0, -1)
    redis.delete.assert_not_called()


@pytest.mark.asyncio
async def test_drain_sync_fallback_with_errors():
    """Test sync fallback drain with error events."""
    import json

    redis = AsyncMock()
    error_data = {
        "layer": "api",
        "category": "auth",
        "severity": "error",
        "message": "Auth failed",
        "trace_id": "123",
    }
    redis.lrange = AsyncMock(return_value=[json.dumps(error_data).encode()])
    redis.delete = AsyncMock()

    with patch(
        "v2.modules.platform_infra.monitoring.alarm_router.get_alarm_router"
    ) as mock_router:
        mock_router.return_value.route = AsyncMock()
        await _drain_sync_fallback(redis)

        redis.lrange.assert_called_once()
        redis.delete.assert_called_once_with("error:sync_fallback")


@pytest.mark.asyncio
async def test_drain_sync_fallback_invalid_json():
    """Test sync fallback drain skips invalid JSON."""
    redis = AsyncMock()
    redis.lrange = AsyncMock(return_value=[b"invalid json"])
    redis.delete = AsyncMock()

    with patch("v2.modules.platform_infra.monitoring.alarm_router.get_alarm_router"):
        await _drain_sync_fallback(redis)

        redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_drain_sync_fallback_redis_error():
    """Test sync fallback handles Redis errors gracefully."""
    redis = AsyncMock()
    redis.lrange = AsyncMock(side_effect=Exception("Redis error"))

    # Should not raise, just log warning
    await _drain_sync_fallback(redis)


@pytest.mark.asyncio
async def test_run_digest_no_redis():
    """Test digest task when Redis unavailable."""
    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = None

        # Should return early without error
        await _run_digest()


@pytest.mark.asyncio
async def test_run_digest_no_errors():
    """Test digest task with no accumulated errors."""
    redis = AsyncMock()
    redis.keys = AsyncMock(return_value=[])

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = redis

        with patch("v2.modules.platform_infra.background.error_digest._drain_sync_fallback"):
            await _run_digest()

            redis.keys.assert_called_once()


@pytest.mark.asyncio
async def test_run_digest_with_error_keys():
    """Digest task Redis'te key bulunca keys() çağrısını yapar."""
    redis_mock = AsyncMock()
    redis_mock.keys = AsyncMock(return_value=[b"error:digest:api:auth"])

    # pipeline().execute() → boş data → lines=[] → early return (notify çağrılmaz)
    pipe = MagicMock()
    pipe.hgetall = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[{}])
    redis_mock.pipeline = MagicMock(return_value=pipe)

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = redis_mock
        with patch("v2.modules.platform_infra.background.error_digest._drain_sync_fallback"):
            await _run_digest()

    redis_mock.keys.assert_called_once()


def test_error_digest_task_runs():
    """Test error_digest Celery task executes (CELERY_EAGER mode)."""
    with patch("v2.modules.platform_infra.background.error_digest._run_digest") as mock_run:
        mock_run.return_value = None

        # Task should execute in eager mode without raising
        error_digest()


@pytest.mark.asyncio
async def test_run_digest_redis_scan_error():
    """Test digest task handles Redis scan errors."""
    redis = AsyncMock()
    redis.keys = AsyncMock(side_effect=Exception("Redis unavailable"))

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = redis

        with patch("v2.modules.platform_infra.background.error_digest._drain_sync_fallback"):
            # Should handle error gracefully
            await _run_digest()
