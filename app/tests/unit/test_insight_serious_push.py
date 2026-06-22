"""Faz 4 — kritik anomali → filo geneli push tetikleyicisi testleri."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.services.insight_engine import _notify_serious_alerts

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_critical_severity_triggers_broadcast():
    payloads = [
        {"severity": "low", "message": "düşük"},
        {"severity": "critical", "message": "Depo anomalisi: ARAÇ-1"},
    ]
    with patch(
        "app.core.services.push_sender.send_push_broadcast",
        new=AsyncMock(),
    ) as mock_broadcast:
        await _notify_serious_alerts(payloads)
    mock_broadcast.assert_awaited_once()
    _, kwargs = mock_broadcast.await_args
    assert kwargs["title"] == "Kritik filo uyarısı"
    assert kwargs["url"] == "/alerts"
    assert "Depo anomalisi" in kwargs["body"]


@pytest.mark.asyncio
async def test_no_serious_severity_does_not_broadcast():
    payloads = [
        {"severity": "low", "message": "a"},
        {"severity": "medium", "message": "b"},
    ]
    with patch(
        "app.core.services.push_sender.send_push_broadcast",
        new=AsyncMock(),
    ) as mock_broadcast:
        await _notify_serious_alerts(payloads)
    mock_broadcast.assert_not_awaited()


@pytest.mark.asyncio
async def test_push_failure_is_swallowed():
    payloads = [{"severity": "high", "message": "x"}]
    with patch(
        "app.core.services.push_sender.send_push_broadcast",
        new=AsyncMock(side_effect=RuntimeError("push down")),
    ):
        # raise etmemeli — best-effort
        await _notify_serious_alerts(payloads)


@pytest.mark.asyncio
async def test_multiple_serious_uses_count_body():
    payloads = [
        {"severity": "high", "message": "x"},
        {"severity": "critical", "message": "y"},
    ]
    with patch(
        "app.core.services.push_sender.send_push_broadcast",
        new=AsyncMock(),
    ) as mock_broadcast:
        await _notify_serious_alerts(payloads)
    _, kwargs = mock_broadcast.await_args
    assert "2" in kwargs["body"]
