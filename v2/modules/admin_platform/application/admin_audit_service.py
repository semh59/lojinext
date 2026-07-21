"""Yönetici (admin) aksiyon audit logu — ``admin_audit_log`` tablosuna yazım.

Eski ``AdminAuditService`` sınıfının B.1 gereği dissolve edilmiş hali: sınıf
hiçbir alan tutmuyordu (her metod kendi ``UnitOfWork``'ünü açıyordu),
gerçek mutable state yoktu.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.admin_platform.infrastructure.models import AdminAuditLog
from v2.modules.auth_rbac.public import Kullanici

logger = get_logger(__name__)


async def log_action(
    user: Optional[Kullanici],
    aksiyon_tipi: str,
    hedef_tablo: Optional[str] = None,
    hedef_id: Optional[str] = None,
    aciklama: Optional[str] = None,
    eski_deger: Optional[Dict[str, Any]] = None,
    yeni_deger: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    basarili: bool = True,
    hata_mesaji: Optional[str] = None,
    sure_ms: Optional[int] = None,
) -> AdminAuditLog:
    """Record an administrative action to the audit log."""
    audit_log = AdminAuditLog(
        kullanici_id=user.id if user and user.id > 0 else None,
        kullanici_email=user.email if user else "system",
        aksiyon_tipi=aksiyon_tipi,
        hedef_tablo=hedef_tablo,
        hedef_id=hedef_id,
        aciklama=aciklama,
        eski_deger=eski_deger,
        yeni_deger=yeni_deger,
        basarili=basarili,
        hata_mesaji=hata_mesaji,
        sure_ms=sure_ms,
        zaman=datetime.now(timezone.utc),
    )

    if request:
        audit_log.ip_adresi = request.client.host if request.client else None
        audit_log.tarayici = request.headers.get("user-agent")
        audit_log.istek_id = (
            request.state.request_id
            if hasattr(request.state, "request_id")
            else None
        )

    try:
        async with UnitOfWork() as uow:
            uow.session.add(audit_log)
            await uow.commit()
    except Exception as e:
        logger.error(f"Failed to save audit log: {e}")
        # Don't raise — audit log failure shouldn't stop the main action

    return audit_log


async def log_login(user: Kullanici, request: Request, basarili: bool = True) -> None:
    """Helper for login logging."""
    await log_action(
        user=user,
        aksiyon_tipi="LOGIN",
        aciklama="Kullanıcı girişi",
        request=request,
        basarili=basarili,
    )


async def log_config_change(
    user: Kullanici,
    key: str,
    old_val: Any,
    new_val: Any,
    request: Request,
) -> None:
    """Helper for config changes."""
    await log_action(
        user=user,
        aksiyon_tipi="CONFIG_UPDATE",
        hedef_tablo="sistem_konfig",
        hedef_id=key,
        eski_deger={"deger": old_val},
        yeni_deger={"deger": new_val},
        aciklama=f"Ayar güncellendi: {key}",
        request=request,
    )
