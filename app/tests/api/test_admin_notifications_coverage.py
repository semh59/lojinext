"""Coverage tests for app/api/v1/endpoints/admin_notifications.py

Targets ~51% → ≥75%  (missed: list_rules, create_rule, get_my_notifications,
mark_all_read, mark_single_read success + 404)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client():
    from httpx import AsyncClient
    from httpx._transports.asgi import ASGITransport

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _fake_user(user_id: int = 42):
    u = MagicMock()
    u.id = user_id
    u.email = "test@example.com"
    u.aktif = True
    return u


def _make_bildirim(bid: int = 1, durum: str = "SENT"):
    n = MagicMock()
    n.id = bid
    n.baslik = "Test Başlık"
    n.icerik = "Test içerik"
    n.olay_tipi = "YAKIT_ALARMI"
    n.kanal = "email"
    n.durum = durum
    n.olusturma_tarihi = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    return n


# ---------------------------------------------------------------------------
# GET /notifications/rules
# ---------------------------------------------------------------------------


class TestListRules:
    async def test_list_rules_empty(self):
        """list_rules returns 200 with empty list when no rules exist."""
        from app.api.deps import get_current_user
        from app.core.services.security_service import SecurityService
        from app.main import app

        user = _fake_user()

        async def _fake_user_dep():
            return user

        with (
            patch("app.database.unit_of_work.UnitOfWork") as MockUow,
            patch.object(SecurityService, "verify_permission", return_value=None),
        ):
            uow_inst = AsyncMock()
            uow_inst.notification_repo.get_all_rules = AsyncMock(return_value=[])
            MockUow.return_value.__aenter__ = AsyncMock(return_value=uow_inst)
            MockUow.return_value.__aexit__ = AsyncMock(return_value=False)

            app.dependency_overrides[get_current_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/admin/notifications/rules")
                assert resp.status_code == 200
                assert resp.json() == []
            finally:
                app.dependency_overrides.clear()

    async def test_list_rules_returns_rules(self):
        """list_rules returns list of notification rules."""
        from app.api.deps import get_current_user
        from app.core.services.security_service import SecurityService
        from app.main import app

        user = _fake_user()

        async def _fake_user_dep():
            return user

        mock_rule = MagicMock()
        mock_rule.id = 1
        mock_rule.olay_tipi = "YAKIT_ALARMI"
        mock_rule.kanallar = ["email", "telegram"]
        mock_rule.alici_rol_id = 2
        mock_rule.aktif = True

        with (
            patch("app.database.unit_of_work.UnitOfWork") as MockUow,
            patch.object(SecurityService, "verify_permission", return_value=None),
        ):
            uow_inst = AsyncMock()
            uow_inst.notification_repo.get_all_rules = AsyncMock(
                return_value=[mock_rule]
            )
            MockUow.return_value.__aenter__ = AsyncMock(return_value=uow_inst)
            MockUow.return_value.__aexit__ = AsyncMock(return_value=False)

            app.dependency_overrides[get_current_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/admin/notifications/rules")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                assert data[0]["olay_tipi"] == "YAKIT_ALARMI"
                assert data[0]["kanallar"] == ["email", "telegram"]
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /notifications/rules
# ---------------------------------------------------------------------------


class TestCreateRule:
    async def test_create_rule_returns_201(self):
        """create_rule returns 201 with the new rule."""
        from app.api.deps import get_current_user
        from app.core.services.security_service import SecurityService
        from app.main import app

        user = _fake_user()

        async def _fake_user_dep():
            return user

        mock_rule = MagicMock()
        mock_rule.id = 10
        mock_rule.olay_tipi = "KAZA"
        mock_rule.kanallar = ["sms"]
        mock_rule.alici_rol_id = 3
        mock_rule.aktif = True

        with (
            patch("app.database.unit_of_work.UnitOfWork") as MockUow,
            patch.object(SecurityService, "verify_permission", return_value=None),
        ):
            uow_inst = AsyncMock()
            uow_inst.notification_repo.create_rule = AsyncMock(return_value=mock_rule)
            uow_inst.commit = AsyncMock()
            MockUow.return_value.__aenter__ = AsyncMock(return_value=uow_inst)
            MockUow.return_value.__aexit__ = AsyncMock(return_value=False)

            app.dependency_overrides[get_current_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.post(
                        "/api/v1/admin/notifications/rules",
                        json={
                            "olay_tipi": "KAZA",
                            "kanallar": ["sms"],
                            "alici_rol_id": 3,
                            "aktif": True,
                        },
                    )
                assert resp.status_code == 201
                data = resp.json()
                assert data["olay_tipi"] == "KAZA"
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /notifications/my
# ---------------------------------------------------------------------------


class TestGetMyNotifications:
    async def test_my_notifications_returns_list(self):
        """get_my_notifications returns list of notification items."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user(user_id=7)
        notif = _make_bildirim(bid=99, durum="SENT")

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.get_user_notifications = AsyncMock(return_value=[notif])

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/admin/notifications/my")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) == 1
                assert data[0]["id"] == 99
                assert data[0]["okundu"] is False  # SENT != READ
            finally:
                app.dependency_overrides.clear()

    async def test_my_notifications_read_flag(self):
        """get_my_notifications sets okundu=True for READ status."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user(user_id=7)
        notif = _make_bildirim(bid=5, durum="READ")

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.get_user_notifications = AsyncMock(return_value=[notif])

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/admin/notifications/my")
                assert resp.status_code == 200
                assert resp.json()[0]["okundu"] is True
            finally:
                app.dependency_overrides.clear()

    async def test_my_notifications_empty(self):
        """get_my_notifications returns [] when no notifications."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user()

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.get_user_notifications = AsyncMock(return_value=[])

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/admin/notifications/my")
                assert resp.status_code == 200
                assert resp.json() == []
            finally:
                app.dependency_overrides.clear()

    async def test_my_notifications_requires_auth(self):
        """get_my_notifications returns 401 without auth."""
        async with _make_client() as client:
            resp = await client.get("/api/v1/admin/notifications/my")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read
