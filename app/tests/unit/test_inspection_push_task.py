"""Faz 4 — compliance.inspection_push task testleri."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


def _item(risk: str):
    return SimpleNamespace(risk_level=risk, plaka="34X", field="muayene")


def test_inspection_push_broadcasts_when_due():
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=MagicMock())),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.analytics_executive.infrastructure.compliance_tasks.scan_compliance",
            new=AsyncMock(return_value=[_item("overdue"), _item("soon")]),
        ),
        patch(
            "v2.modules.analytics_executive.infrastructure.compliance_tasks.send_push_broadcast",
            new=AsyncMock(),
        ) as mock_bc,
    ):
        from v2.modules.analytics_executive.infrastructure.compliance_tasks import (
            inspection_push,
        )

        result = inspection_push.run()

    assert result == {"due": 2, "overdue": 1, "pushed": True}
    mock_bc.assert_awaited_once()
    _, kwargs = mock_bc.await_args
    assert kwargs["title"] == "Muayene hatırlatması"
    assert "2" in kwargs["body"]


def test_inspection_push_skips_when_none_due():
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=MagicMock())),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        patch(
            "v2.modules.analytics_executive.infrastructure.compliance_tasks.scan_compliance",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "v2.modules.analytics_executive.infrastructure.compliance_tasks.send_push_broadcast",
            new=AsyncMock(),
        ) as mock_bc,
    ):
        from v2.modules.analytics_executive.infrastructure.compliance_tasks import (
            inspection_push,
        )

        result = inspection_push.run()

    assert result == {"due": 0, "pushed": False}
    mock_bc.assert_not_awaited()
