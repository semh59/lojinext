"""notifications.weekly_digest task testi."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@asynccontextmanager
async def _fake_uow():
    yield MagicMock()


def _triage():
    return SimpleNamespace(
        items=[
            SimpleNamespace(title="A", severity="high"),
            SimpleNamespace(title="B", severity="medium"),
            SimpleNamespace(title="C", severity="low"),
            SimpleNamespace(title="D", severity="low"),
        ]
    )


def test_weekly_digest_pushes_top3_to_subscribed_users():
    with (
        patch("app.workers.tasks.notification_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.notification_tasks._distinct_subscriber_ids",
            new=AsyncMock(return_value=[7, 8]),
        ),
        patch(
            "app.workers.tasks.notification_tasks.aggregate_today_triage",
            new=AsyncMock(return_value=_triage()),
        ),
        patch(
            "app.workers.tasks.notification_tasks.send_push_to_user",
            new=AsyncMock(return_value=SimpleNamespace(sent=1, expired=0, failed=0)),
        ) as mock_push,
    ):
        from app.workers.tasks.notification_tasks import weekly_digest

        result = weekly_digest.run()

    assert result["users"] == 2
    assert mock_push.await_count == 2
    _, kwargs = mock_push.await_args
    assert "A" in kwargs["body"]
    assert "C" in kwargs["body"]
    assert "D" not in kwargs["body"]  # yalnız top-3
    assert kwargs["respect_quiet_hours"] is True


def test_weekly_digest_no_subscribers():
    with (
        patch("app.workers.tasks.notification_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.notification_tasks._distinct_subscriber_ids",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.workers.tasks.notification_tasks.send_push_to_user",
            new=AsyncMock(),
        ) as mock_push,
    ):
        from app.workers.tasks.notification_tasks import weekly_digest

        result = weekly_digest.run()

    assert result["users"] == 0
    mock_push.assert_not_awaited()


def test_digest_body_empty_items():
    """_digest_body with no items returns the 'no urgent issues' message."""
    from app.workers.tasks.notification_tasks import _digest_body

    empty_triage = SimpleNamespace(items=[])
    body = _digest_body(empty_triage)
    assert "dikkat gerektiren" in body
    assert "görünmüyor" in body


async def test_distinct_subscriber_ids_returns_list():
    """_distinct_subscriber_ids executes query and returns integer list."""
    from app.workers.tasks.notification_tasks import _distinct_subscriber_ids

    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [1, 2, None, 3]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_rows)
    mock_uow = MagicMock()
    mock_uow.session = mock_session

    with patch("app.workers.tasks.notification_tasks.select", return_value=MagicMock()):
        result = await _distinct_subscriber_ids(mock_uow)

    assert result == [1, 2, 3]


def test_weekly_digest_exception_path():
    """weekly_digest catches exceptions and returns error dict."""

    async def _raise(*_a, **_kw):
        raise RuntimeError("DB down")

    with (
        patch("app.workers.tasks.notification_tasks.UnitOfWork", _fake_uow),
        patch(
            "app.workers.tasks.notification_tasks._distinct_subscriber_ids",
            new=AsyncMock(side_effect=RuntimeError("DB down")),
        ),
    ):
        from app.workers.tasks.notification_tasks import weekly_digest

        result = weekly_digest.run()

    assert result["users"] == 0
    assert result["pushed"] == 0
    assert "DB down" in result["error"]