# ---------------------------------------------------------------------------


class TestMarkAllRead:
    async def test_mark_all_read_returns_count(self):
        """mark_all_read returns success=True and count."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user(user_id=11)

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.mark_all_as_read = AsyncMock(return_value=5)

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.post(
                        "/api/v1/admin/notifications/mark-all-read"
                    )
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["count"] == 5
            finally:
                app.dependency_overrides.clear()

    async def test_mark_all_read_zero(self):
        """mark_all_read returns count=0 when nothing to mark."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user(user_id=11)

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.mark_all_as_read = AsyncMock(return_value=0)

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.post(
                        "/api/v1/admin/notifications/mark-all-read"
                    )
                assert resp.status_code == 200
                assert resp.json()["count"] == 0
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------


class TestMarkSingleRead:
    async def test_mark_single_read_success(self):
        """mark_single_read returns success=True when notification found."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user(user_id=3)

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.mark_as_read = AsyncMock(return_value=True)

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.patch("/api/v1/admin/notifications/55/read")
                assert resp.status_code == 200
                assert resp.json()["success"] is True
            finally:
                app.dependency_overrides.clear()

    async def test_mark_single_read_not_found(self):
        """mark_single_read returns 404 when notification not found."""
        from app.api.deps import get_current_active_user
        from app.main import app

        user = _fake_user(user_id=3)

        async def _fake_user_dep():
            return user

        with patch(
            "app.api.v1.endpoints.admin_notifications.NotificationService"
        ) as MockSvc:
            svc = MockSvc.return_value
            svc.mark_as_read = AsyncMock(return_value=False)

            app.dependency_overrides[get_current_active_user] = _fake_user_dep
            try:
                async with _make_client() as client:
                    resp = await client.patch("/api/v1/admin/notifications/9999/read")
                assert resp.status_code == 404
            finally:
                app.dependency_overrides.clear()

    async def test_mark_single_read_requires_auth(self):
        """mark_single_read returns 401 without auth."""
        async with _make_client() as client:
            resp = await client.patch("/api/v1/admin/notifications/1/read")
        assert resp.status_code == 401
