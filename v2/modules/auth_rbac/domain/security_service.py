from __future__ import annotations

from enum import IntFlag, auto
from typing import TYPE_CHECKING, Any, Dict, List, Union

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from v2.modules.auth_rbac.infrastructure.models import Kullanici


class Permission(IntFlag):
    NONE = 0
    READ = auto()
    WRITE = auto()
    DELETE = auto()
    ADMIN = auto()
    SUPERADMIN = auto()


class SecurityService:
    """
    Sovereign Security Service for Zero-Defect RBAC and Isolation.

    B.1 istisnası: bu sınıf yalnız ``@classmethod`` içerir, hiçbir
    constructor/instance-state yok — namespace/enum-benzeri kullanım
    (Permission enum ile birlikte). Free function'a bölünmedi çünkü
    kaldırılan diğer servis sınıflarının (UserService/PreferenceService/
    LicenseEngine) aksine burada state/DI parametresi hiç olmadı, sadece
    ilgili beş fonksiyonu bir arada gruplayan bir isim alanı — CLAUDE.md'de
    dokümante.
    """

    ROLE_PERMISSIONS: Dict[str, Permission] = {
        "user": Permission.READ,
        "driver": Permission.READ,
        "admin": Permission.READ
        | Permission.WRITE
        | Permission.DELETE
        | Permission.ADMIN,
        "super_admin": Permission.READ
        | Permission.WRITE
        | Permission.DELETE
        | Permission.ADMIN
        | Permission.SUPERADMIN,
    }

    @classmethod
    def has_permission(
        cls, user: Kullanici, required_permission: Union[Permission, str, List[str]]
    ) -> bool:
        """
        Check if user has required permission.
        Supports both legacy bitwise flags and new granular string keys.
        """
        if not user or not user.aktif:
            return False

        # Super Admin bypass
        user_role_name = getattr(user.rol, "ad", None) if user.rol else None
        if user_role_name == "super_admin":
            return True

        # New Granular Permission Check (String or List[String])
        if isinstance(required_permission, (str, list)):
            if not user.rol or not user.rol.yetkiler:
                return False

            # Admin/SuperAdmin bypass for granular checks is already handled above
            # specifically for role names, but here we check permissions.
            perms_to_check = (
                [required_permission]
                if isinstance(required_permission, str)
                else required_permission
            )

            # Wildcard match
            if user.rol.yetkiler.get("*"):
                return True

            # Match at least one
            for perm in perms_to_check:
                if user.rol.yetkiler.get(perm):
                    return True
            return False

        # Legacy Bitwise Check (Permission enum)
        role_name = user.rol.ad if user.rol else "user"
        user_permission = cls.ROLE_PERMISSIONS.get(role_name, Permission.NONE)
        return bool(user_permission & required_permission)

    @classmethod
    def verify_permission(
        cls,
        user: Kullanici,
        required_permission: Union[Permission, str, List[str]],
    ) -> None:
        """Raise HTTPException if permission is missing."""
        if not cls.has_permission(user, required_permission):
            perm_name = (
                required_permission.name
                if isinstance(required_permission, Permission)
                else required_permission
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Erişim Reddedildi: {perm_name} yetkisi gerekli.",
            )

    @classmethod
    def verify_ownership(
        cls,
        user: Kullanici,
        owner_id: Union[int, None],
        field_name: str = "sofor_id",
    ) -> None:
        """Verify data ownership for isolation.

        Admin: full pass.
        Driver users (user.sofor_id set): must match owner_id exactly.
        Non-driver users (user.sofor_id is None) with READ: full pass (managers).
        Anyone else: denied.
        """
        if cls.has_permission(user, Permission.ADMIN):
            return

        if field_name == "sofor_id":
            user_sofor_id = getattr(user, "sofor_id", None)
            if user_sofor_id is None:
                # Non-driver staff: READ permission grants full visibility
                if cls.has_permission(user, Permission.READ):
                    return
            else:
                # Driver: may only access their own records
                if user_sofor_id == owner_id:
                    return
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Erişim Reddedildi: Bu kayıt size ait değil.",
                )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Erişim Reddedildi: Okuma yetkiniz bulunmamaktadır.",
        )

    @classmethod
    def apply_isolation(
        cls, user: Kullanici, filters: Dict[str, Any], field_name: str = "sofor_id"
    ) -> Dict[str, Any]:
        """Permission-based filter refinement for a single-tenant deployment.

        This is **not** tenant isolation — the system is single-tenant and has
        no `tenant_id` column. The helper just blocks users without READ
        permission by injecting an impossible filter value. Admins and
        READ-permissioned users see everything.
        """
        if cls.has_permission(user, Permission.ADMIN):
            return filters

        if cls.has_permission(user, Permission.READ):
            return filters

        # No permissions at all — restrict everything via an impossible match.
        filters[field_name] = -1
        return filters
