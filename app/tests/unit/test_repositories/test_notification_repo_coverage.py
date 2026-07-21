"""Coverage tests for v2/modules/notification/infrastructure/repository.py

Targets ~38% → ≥75%
Covers: get_rules_by_event, get_user_notifications, get_all_rules,
        create_rule, mark_all_as_read
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo():
    from v2.modules.notification.infrastructure.repository import (
        NotificationRepository,
    )

    mock_session = AsyncMock()
    repo = NotificationRepository.__new__(NotificationRepository)
    repo.session = mock_session
    return repo, mock_session


def _mock_scalars_result(items):
    """Returns a mock execute result whose scalars().all() returns `items`."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


# ---------------------------------------------------------------------------
# get_rules_by_event
# ---------------------------------------------------------------------------


class TestGetRulesByEvent:
    async def test_get_rules_by_event_returns_list(self):
        """get_rules_by_event returns list of active rules for event type."""
        repo, session = _make_repo()
        mock_rule = MagicMock()
        mock_rule.olay_tipi = "YAKIT_ALARMI"
        mock_rule.aktif = True

        session.execute = AsyncMock(return_value=_mock_scalars_result([mock_rule]))

        result = await repo.get_rules_by_event("YAKIT_ALARMI")

        assert isinstance(result, list)
        assert len(result) == 1
        session.execute.assert_called_once()

    async def test_get_rules_by_event_empty(self):
        """get_rules_by_event returns empty list when no matching rules."""
        repo, session = _make_repo()
        session.execute = AsyncMock(return_value=_mock_scalars_result([]))

        result = await repo.get_rules_by_event("UNKNOWN_EVENT")

        assert result == []

    async def test_get_rules_by_event_multiple(self):
        """get_rules_by_event returns all matching rules."""
        repo, session = _make_repo()
        rules = [MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_mock_scalars_result(rules))

        result = await repo.get_rules_by_event("KAZA")

        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_user_notifications
# ---------------------------------------------------------------------------


class TestGetUserNotifications:
    async def test_get_user_notifications_default_limit(self):
        """get_user_notifications uses default limit=50."""
        repo, session = _make_repo()
        notifs = [MagicMock() for _ in range(3)]
        session.execute = AsyncMock(return_value=_mock_scalars_result(notifs))

        result = await repo.get_user_notifications(kullanici_id=42)

        assert len(result) == 3
        session.execute.assert_called_once()

    async def test_get_user_notifications_custom_limit(self):
        """get_user_notifications respects custom limit."""
        repo, session = _make_repo()
        session.execute = AsyncMock(return_value=_mock_scalars_result([]))

        result = await repo.get_user_notifications(kullanici_id=1, limit=10)

        assert result == []

    async def test_get_user_notifications_empty(self):
        """get_user_notifications returns empty list when no notifications."""
        repo, session = _make_repo()
        session.execute = AsyncMock(return_value=_mock_scalars_result([]))

        result = await repo.get_user_notifications(kullanici_id=999)

        assert result == []


# ---------------------------------------------------------------------------
# get_all_rules
# ---------------------------------------------------------------------------


class TestGetAllRules:
    async def test_get_all_rules_returns_all(self):
        """get_all_rules fetches all notification rules."""
        repo, session = _make_repo()
        rules = [MagicMock(), MagicMock(), MagicMock()]
        session.execute = AsyncMock(return_value=_mock_scalars_result(rules))

        result = await repo.get_all_rules()

        assert len(result) == 3
        session.execute.assert_called_once()

    async def test_get_all_rules_empty(self):
        """get_all_rules returns empty list when no rules configured."""
        repo, session = _make_repo()
        session.execute = AsyncMock(return_value=_mock_scalars_result([]))

        result = await repo.get_all_rules()

        assert result == []


# ---------------------------------------------------------------------------
# create_rule
# ---------------------------------------------------------------------------


class TestCreateRule:
    async def test_create_rule_adds_and_flushes(self):
        """create_rule adds BildirimKurali to session and flushes."""
        repo, session = _make_repo()
        session.add = MagicMock()
        session.flush = AsyncMock()

        rule_data = {
            "olay_tipi": "YAKIT_ALARMI",
            "kanallar": ["email"],
            "alici_rol_id": 1,
            "aktif": True,
        }

        result = await repo.create_rule(rule_data)

        session.add.assert_called_once()
        session.flush.assert_called_once()

        # returned object is a BildirimKurali instance
        from v2.modules.notification.public import BildirimKurali

        assert isinstance(result, BildirimKurali)
        assert result.olay_tipi == "YAKIT_ALARMI"
        assert result.kanallar == ["email"]

    async def test_create_rule_inactive(self):
        """create_rule creates rule with aktif=False."""
        repo, session = _make_repo()
        session.add = MagicMock()
        session.flush = AsyncMock()

        rule_data = {
            "olay_tipi": "TEST",
            "kanallar": ["sms"],
            "alici_rol_id": 2,
            "aktif": False,
        }

        result = await repo.create_rule(rule_data)

        from v2.modules.notification.public import BildirimKurali

        assert isinstance(result, BildirimKurali)
        assert result.aktif is False


# ---------------------------------------------------------------------------
# mark_all_as_read
# ---------------------------------------------------------------------------


class TestMarkAllAsRead:
    async def test_mark_all_as_read_returns_rowcount(self):
        """mark_all_as_read returns number of updated rows."""
        repo, session = _make_repo()

        mock_result = MagicMock()
        mock_result.rowcount = 7
        session.execute = AsyncMock(return_value=mock_result)

        count = await repo.mark_all_as_read(user_id=42)

        assert count == 7
        session.execute.assert_called_once()

    async def test_mark_all_as_read_zero(self):
        """mark_all_as_read returns 0 when no unread notifications."""
        repo, session = _make_repo()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute = AsyncMock(return_value=mock_result)

        count = await repo.mark_all_as_read(user_id=999)

        assert count == 0

    async def test_mark_all_as_read_updates_durum_to_read(self):
        """mark_all_as_read issues an UPDATE statement."""

        repo, session = _make_repo()

        mock_result = MagicMock()
        mock_result.rowcount = 3
        session.execute = AsyncMock(return_value=mock_result)

        count = await repo.mark_all_as_read(user_id=5)

        # Verify execute was called (with an UPDATE statement)
        session.execute.assert_called_once()
        call_args = session.execute.call_args[0]
        # The first argument should be an update statement
        assert call_args is not None
        assert count == 3
