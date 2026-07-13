"""Coverage tests for v2/modules/notification/application/{handle_trip_events,
get_user_notifications,mark_notification_read,mark_all_notifications_read}.py.

Was coverage for the old NotificationService class (app/core/services/
notification_service.py) — dalga 2 (notification modülü) split it into
free functions (B.1, same rationale as location's LokasyonService removal).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.events.event_bus import Event, EventType
from v2.modules.notification.application import handle_trip_events as mod
from v2.modules.notification.application.get_user_notifications import (
    get_user_notifications,
)
from v2.modules.notification.application.mark_all_notifications_read import (
    mark_all_as_read,
)
from v2.modules.notification.application.mark_notification_read import mark_as_read

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uow(rules=None, users_by_rol=None):
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.session = AsyncMock()
    uow.session.add_all = MagicMock()
    uow.session.flush = AsyncMock()
    uow.commit = AsyncMock()

    uow.notification_repo = AsyncMock()
    uow.notification_repo.get_rules_by_event = AsyncMock(return_value=rules or [])
    uow.notification_repo.get_user_notifications = AsyncMock(return_value=[])
    uow.notification_repo.update = AsyncMock(return_value=True)
    uow.notification_repo.mark_all_as_read = AsyncMock(return_value=3)

    uow.kullanici_repo = AsyncMock()
    uow.kullanici_repo.get_by_rol_ids = AsyncMock(return_value=users_by_rol or {})

    return uow


def _make_rule(rol_id: int = 1, kanallar: list = None):
    rule = MagicMock()
    rule.alici_rol_id = rol_id
    rule.kanallar = kanallar or ["UI"]
    return rule


def _make_user(user_id: int = 1, email: str = "user@test.com"):
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


# ---------------------------------------------------------------------------
# register_handlers
# ---------------------------------------------------------------------------


class TestRegisterHandlers:
    def test_register_handlers_subscribes_events(self):
        mock_bus = MagicMock()
        with patch.object(mod, "get_event_bus", return_value=mock_bus):
            mod.register_handlers()

        # At least SEFER_UPDATED and SLA_DELAY
        assert mock_bus.subscribe.call_count >= 2


# ---------------------------------------------------------------------------
# handle_event — no rules
# ---------------------------------------------------------------------------


class TestHandleEventNoRules:
    async def test_handle_event_returns_early_when_no_rules(self):
        uow = _make_uow(rules=[])

        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 1, "trigger": "test"}
        )

        with patch.object(mod, "UnitOfWork", return_value=uow):
            await mod.handle_event(event)

        # add_all should NOT be called
        uow.session.add_all.assert_not_called()


# ---------------------------------------------------------------------------
# handle_event — with rules and users
# ---------------------------------------------------------------------------


class TestHandleEventWithRulesUI:
    async def test_handle_event_creates_notifications_for_users(self):
        user = _make_user(user_id=5, email="driver@test.com")
        rule = _make_rule(rol_id=2, kanallar=["UI"])
        uow = _make_uow(
            rules=[rule],
            users_by_rol={2: [user]},
        )

        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 10, "trigger": "yakit"}
        )

        with patch.object(mod, "UnitOfWork", return_value=uow):
            await mod.handle_event(event)

        uow.session.add_all.assert_called_once()
        uow.commit.assert_called_once()

    async def test_handle_event_calls_ws_manager_for_ui_channel(self):
        """When ws_manager is set and channel=UI, send_personal_message is called."""
        user = _make_user(user_id=7, email="ops@test.com")
        rule = _make_rule(kanallar=["UI"])
        uow = _make_uow(rules=[rule], users_by_rol={1: [user]})

        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 7, "trigger": "sync"}
        )

        mock_ws = AsyncMock()
        original = mod.notification_ws_manager
        try:
            mod.notification_ws_manager = mock_ws
            with patch.object(mod, "UnitOfWork", return_value=uow):
                await mod.handle_event(event)
        finally:
            mod.notification_ws_manager = original

        mock_ws.send_personal_message.assert_called_once()

    async def test_handle_event_email_channel_does_not_crash(self):
        """EMAIL channel logs a message but does not raise."""
        user = _make_user()
        rule = _make_rule(kanallar=["EMAIL"])
        uow = _make_uow(rules=[rule], users_by_rol={1: [user]})

        event = Event(type=EventType.SLA_DELAY, data={"sefer_id": 2, "delay_min": 45})

        with patch.object(mod, "UnitOfWork", return_value=uow):
            await mod.handle_event(event)

        uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# _format_message
# ---------------------------------------------------------------------------


class TestFormatMessage:
    def test_format_sefer_updated(self):
        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 42, "trigger": "sync"}
        )
        header, content = mod._format_message(event)
        assert "42" in header
        assert "sync" in content

    def test_format_sla_delay(self):
        event = Event(type=EventType.SLA_DELAY, data={"sefer_id": 5, "delay_min": 30})
        header, content = mod._format_message(event)
        assert "SLA" in header or "Gecikme" in header
        assert "30" in content

    def test_format_anomaly_detected(self):
        event = Event(
            type=EventType.ANOMALY_DETECTED,
            data={"aciklama": "Yakıt anomalisi tespit edildi."},
        )
        header, content = mod._format_message(event)
        assert "Anomali" in header
        assert "Yakıt anomalisi" in content

    def test_format_anomaly_detected_default_content(self):
        event = Event(type=EventType.ANOMALY_DETECTED, data={})
        _, content = mod._format_message(event)
        assert "sıra dışı" in content

    def test_format_sla_delay_default_delay_min(self):
        # delay_min missing → defaults to 0
        event = Event(type=EventType.SLA_DELAY, data={"sefer_id": 1})
        _, content = mod._format_message(event)
        assert "0" in content

    def test_format_unknown_event_type(self):
        # Use a different event type not explicitly handled (SEFER_ADDED is not handled)
        event = Event(type=EventType.SEFER_ADDED, data={"foo": "bar"})
        header, content = mod._format_message(event)
        assert header == "Sistem Mesajı"
        assert "bar" in content


# ---------------------------------------------------------------------------
# get_user_notifications
# ---------------------------------------------------------------------------


class TestGetUserNotifications:
    async def test_returns_list(self):
        notifs = [MagicMock(), MagicMock()]
        uow = _make_uow()
        uow.notification_repo.get_user_notifications = AsyncMock(return_value=notifs)

        with patch(
            "v2.modules.notification.application.get_user_notifications.UnitOfWork",
            return_value=uow,
        ):
            result = await get_user_notifications(user_id=1)

        assert result == notifs


# ---------------------------------------------------------------------------
# mark_as_read
# ---------------------------------------------------------------------------


class TestMarkAsRead:
    async def test_returns_true_on_success(self):
        uow = _make_uow()
        uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=True)

        with patch(
            "v2.modules.notification.application.mark_notification_read.UnitOfWork",
            return_value=uow,
        ):
            result = await mark_as_read(notification_id=10, user_id=7)

        assert result is True
        uow.notification_repo.mark_as_read_for_user.assert_awaited_once_with(10, 7)
        uow.commit.assert_called_once()

    async def test_returns_false_when_not_found(self):
        uow = _make_uow()
        uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=False)

        with patch(
            "v2.modules.notification.application.mark_notification_read.UnitOfWork",
            return_value=uow,
        ):
            result = await mark_as_read(notification_id=999, user_id=7)

        assert result is False
        uow.commit.assert_not_called()

    async def test_ownership_scoped_to_user(self):
        """IDOR guard: başka kullanıcının bildirimi (eşleşme yok) → False,
        commit yok."""
        uow = _make_uow()
        # Repo, sahiplik eşleşmediğinde rowcount=0 → False döner.
        uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=False)

        with patch(
            "v2.modules.notification.application.mark_notification_read.UnitOfWork",
            return_value=uow,
        ):
            result = await mark_as_read(notification_id=10, user_id=999)

        assert result is False
        uow.notification_repo.mark_as_read_for_user.assert_awaited_once_with(10, 999)
        uow.commit.assert_not_called()


# ---------------------------------------------------------------------------
# mark_all_as_read
# ---------------------------------------------------------------------------


class TestMarkAllAsRead:
    async def test_returns_count(self):
        uow = _make_uow()
        uow.notification_repo.mark_all_as_read = AsyncMock(return_value=5)

        with patch(
            "v2.modules.notification.application.mark_all_notifications_read.UnitOfWork",
            return_value=uow,
        ):
            result = await mark_all_as_read(user_id=1)

        assert result == 5
        uow.commit.assert_called_once()

    async def test_no_commit_when_count_is_zero(self):
        uow = _make_uow()
        uow.notification_repo.mark_all_as_read = AsyncMock(return_value=0)

        with patch(
            "v2.modules.notification.application.mark_all_notifications_read.UnitOfWork",
            return_value=uow,
        ):
            result = await mark_all_as_read(user_id=1)

        assert result == 0
        uow.commit.assert_not_called()
