from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit


def _make_user(role_name="admin", aktif=True, yetkiler=None):
    """Build a minimal mock Kullanici with a Rol attached."""
    rol = MagicMock()
    rol.ad = role_name
    rol.yetkiler = yetkiler if yetkiler is not None else {}

    user = MagicMock()
    user.aktif = aktif
    user.rol = rol
    return user


class TestSecurityService:
    def test_service_exists(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        assert SecurityService is not None

    def test_basic_initialization(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        # Class-level role mapping must contain key tiers
        assert "admin" in SecurityService.ROLE_PERMISSIONS
        assert "super_admin" in SecurityService.ROLE_PERMISSIONS
        assert "user" in SecurityService.ROLE_PERMISSIONS
        assert Permission.ADMIN in SecurityService.ROLE_PERMISSIONS["admin"]

    def test_happy_path_admin_has_write(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        user = _make_user(role_name="admin")
        assert SecurityService.has_permission(user, Permission.WRITE) is True

    def test_super_admin_bypasses_all(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        user = _make_user(role_name="super_admin")
        # Even SUPERADMIN permission should be granted
        assert SecurityService.has_permission(user, Permission.SUPERADMIN) is True

    def test_error_handling_inactive_user_denied(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        user = _make_user(role_name="admin", aktif=False)
        assert SecurityService.has_permission(user, Permission.READ) is False

    def test_edge_case_none_user(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        assert SecurityService.has_permission(None, Permission.READ) is False

    def test_granular_string_permission_match(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="operator", yetkiler={"sefer:onayla": True})
        assert SecurityService.has_permission(user, "sefer:onayla") is True

    def test_granular_string_permission_denied(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="operator", yetkiler={"sefer:goruntule": True})
        assert SecurityService.has_permission(user, "sefer:sil") is False

    def test_wildcard_permission_grants_all(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="operator", yetkiler={"*": True})
        assert SecurityService.has_permission(user, "any:action") is True

    def test_verify_permission_raises_403(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        user = _make_user(role_name="user")  # READ only
        with pytest.raises(HTTPException) as exc_info:
            SecurityService.verify_permission(user, Permission.DELETE)
        assert exc_info.value.status_code == 403

    def test_verify_permission_passes_for_admin(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        user = _make_user(role_name="admin")
        # Should not raise
        SecurityService.verify_permission(user, Permission.WRITE)

    def test_apply_isolation_admin_no_filter_added(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="admin")
        filters = {"arac_id": 5}
        result = SecurityService.apply_isolation(user, filters)
        assert "sofor_id" not in result or result.get("sofor_id") != -1

    def test_apply_isolation_no_permission_injects_impossible_filter(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="unknown", yetkiler={})
        filters = {}
        result = SecurityService.apply_isolation(user, filters)
        assert result.get("sofor_id") == -1

    def test_verify_ownership_admin_allowed(self):
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="admin")
        # Should not raise even for a different owner
        SecurityService.verify_ownership(user, owner_id=999)

    def test_integration_with_mock(self):
        """List[str] permission check: at least one match grants access."""
        from v2.modules.auth_rbac.domain.security_service import SecurityService

        user = _make_user(role_name="op", yetkiler={"rota:goruntule": True})
        assert (
            SecurityService.has_permission(user, ["rota:goruntule", "rota:duzenle"])
            is True
        )

    def test_return_type_validation(self):
        from v2.modules.auth_rbac.domain.security_service import (
            Permission,
            SecurityService,
        )

        user = _make_user(role_name="user")
        result = SecurityService.has_permission(user, Permission.READ)
        assert isinstance(result, bool)
