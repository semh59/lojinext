"""Faz 4 — compliance.inspection_push task testleri."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@asynccontextmanager
async def _fake_uow():
    yield MagicMock()


def _item(risk: str):
    return SimpleNamespace(risk_level=risk, plaka="34X", field="muayene")


def test_inspection_push_broadcasts_when_due():
    with (
        patch("app.workers.tasks.compliance_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.compliance_tasks.scan_compliance",
            new=AsyncMock(return_value=[_item("overdue"), _item("soon")]),
        ),
        patch(
            "app.workers.tasks.compliance_tasks.send_push_broadcast",
            new=AsyncMock(),
        ) as mock_bc,
    ):
        from app.workers.tasks.compliance_tasks import inspection_push

        result = inspection_push.run()

    assert result == {"due": 2, "overdue": 1, "pushed": True}
    mock_bc.assert_awaited_once()
    _, kwargs = mock_bc.await_args
    assert kwargs["title"] == "Muayene hatırlatması"
    assert "2" in kwargs["body"]


def test_inspection_push_skips_when_none_due():
    with (
        patch("app.workers.tasks.compliance_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.compliance_tasks.scan_compliance",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.workers.tasks.compliance_tasks.send_push_broadcast",
            new=AsyncMock(),
        ) as mock_bc,
    ):
        from app.workers.tasks.compliance_tasks import inspection_push

        result = inspection_push.run()

    assert result == {"due": 0, "pushed": False}
    mock_bc.assert_not_awaited()
