"""Coverage tests for app/core/services/notification_service.py (56% → ≥75%)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.events.event_bus import Event, EventType

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


def _make_service(uow=None):
    from app.core.services.notification_service import NotificationService

    svc = NotificationService.__new__(NotificationService)
    svc.event_bus = MagicMock()
    return svc, uow


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestNotificationServiceInit:
    def test_init_subscribes_event_bus(self):
        mock_bus = MagicMock()
        with patch(
            "app.core.services.notification_service.get_event_bus",
            return_value=mock_bus,
        ):
            from app.core.services.notification_service import NotificationService

            svc = NotificationService()
        assert svc.event_bus is mock_bus

    def test_register_handlers_subscribes_events(self):
        mock_bus = MagicMock()
        with patch(
            "app.core.services.notification_service.get_event_bus",
            return_value=mock_bus,
        ):
            from app.core.services.notification_service import NotificationService

            svc = NotificationService()
            svc.register_handlers()

        # At least SEFER_UPDATED and SLA_DELAY
        assert mock_bus.subscribe.call_count >= 2


# ---------------------------------------------------------------------------
# handle_event — no rules
# ---------------------------------------------------------------------------


class TestHandleEventNoRules:
    async def test_handle_event_returns_early_when_no_rules(self):
        svc, _ = _make_service()
        uow = _make_uow(rules=[])

        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 1, "trigger": "test"}
        )

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            await svc.handle_event(event)

        # add_all should NOT be called
        uow.session.add_all.assert_not_called()


# ---------------------------------------------------------------------------
# handle_event — with rules and users
# ---------------------------------------------------------------------------


class TestHandleEventWithRulesUI:
    async def test_handle_event_creates_notifications_for_users(self):
        svc, _ = _make_service()

        user = _make_user(user_id=5, email="driver@test.com")
        rule = _make_rule(rol_id=2, kanallar=["UI"])
        uow = _make_uow(
            rules=[rule],
            users_by_rol={2: [user]},
        )

        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id=": 10, "trigger": "yakit"}
        )

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            await svc.handle_event(event)

        uow.session.add_all.assert_called_once()
        uow.commit.assert_called_once()

    async def test_handle_event_skips_ws_when_manager_none(self):
        """No crash when notification_ws_manager is None."""
        import app.core.services.notification_service as mod

        svc, _ = _make_service()

        user = _make_user()
        rule = _make_rule(kanallar=["UI"])
        uow = _make_uow(rules=[rule], users_by_rol={1: [user]})

        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 1, "trigger": "x"}
        )

        original = mod.notification_ws_manager
        try:
            mod.notification_ws_manager = None
            with patch(
                "app.core.services.notification_service.UnitOfWork", return_value=uow
            ):
                await svc.handle_event(event)
        finally:
            mod.notification_ws_manager = original

        uow.commit.assert_called_once()

    async def test_handle_event_calls_ws_manager_for_ui_channel(self):
        """When ws_manager is set and channel=UI, send_personal_message is called."""
        import app.core.services.notification_service as mod

        svc, _ = _make_service()

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
            with patch(
                "app.core.services.notification_service.UnitOfWork", return_value=uow
            ):
                await svc.handle_event(event)
        finally:
            mod.notification_ws_manager = original

        mock_ws.send_personal_message.assert_called_once()

    async def test_handle_event_email_channel_does_not_crash(self):
        """EMAIL channel logs a message but does not raise."""

        svc, _ = _make_service()

        user = _make_user()
        rule = _make_rule(kanallar=["EMAIL"])
        uow = _make_uow(rules=[rule], users_by_rol={1: [user]})

        event = Event(type=EventType.SLA_DELAY, data={"sefer_id": 2, "delay_min": 45})

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            await svc.handle_event(event)

        uow.commit.assert_called_once()


# ---------------------------------------------------------------------------
# _format_message
# ---------------------------------------------------------------------------


class TestFormatMessage:
    def _svc(self):
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()
        return svc

    def test_format_sefer_updated(self):
        svc = self._svc()
        event = Event(
            type=EventType.SEFER_UPDATED, data={"sefer_id": 42, "trigger": "sync"}
        )
        header, content = svc._format_message(event)
        assert "42" in header
        assert "sync" in content

    def test_format_sla_delay(self):
        svc = self._svc()
        event = Event(type=EventType.SLA_DELAY, data={"sefer_id": 5, "delay_min": 30})
        header, content = svc._format_message(event)
        assert "SLA" in header or "Gecikme" in header
        assert "30" in content

    def test_format_anomaly_detected(self):
        svc = self._svc()
        event = Event(
            type=EventType.ANOMALY_DETECTED,
            data={"aciklama": "Yakıt anomalisi tespit edildi."},
        )
        header, content = svc._format_message(event)
        assert "Anomali" in header
        assert "Yakıt anomalisi" in content

    def test_format_anomaly_detected_default_content(self):
        svc = self._svc()
        event = Event(type=EventType.ANOMALY_DETECTED, data={})
        _, content = svc._format_message(event)
        assert "sıra dışı" in content

    def test_format_sla_delay_default_delay_min(self):
        svc = self._svc()
        # delay_min missing → defaults to 0
        event = Event(type=EventType.SLA_DELAY, data={"sefer_id": 1})
        _, content = svc._format_message(event)
        assert "0" in content

    def test_format_unknown_event_type(self):
        svc = self._svc()
        # Use a different event type not explicitly handled (SEFER_ADDED is not handled)
        event = Event(type=EventType.SEFER_ADDED, data={"foo": "bar"})
        header, content = svc._format_message(event)
        assert header == "Sistem Mesajı"
        assert "bar" in content


# ---------------------------------------------------------------------------
# get_user_notifications
# ---------------------------------------------------------------------------


class TestGetUserNotifications:
    async def test_returns_list(self):
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()

        notifs = [MagicMock(), MagicMock()]
        uow = _make_uow()
        uow.notification_repo.get_user_notifications = AsyncMock(return_value=notifs)

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            result = await svc.get_user_notifications(user_id=1)

        assert result == notifs


# ---------------------------------------------------------------------------
# mark_as_read
# ---------------------------------------------------------------------------


class TestMarkAsRead:
    async def test_returns_true_on_success(self):
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()

        uow = _make_uow()
        uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=True)

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            result = await svc.mark_as_read(notification_id=10, user_id=7)

        assert result is True
        uow.notification_repo.mark_as_read_for_user.assert_awaited_once_with(10, 7)
        uow.commit.assert_called_once()

    async def test_returns_false_when_not_found(self):
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()

        uow = _make_uow()
        uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=False)

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            result = await svc.mark_as_read(notification_id=999, user_id=7)

        assert result is False
        uow.commit.assert_not_called()

    async def test_ownership_scoped_to_user(self):
        """IDOR guard: başka kullanıcının bildirimi (eşleşme yok) → False,
        commit yok."""
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()

        uow = _make_uow()
        # Repo, sahiplik eşleşmediğinde rowcount=0 → False döner.
        uow.notification_repo.mark_as_read_for_user = AsyncMock(return_value=False)

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            result = await svc.mark_as_read(notification_id=10, user_id=999)

        assert result is False
        uow.notification_repo.mark_as_read_for_user.assert_awaited_once_with(10, 999)
        uow.commit.assert_not_called()


# ---------------------------------------------------------------------------
# mark_all_as_read
# ---------------------------------------------------------------------------


class TestMarkAllAsRead:
    async def test_returns_count(self):
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()

        uow = _make_uow()
        uow.notification_repo.mark_all_as_read = AsyncMock(return_value=5)

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            result = await svc.mark_all_as_read(user_id=1)

        assert result == 5
        uow.commit.assert_called_once()

    async def test_no_commit_when_count_is_zero(self):
        from app.core.services.notification_service import NotificationService

        svc = NotificationService.__new__(NotificationService)
        svc.event_bus = MagicMock()

        uow = _make_uow()
        uow.notification_repo.mark_all_as_read = AsyncMock(return_value=0)

        with patch(
            "app.core.services.notification_service.UnitOfWork", return_value=uow
        ):
            result = await svc.mark_all_as_read(user_id=1)

        assert result == 0
        uow.commit.assert_not_called()
