"""Coverage tests for v2/modules/notification/api/notification_routes.py

Targets ~51% → ≥75%  (missed: list_rules, create_rule, get_my_notifications,
mark_all_read, mark_single_read success + 404)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


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
    async def test_list_rules_empty(self, async_client, admin_auth_headers):
        """list_rules returns 200 with empty list when no rules exist."""
        resp = await async_client.get(
            "/api/v1/admin/notifications/rules", headers=admin_auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_rules_returns_rules(
        self, async_client, admin_auth_headers, db_session
    ):
        """list_rules returns seeded notification rules from real DB."""
        from v2.modules.auth_rbac.public import Rol
        from v2.modules.notification.public import BildirimKurali

        role = Rol(ad="notif_test_rol", yetkiler={})
        db_session.add(role)
        await db_session.flush()

        rule = BildirimKurali(
            olay_tipi="YAKIT_ALARMI",
            kanallar=["email", "telegram"],
            alici_rol_id=role.id,
            aktif=True,
        )
        db_session.add(rule)
        await db_session.flush()

        resp = await async_client.get(
            "/api/v1/admin/notifications/rules", headers=admin_auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["olay_tipi"] == "YAKIT_ALARMI"
        assert data[0]["kanallar"] == ["email", "telegram"]


# ---------------------------------------------------------------------------
# POST /notifications/rules
# ---------------------------------------------------------------------------


class TestCreateRule:
    async def test_create_rule_returns_201(
        self, async_client, admin_auth_headers, db_session
    ):
        """create_rule persists to DB and returns 201 with the new rule."""
        from v2.modules.auth_rbac.public import Rol

        role = Rol(ad="notif_create_test_rol", yetkiler={})
        db_session.add(role)
        await db_session.flush()

        resp = await async_client.post(
            "/api/v1/admin/notifications/rules",
            json={
                "olay_tipi": "KAZA",
                "kanallar": ["sms"],
                "alici_rol_id": role.id,
                "aktif": True,
            },
            headers=admin_auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["olay_tipi"] == "KAZA"


# ---------------------------------------------------------------------------
# GET /notifications/my
# ---------------------------------------------------------------------------


class TestGetMyNotifications:
    async def test_my_notifications_returns_list(
        self, async_client, admin_auth_headers
    ):
        """get_my_notifications returns list of notification items."""
        notif = _make_bildirim(bid=99, durum="SENT")

        with patch(
            "v2.modules.notification.api.notification_routes.get_user_notifications",
            AsyncMock(return_value=[notif]),
        ):
            resp = await async_client.get(
                "/api/v1/admin/notifications/my", headers=admin_auth_headers
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == 99
        assert data[0]["okundu"] is False  # SENT != READ

    async def test_my_notifications_read_flag(self, async_client, admin_auth_headers):
        """get_my_notifications sets okundu=True for READ status."""
        notif = _make_bildirim(bid=5, durum="READ")

        with patch(
            "v2.modules.notification.api.notification_routes.get_user_notifications",
            AsyncMock(return_value=[notif]),
        ):
            resp = await async_client.get(
                "/api/v1/admin/notifications/my", headers=admin_auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()[0]["okundu"] is True

    async def test_my_notifications_empty(self, async_client, admin_auth_headers):
        """get_my_notifications returns [] when no notifications."""
        with patch(
            "v2.modules.notification.api.notification_routes.get_user_notifications",
            AsyncMock(return_value=[]),
        ):
            resp = await async_client.get(
                "/api/v1/admin/notifications/my", headers=admin_auth_headers
            )

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_my_notifications_requires_auth(self, async_client):
        """get_my_notifications returns 401 without auth."""
        resp = await async_client.get("/api/v1/admin/notifications/my")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read
# ---------------------------------------------------------------------------


class TestMarkAllRead:
    async def test_mark_all_read_returns_count(self, async_client, admin_auth_headers):
        """mark_all_read returns success=True and count."""
        with patch(
            "v2.modules.notification.api.notification_routes.mark_all_as_read",
            AsyncMock(return_value=5),
        ):
            resp = await async_client.post(
                "/api/v1/admin/notifications/mark-all-read",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 5

    async def test_mark_all_read_zero(self, async_client, admin_auth_headers):
        """mark_all_read returns count=0 when nothing to mark."""
        with patch(
            "v2.modules.notification.api.notification_routes.mark_all_as_read",
            AsyncMock(return_value=0),
        ):
            resp = await async_client.post(
                "/api/v1/admin/notifications/mark-all-read",
                headers=admin_auth_headers,
            )

        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------


class TestMarkSingleRead:
    async def test_mark_single_read_success(self, async_client, admin_auth_headers):
        """mark_single_read returns success=True when notification found."""
        with patch(
            "v2.modules.notification.api.notification_routes.mark_as_read",
            AsyncMock(return_value=True),
        ):
            resp = await async_client.patch(
                "/api/v1/admin/notifications/55/read", headers=admin_auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    async def test_mark_single_read_not_found(self, async_client, admin_auth_headers):
        """mark_single_read returns 404 when notification not found."""
        with patch(
            "v2.modules.notification.api.notification_routes.mark_as_read",
            AsyncMock(return_value=False),
        ):
            resp = await async_client.patch(
                "/api/v1/admin/notifications/9999/read", headers=admin_auth_headers
            )

        assert resp.status_code == 404

    async def test_mark_single_read_requires_auth(self, async_client):
        """mark_single_read returns 401 without auth."""
        resp = await async_client.patch("/api/v1/admin/notifications/1/read")
        assert resp.status_code == 401
