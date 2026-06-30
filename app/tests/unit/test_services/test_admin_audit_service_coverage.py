"""Coverage tests for app/core/services/admin_audit_service.py

Targets ~41% → ≥75%
Covers: log_action (basic, with request, user=None, basarili=False,
        DB exception swallowed), log_login, log_config_change.

0-mock (Dilim 30): patch("app.database.unit_of_work.UnitOfWork") replaced with
narrow patch.object(UnitOfWork, '__aenter__'/__aexit__) so the class itself
is never replaced — only its context-manager dunders are stubbed out.
All assertions are on the returned AdminAuditLog object (built before any DB call).
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(uid: int = 5):
    u = MagicMock()
    u.id = uid
    u.email = "admin@loji.com"
    return u


def _make_request(
    ip: str = "127.0.0.1", ua: str = "TestAgent/1.0", request_id: str = "req-abc"
):
    req = MagicMock()
    req.client = MagicMock()
    req.client.host = ip
    req.headers = {"user-agent": ua}
    req.state = MagicMock()
    req.state.request_id = request_id
    # hasattr check: make sure request_id attribute exists
    type(req.state).request_id = PropertyMock(return_value=request_id)
    return req


def _stub_uow():
    """Return (mock_inst, enter_patch_kwargs, exit_patch_kwargs) for patch.object."""
    inst = AsyncMock()
    inst.session = MagicMock()
    inst.session.add = MagicMock()
    inst.commit = AsyncMock()
    return inst


# ---------------------------------------------------------------------------
# log_action
# ---------------------------------------------------------------------------


class TestLogAction:
    async def test_log_action_basic_returns_audit_log(self):
        """log_action returns an AdminAuditLog without request."""
        from app.core.services.admin_audit_service import AdminAuditService
        from app.database.models import AdminAuditLog

        service = AdminAuditService()
        user = _make_user(uid=1)
        uow_inst = _stub_uow()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await service.log_action(
                user=user,
                aksiyon_tipi="DELETE",
                hedef_tablo="seferler",
                hedef_id="42",
            )

        assert isinstance(result, AdminAuditLog)
        assert result.aksiyon_tipi == "DELETE"
        assert result.hedef_tablo == "seferler"
        assert result.hedef_id == "42"
        assert result.kullanici_id == 1
        assert result.kullanici_email == "admin@loji.com"

    async def test_log_action_with_request_captures_ip(self):
        """log_action extracts ip_adresi, tarayici, istek_id from Request."""
        from app.core.services.admin_audit_service import AdminAuditService

        service = AdminAuditService()
        user = _make_user()
        request = _make_request(ip="10.0.0.1", ua="Mozilla/5.0", request_id="rid-999")
        uow_inst = _stub_uow()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await service.log_action(
                user=user,
                aksiyon_tipi="READ",
                request=request,
            )

        assert result.ip_adresi == "10.0.0.1"
        assert result.tarayici == "Mozilla/5.0"
        assert result.istek_id == "rid-999"

    async def test_log_action_none_user_uses_system_email(self):
        """log_action with user=None sets kullanici_email='system'."""
        from app.core.services.admin_audit_service import AdminAuditService

        service = AdminAuditService()
        uow_inst = _stub_uow()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await service.log_action(
                user=None,
                aksiyon_tipi="SYSTEM_TASK",
            )

        assert result.kullanici_id is None
        assert result.kullanici_email == "system"

    async def test_log_action_basarili_false(self):
        """log_action records basarili=False and hata_mesaji."""
        from app.core.services.admin_audit_service import AdminAuditService

        service = AdminAuditService()
        user = _make_user()
        uow_inst = _stub_uow()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await service.log_action(
                user=user,
                aksiyon_tipi="LOGIN",
                basarili=False,
                hata_mesaji="Hatalı şifre",
            )

        assert result.basarili is False
        assert result.hata_mesaji == "Hatalı şifre"

    async def test_log_action_db_exception_swallowed(self):
        """log_action does not raise when DB commit fails."""
        from app.core.services.admin_audit_service import AdminAuditService

        service = AdminAuditService()
        user = _make_user()

        with patch.object(
            UnitOfWork,
            "__aenter__",
            AsyncMock(side_effect=Exception("DB connection lost")),
        ):
            # Should NOT raise
            result = await service.log_action(
                user=user,
                aksiyon_tipi="DELETE",
            )

        # Still returns the audit log object even if DB failed
        assert result is not None
        assert result.aksiyon_tipi == "DELETE"

    async def test_log_action_with_old_and_new_values(self):
        """log_action stores eski_deger and yeni_deger."""
        from app.core.services.admin_audit_service import AdminAuditService

        service = AdminAuditService()
        user = _make_user()
        uow_inst = _stub_uow()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await service.log_action(
                user=user,
                aksiyon_tipi="CONFIG_UPDATE",
                eski_deger={"deger": "old"},
                yeni_deger={"deger": "new"},
            )

        assert result.eski_deger == {"deger": "old"}
        assert result.yeni_deger == {"deger": "new"}

    async def test_log_action_request_no_client(self):
        """log_action handles request.client=None gracefully."""
        from app.core.services.admin_audit_service import AdminAuditService

        service = AdminAuditService()
        user = _make_user()

        request = MagicMock()
        request.client = None
        request.headers = {}
        request.state = MagicMock(spec=[])  # no request_id attribute
        uow_inst = _stub_uow()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await service.log_action(
                user=user,
                aksiyon_tipi="LOGIN",
                request=request,
            )

        assert result.ip_adresi is None


# ---------------------------------------------------------------------------
# log_login (classmethod)
# ---------------------------------------------------------------------------


class TestLogLogin:
    async def test_log_login_calls_log_action(self):
        """log_login delegates to log_action with LOGIN type."""
        from app.core.services.admin_audit_service import AdminAuditService

        user = _make_user(uid=10)
        request = _make_request()

        with patch.object(
            AdminAuditService, "log_action", new_callable=AsyncMock
        ) as mock_log:
            await AdminAuditService.log_login(user=user, request=request, basarili=True)
            mock_log.assert_called_once()
            kwargs = mock_log.call_args[1]
            assert kwargs["aksiyon_tipi"] == "LOGIN"
            assert kwargs["basarili"] is True

    async def test_log_login_failed(self):
        """log_login passes basarili=False."""
        from app.core.services.admin_audit_service import AdminAuditService

        user = _make_user()
        request = _make_request()

        with patch.object(
            AdminAuditService, "log_action", new_callable=AsyncMock
        ) as mock_log:
            await AdminAuditService.log_login(
                user=user, request=request, basarili=False
            )
            kwargs = mock_log.call_args[1]
            assert kwargs["basarili"] is False


# ---------------------------------------------------------------------------
# log_config_change (classmethod)
# ---------------------------------------------------------------------------


class TestLogConfigChange:
    async def test_log_config_change_delegates_correctly(self):
        """log_config_change passes CONFIG_UPDATE type with old/new values."""
        from app.core.services.admin_audit_service import AdminAuditService

        user = _make_user()
        request = _make_request()

        with patch.object(
            AdminAuditService, "log_action", new_callable=AsyncMock
        ) as mock_log:
            await AdminAuditService.log_config_change(
                user=user,
                key="MAX_SPEED",
                old_val=90,
                new_val=120,
                request=request,
            )
            mock_log.assert_called_once()
            kwargs = mock_log.call_args[1]
            assert kwargs["aksiyon_tipi"] == "CONFIG_UPDATE"
            assert kwargs["hedef_tablo"] == "sistem_konfig"
            assert kwargs["hedef_id"] == "MAX_SPEED"
            assert kwargs["eski_deger"] == {"deger": 90}
            assert kwargs["yeni_deger"] == {"deger": 120}
