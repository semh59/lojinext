"""Telegram notifier unit tests."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_client(raise_for_status_side_effect=None):
    mock_response = MagicMock()
    if raise_for_status_side_effect:
        mock_response.raise_for_status = MagicMock(
            side_effect=raise_for_status_side_effect
        )
    else:
        mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client, mock_response


@pytest.mark.unit
async def test_notify_error_success_no_exception():
    """Successful POST → no exception raised."""
    mock_client, _ = _make_mock_client()

    with patch(
        "v2.modules.notification.infrastructure.telegram_client.get_monitored_client",
        return_value=mock_client,
    ):
        from v2.modules.notification.infrastructure.telegram_client import notify_error

        # Must not raise
        await notify_error(level="critical", message="test msg")
        mock_client.post.assert_called_once()


@pytest.mark.unit
async def test_notify_error_logs_warning_on_network_failure(caplog):
    """All retries fail → WARNING log, exception swallowed, sync_fallback written."""
    mock_client, _ = _make_mock_client(
        raise_for_status_side_effect=Exception("HTTP 503")
    )

    with (
        patch(
            "v2.modules.notification.infrastructure.telegram_client.get_monitored_client",
            return_value=mock_client,
        ),
        patch("v2.modules.notification.infrastructure.telegram_client.asyncio.sleep"),
        patch(
            "v2.modules.notification.infrastructure.telegram_client._push_to_sync_fallback"
        ) as mock_fb,
    ):
        import v2.modules.notification.infrastructure.telegram_client as mod

        with caplog.at_level(logging.WARNING, logger=mod.logger.name):
            await mod.notify_error(level="critical", message="fail test")

    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_records) >= 1
    assert any(
        "Telegram" in r.message or "notify_error" in r.message.lower()
        for r in warning_records
    ), f"Expected Telegram warning, got: {[r.message for r in warning_records]}"
    mock_fb.assert_called_once()  # fallback must be invoked after all retries fail


@pytest.mark.unit
async def test_notify_error_sends_correct_payload():
    """POST body contains expected fields."""
    mock_client, _ = _make_mock_client()

    with patch(
        "v2.modules.notification.infrastructure.telegram_client.get_monitored_client",
        return_value=mock_client,
    ):
        from v2.modules.notification.infrastructure.telegram_client import notify_error

        await notify_error(
            level="error",
            message="fuel anomaly",
            path="/api/v1/seferler",
            trace_id="trace-123",
        )

    call_kwargs = mock_client.post.call_args
    json_payload = call_kwargs[1]["json"]
    assert json_payload["level"] == "error"
    assert json_payload["message"] == "fuel anomaly"
    assert json_payload["path"] == "/api/v1/seferler"
    assert json_payload["trace_id"] == "trace-123"


@pytest.mark.unit
async def test_notify_error_default_path_and_trace():
    """Default path/trace_id are empty strings."""
    mock_client, _ = _make_mock_client()

    with patch(
        "v2.modules.notification.infrastructure.telegram_client.get_monitored_client",
        return_value=mock_client,
    ):
        from v2.modules.notification.infrastructure.telegram_client import notify_error

        await notify_error(level="warning", message="test")

    json_payload = mock_client.post.call_args[1]["json"]
    assert json_payload["path"] == ""
    assert json_payload["trace_id"] == ""


@pytest.mark.unit
async def test_notify_error_retries_then_fallback():
    """Two transient failures + final success → exactly 3 attempts, no fallback."""
    call_count = 0
    success_response = MagicMock()
    success_response.raise_for_status = MagicMock()
    fail_response = MagicMock()
    fail_response.raise_for_status = MagicMock(side_effect=Exception("503"))

    async def alternating_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return fail_response if call_count < 3 else success_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = alternating_post

    with (
        patch(
            "v2.modules.notification.infrastructure.telegram_client.get_monitored_client",
            return_value=mock_client,
        ),
        patch("v2.modules.notification.infrastructure.telegram_client.asyncio.sleep"),
        patch(
            "v2.modules.notification.infrastructure.telegram_client._push_to_sync_fallback"
        ) as mock_fb,
    ):
        from v2.modules.notification.infrastructure.telegram_client import notify_error

        await notify_error(level="error", message="transient")

    assert call_count == 3
    mock_fb.assert_not_called()  # succeeded on 3rd attempt, no fallback needed


@pytest.mark.unit
async def test_push_to_sync_fallback_uses_async_redis_not_blocking_client():
    """Sentry LOJINEXT-182: _push_to_sync_fallback must go through the async
    Redis client (get_pubsub_manager().redis), never a synchronous redis-py
    connection — a blocking socket call from inside this async function
    previously froze the whole event loop (every concurrent coroutine,
    including in-flight SQL query callbacks), which is the proven root
    cause of a "Slow query" false alarm on an otherwise trivial query."""
    from v2.modules.notification.infrastructure.telegram_client import (
        _push_to_sync_fallback,
    )

    mock_redis = AsyncMock()
    mock_manager = MagicMock()
    mock_manager.redis = mock_redis

    with patch(
        "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
        return_value=mock_manager,
    ):
        await _push_to_sync_fallback(
            level="error", message="msg", path="/x", trace_id="t1"
        )

    mock_redis.lpush.assert_awaited_once()
    mock_redis.ltrim.assert_awaited_once()


@pytest.mark.unit
async def test_push_to_sync_fallback_noop_when_redis_unavailable():
    """No async Redis client configured — returns cleanly, no exception."""
    from v2.modules.notification.infrastructure.telegram_client import (
        _push_to_sync_fallback,
    )

    mock_manager = MagicMock()
    mock_manager.redis = None

    with patch(
        "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
        return_value=mock_manager,
    ):
        await _push_to_sync_fallback(
            level="error", message="msg", path="/x", trace_id="t1"
        )  # must not raise
