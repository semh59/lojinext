from unittest.mock import AsyncMock, patch  # noqa: F401

import pytest

from app.infrastructure.monitoring.service_probe import (
    assert_invariant,
    intentional_fallback,
    monitor_errors,
)


@pytest.mark.unit
async def test_monitor_errors_reraises_by_default():
    @monitor_errors(category="test_error")
    async def failing_fn():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await failing_fn()


@pytest.mark.unit
async def test_monitor_errors_emits_event_on_exception():
    @monitor_errors(category="test_error")
    async def failing_fn():
        raise RuntimeError("test failure")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        with pytest.raises(RuntimeError):
            await failing_fn()
        mock_emit.assert_called_once()
        ev = mock_emit.call_args[0][0]
        assert ev.category == "test_error"


@pytest.mark.unit
async def test_monitor_errors_skips_domain_errors():
    from v2.modules.shared_kernel.exceptions import DomainError

    @monitor_errors(category="test_error")
    async def domain_fn():
        raise DomainError("domain issue")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        with pytest.raises(DomainError):
            await domain_fn()
        mock_emit.assert_not_called()


@pytest.mark.unit
async def test_monitor_errors_skips_value_errors():
    """ValueError = iş-kuralı validasyonu (endpoint 400'e çevirir) — Sentry'ye
    hata olarak AKMAMALI ama çağırana aynen fırlatılmalı (LOJINEXT-1CW)."""

    @monitor_errors(category="test_error")
    async def validation_fn():
        raise ValueError("araç silinemez, kayıtları var")

    with patch(
        "app.infrastructure.monitoring.service_probe.aemit", new_callable=AsyncMock
    ) as mock_emit:
        with pytest.raises(ValueError):
            await validation_fn()
        mock_emit.assert_not_called()


@pytest.mark.unit
def test_monitor_errors_skips_value_errors_sync():
    @monitor_errors(category="test_error")
    def validation_fn():
        raise ValueError("gecersiz deger")

    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        with pytest.raises(ValueError):
            validation_fn()
        mock_emit.assert_not_called()


@pytest.mark.unit
async def test_intentional_fallback_returns_none_on_error():
    @intentional_fallback("test fallback reason")
    async def fallback_fn():
        raise ConnectionError("external down")

    result = await fallback_fn()
    assert result is None


@pytest.mark.unit
def test_assert_invariant_emits_on_violation():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        assert_invariant(False, "negative fuel detected")
        mock_emit.assert_called_once()
        ev = mock_emit.call_args[0][0]
        assert ev.category == "invariant_violation"


@pytest.mark.unit
def test_assert_invariant_no_emit_when_true():
    with patch("app.infrastructure.monitoring.service_probe.emit") as mock_emit:
        assert_invariant(True, "should not emit")
        mock_emit.assert_not_called()
