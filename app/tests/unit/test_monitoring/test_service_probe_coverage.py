"""
Additional coverage tests for app/infrastructure/monitoring/service_probe.py
Covers: sync monitor_errors, no-reraise path, capture_result, intentional_fallback,
        assert_invariant with metadata, setup_asyncio_exception_handler.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# monitor_errors — async paths (supplementary)
# ---------------------------------------------------------------------------


async def test_monitor_errors_no_reraise_returns_none():
    """reraise=False: exception is swallowed, None returned."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    # RuntimeError: ValueError artık iş-validasyonu olarak SKIP edilip her
    # zaman reraise edilir (LOJINEXT-1CW fix'i) — bu test reraise=False
    # yolunu sınıyor, tip önemli değil.
    @monitor_errors(category="test", reraise=False)
    async def fragile():
        raise RuntimeError("swallowed")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ):
        result = await fragile()

    assert result is None


async def test_monitor_errors_capture_result_emits_warning_on_none():
    """capture_result=True and fn returns None → WARNING emitted."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="test", capture_result=True)
    async def returns_none():
        return None

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        result = await returns_none()

    assert result is None
    mock_emit.assert_called_once()
    ev = mock_emit.call_args[0][0]
    assert "null_result" in ev.category


async def test_monitor_errors_capture_result_no_emit_when_value_returned():
    """capture_result=True but fn returns a value → no emit."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="test", capture_result=True)
    async def returns_value():
        return {"id": 1}

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        result = await returns_value()

    assert result == {"id": 1}
    mock_emit.assert_not_called()


async def test_monitor_errors_skips_http_exception():
    """HTTPException is not emitted and re-raised directly."""
    from fastapi import HTTPException

    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="test")
    async def http_fail():
        raise HTTPException(status_code=404, detail="not found")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        with pytest.raises(HTTPException):
            await http_fail()
        mock_emit.assert_not_called()


async def test_monitor_errors_includes_call_chain_in_metadata():
    """Emitted ErrorEvent should include fn qualname in metadata."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="chain_test")
    async def inner_fn():
        raise RuntimeError("chain test")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        with pytest.raises(RuntimeError):
            await inner_fn()

    ev = mock_emit.call_args[0][0]
    assert "inner_fn" in ev.metadata.get("fn", "")


async def test_monitor_errors_custom_severity():
    """Custom severity string is passed to ErrorEvent."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="test", severity="warning", reraise=False)
    async def warning_fn():
        raise RuntimeError("warning level")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        await warning_fn()

    ev = mock_emit.call_args[0][0]
    assert ev.severity.value == "warning"


# ---------------------------------------------------------------------------
# monitor_errors — sync path
# ---------------------------------------------------------------------------


def test_monitor_errors_sync_reraises():
    """Sync function with reraise=True should re-raise non-domain errors."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    # RuntimeError: bkz. yukarıdaki not (ValueError artık emit edilmeden
    # reraise edilir).
    @monitor_errors(category="sync_test")
    def sync_fail():
        raise RuntimeError("sync boom")

    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        with pytest.raises(RuntimeError):
            sync_fail()
        mock_emit.assert_called_once()


def test_monitor_errors_sync_no_reraise():
    """Sync function with reraise=False swallows exception."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="sync_test", reraise=False)
    def sync_swallow():
        raise RuntimeError("swallowed sync")

    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        result = sync_swallow()

    assert result is None
    mock_emit.assert_called_once()


def test_monitor_errors_sync_skips_domain_error():
    """Sync: DomainError passes through without emit."""
    from app.core.exceptions import DomainError
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="sync_test")
    def domain_sync():
        raise DomainError("domain issue sync")

    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        with pytest.raises(DomainError):
            domain_sync()
        mock_emit.assert_not_called()


def test_monitor_errors_sync_skips_http_exception():
    from fastapi import HTTPException

    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="sync_test")
    def http_sync():
        raise HTTPException(status_code=400)

    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        with pytest.raises(HTTPException):
            http_sync()
        mock_emit.assert_not_called()


def test_monitor_errors_sync_normal_return():
    """Sync function that returns normally — no emit."""
    from app.infrastructure.monitoring.service_probe import monitor_errors

    @monitor_errors(category="sync_test")
    def ok():
        return 42

    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        result = ok()

    assert result == 42
    mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# intentional_fallback
# ---------------------------------------------------------------------------


async def test_intentional_fallback_success_path():
    """No exception: function result is returned as-is."""
    from app.infrastructure.monitoring.service_probe import intentional_fallback

    @intentional_fallback("test reason")
    async def ok_fn():
        return {"status": "ok"}

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        result = await ok_fn()

    assert result == {"status": "ok"}
    mock_emit.assert_not_called()


async def test_intentional_fallback_emits_warning():
    """Exception → WARNING emitted with reason in message."""
    from app.infrastructure.monitoring.service_probe import intentional_fallback

    @intentional_fallback("external API down")
    async def external_call():
        raise TimeoutError("timeout")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        result = await external_call()

    assert result is None
    ev = mock_emit.call_args[0][0]
    assert ev.category == "intentional_fallback"
    assert "external API down" in ev.message
    assert ev.severity.value == "warning"


# ---------------------------------------------------------------------------
# assert_invariant
# ---------------------------------------------------------------------------


def test_assert_invariant_with_metadata():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        from app.infrastructure.monitoring.service_probe import assert_invariant

        assert_invariant(False, "bad state", metadata={"field": "fuel_lt"})

    ev = mock_emit.call_args[0][0]
    assert ev.metadata == {"field": "fuel_lt"}


def test_assert_invariant_warning_severity():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        from app.infrastructure.monitoring.service_probe import assert_invariant

        assert_invariant(False, "soft warning", severity="warning")

    ev = mock_emit.call_args[0][0]
    assert ev.severity.value == "warning"


def test_assert_invariant_true_is_noop():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        from app.infrastructure.monitoring.service_probe import assert_invariant

        assert_invariant(True, "should not emit", metadata={"x": 1})

    mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# setup_asyncio_exception_handler
# ---------------------------------------------------------------------------


async def test_setup_asyncio_exception_handler_registers():
    """Called from async context (running loop exists) — sets exception handler."""
    from app.infrastructure.monitoring.service_probe import (
        setup_asyncio_exception_handler,
    )

    loop = asyncio.get_running_loop()
    original_handler = loop.get_exception_handler()

    try:
        setup_asyncio_exception_handler()
        handler = loop.get_exception_handler()
        assert handler is not None
    finally:
        loop.set_exception_handler(original_handler)


async def test_setup_asyncio_handler_emits_on_unhandled():
    """The installed handler emits an ErrorEvent when called."""
    from app.infrastructure.monitoring.service_probe import (
        setup_asyncio_exception_handler,
    )

    loop = asyncio.get_running_loop()
    original_handler = loop.get_exception_handler()

    try:
        with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
            setup_asyncio_exception_handler()
            installed = loop.get_exception_handler()
            assert installed is not None
            exc = RuntimeError("dangling task")
            installed(
                loop,
                {"message": "task exception was never retrieved", "exception": exc},
            )
            mock_emit.assert_called_once()
            ev = mock_emit.call_args[0][0]
            assert ev.category == "async_context_leak"
    finally:
        loop.set_exception_handler(original_handler)


def test_setup_asyncio_exception_handler_no_loop(monkeypatch):
    """No running loop → function returns early without error."""
    from app.infrastructure.monitoring.service_probe import (
        setup_asyncio_exception_handler,
    )

    with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
        # Should not raise
        setup_asyncio_exception_handler()
