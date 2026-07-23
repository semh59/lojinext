"""FastAPI-aware RBAC dependency factory.

2026-07-22 (Kalem 3 commit 1): domain/'den application/'a taşındı —
`Depends(get_current_user)` kullanan bu sınıf zaten FastAPI-farkında
(domain/ I/O-suz olmalı kuralına aykırıydı); `get_current_user`'ın da aynı
turda `application/authenticate.py`'ye taşınmasıyla artık aynı katmanda
(application) bir sibling import — `module-internal-layers` kontratının
"domain infrastructure'ı import edemez" kısıtı artık bu dosya için hiç
geçerli değil (application→infrastructure zaten izinli yön), bu yüzden
`.importlinter`'daki eski `auth_rbac.domain.permission_checker ->
auth_rbac.infrastructure.models` ignore_imports satırları (2 kontratta)
silindi — artık gereksiz.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union

from fastapi import Depends

from v2.modules.auth_rbac.application.authenticate import get_current_user
from v2.modules.auth_rbac.domain.security_service import Permission, SecurityService

if TYPE_CHECKING:
    from v2.modules.auth_rbac.infrastructure.models import Kullanici


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
