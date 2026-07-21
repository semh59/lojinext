"""notifications.weekly_digest task testi.

0-mock (Dilim 37): patch("...UnitOfWork", _fake_uow) replaced with
narrow patch.object(UnitOfWork, '__aenter__'/__aexit__).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


def _triage():
    return SimpleNamespace(
        items=[
            SimpleNamespace(title="A", severity="high"),
            SimpleNamespace(title="B", severity="medium"),
            SimpleNamespace(title="C", severity="low"),
            SimpleNamespace(title="D", severity="low"),
        ]
    )


def _uow_ctx():
    return (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=MagicMock())),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    )


def test_weekly_digest_pushes_top3_to_subscribed_users():
    enter_p, exit_p = _uow_ctx()
    with (
        enter_p,
        exit_p,
        patch(
            "v2.modules.notification.infrastructure.tasks._distinct_subscriber_ids",
            new=AsyncMock(return_value=[7, 8]),
        ),
        patch(
            "v2.modules.notification.infrastructure.tasks.aggregate_today_triage",
            new=AsyncMock(return_value=_triage()),
        ),
        patch(
            "v2.modules.notification.infrastructure.tasks.send_push_to_user",
            new=AsyncMock(return_value=SimpleNamespace(sent=1, expired=0, failed=0)),
        ) as mock_push,
    ):
        from v2.modules.notification.infrastructure.tasks import weekly_digest

        result = weekly_digest.run()

    assert result["users"] == 2
    assert mock_push.await_count == 2
    _, kwargs = mock_push.await_args
    assert "A" in kwargs["body"]
    assert "C" in kwargs["body"]
    assert "D" not in kwargs["body"]  # yalnız top-3
    assert kwargs["respect_quiet_hours"] is True


def test_weekly_digest_no_subscribers():
    enter_p, exit_p = _uow_ctx()
    with (
        enter_p,
        exit_p,
        patch(
            "v2.modules.notification.infrastructure.tasks._distinct_subscriber_ids",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "v2.modules.notification.infrastructure.tasks.send_push_to_user",
            new=AsyncMock(),
        ) as mock_push,
    ):
        from v2.modules.notification.infrastructure.tasks import weekly_digest

        result = weekly_digest.run()

    assert result["users"] == 0
    mock_push.assert_not_awaited()


def test_digest_body_empty_items():
    """_digest_body with no items returns the 'no urgent issues' message."""
    from v2.modules.notification.infrastructure.tasks import _digest_body

    empty_triage = SimpleNamespace(items=[])
    body = _digest_body(empty_triage)
    assert "dikkat gerektiren" in body
    assert "görünmüyor" in body


async def test_distinct_subscriber_ids_returns_list():
    """_distinct_subscriber_ids executes query and returns integer list."""
    from v2.modules.notification.infrastructure.tasks import _distinct_subscriber_ids

    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [1, 2, None, 3]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_rows)
    mock_uow = MagicMock()
    mock_uow.session = mock_session

    with patch(
        "v2.modules.notification.infrastructure.tasks.select", return_value=MagicMock()
    ):
        result = await _distinct_subscriber_ids(mock_uow)

    assert result == [1, 2, 3]


def test_weekly_digest_generic_error_reraises():
    """2026-07-01 derin kontrol: eskiden generic bir hata yutulup normal bir
    sonuç dict'i dönüyordu (Celery bunu SUCCESS sayardı, retry hiç
    tetiklenmezdi). Artık log'lanıp yeniden fırlatılıyor — task gerçekten
    FAILED olarak işaretlenir."""
    enter_p, exit_p = _uow_ctx()
    with (
        enter_p,
        exit_p,
        patch(
            "v2.modules.notification.infrastructure.tasks._distinct_subscriber_ids",
            new=AsyncMock(side_effect=RuntimeError("DB down")),
        ),
    ):
        from v2.modules.notification.infrastructure.tasks import weekly_digest

        with pytest.raises(Exception):
            weekly_digest.apply(args=[]).get(propagate=True)


def test_weekly_digest_connection_error_retries():
    """Geçici bir bağlantı hatası (ConnectionError) retry path'ini tetikler."""
    enter_p, exit_p = _uow_ctx()
    with (
        enter_p,
        exit_p,
        patch(
            "v2.modules.notification.infrastructure.tasks._distinct_subscriber_ids",
            new=AsyncMock(side_effect=ConnectionError("Redis unreachable")),
        ),
    ):
        from v2.modules.notification.infrastructure.tasks import weekly_digest

        with pytest.raises(Exception):
            weekly_digest.apply(args=[]).get(propagate=True)
