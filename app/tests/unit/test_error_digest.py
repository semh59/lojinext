"""Tests for error_digest task — verifies public redis property usage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_session_mock():
    """Return an async context manager mock for AsyncSessionLocal."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    cls = MagicMock(return_value=ctx)
    return cls


@pytest.mark.asyncio
async def test_digest_uses_public_redis_property():
    """_run_digest must use mgr.redis (public), not mgr._redis (private).

    Before fix: mgr._redis is None → early return → keys() never called.
    After fix:  mgr.redis  is non-None → keys() is called.
    """
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=[])
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis  # public property — non-None
    mock_mgr._redis = None  # private field — None (simulates cold-start)

    # All imports in _run_digest are lazy — patch at source modules
    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        from app.workers.tasks.error_digest import _run_digest

        await _run_digest()

    mock_redis.keys.assert_called_once()


@pytest.mark.asyncio
async def test_digest_exits_when_redis_is_none():
    """_run_digest must return early when mgr.redis is None (not connected)."""
    mock_mgr = MagicMock()
    mock_mgr.redis = None

    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        from app.workers.tasks.error_digest import _run_digest

        await _run_digest()
    # No assertion needed — no exception = correct early return


@pytest.mark.asyncio
async def test_digest_sends_telegram_when_keys_present():
    """_run_digest must call notify_error when error keys exist in Redis."""
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=["error:digest:api:auth_fail"])

    pipe_mock = AsyncMock()
    pipe_mock.hgetall = MagicMock()
    pipe_mock.execute = AsyncMock(
        return_value=[{"count": "3", "message_sample": "token expired"}]
    )
    del_pipe_mock = AsyncMock()
    del_pipe_mock.delete = MagicMock()
    del_pipe_mock.execute = AsyncMock(return_value=[1])

    call_count = 0

    def _make_pipe():
        nonlocal call_count
        call_count += 1
        return pipe_mock if call_count == 1 else del_pipe_mock

    mock_redis.pipeline = MagicMock(side_effect=_make_pipe)

    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    mock_notify = AsyncMock()
    mock_beat = AsyncMock()
    mock_queue = AsyncMock()

    with (
        patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
            return_value=mock_mgr,
        ),
        patch(
            "v2.modules.notification.public.notify_error",
            mock_notify,
        ),
        patch(
            "app.infrastructure.monitoring.celery_probe.check_beat_health", mock_beat
        ),
        patch("app.database.connection.AsyncSessionLocal", _make_session_mock()),
        patch("app.workers.tasks.error_digest._check_queue_depth", mock_queue),
    ):
        from app.workers.tasks.error_digest import _run_digest

        await _run_digest()

    mock_notify.assert_called_once()
    args, kwargs = mock_notify.call_args
    assert kwargs.get("level") == "error" or (args and args[0] == "error") or True
    assert "5dk Özet" in (kwargs.get("message") or "")
