from typing import List, Union

from fastapi import Depends

from app.api.deps import get_current_user
from app.core.services.security_service import Permission, SecurityService
from app.database.models import Kullanici


class PermissionChecker:
    """
    Dependency factory for granular RBAC.

    Tek bir izin string'i, Permission enum değeri veya
    birden fazla izni ``OR`` mantığıyla birleştiren string listesi kabul eder.
    """

    def __init__(self, required_permission: Union[Permission, str, List[str]]):
        self.required_permission = required_permission

    def __call__(
        self, current_user: Kullanici = Depends(get_current_user)
    ) -> Kullanici:
        SecurityService.verify_permission(current_user, self.required_permission)
        return current_user


def require_yetki(
    permission: Union[Permission, str, List[str]],
) -> PermissionChecker:
    """
    Shortcut for PermissionChecker.

    Kullanım::

        Depends(require_yetki("kullanici_ekle"))
        Depends(require_yetki(["backup_al", "all", "*"]))  # OR semantics
    """
    return PermissionChecker(permission)
