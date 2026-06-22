from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Request

from app.database.models import AdminAuditLog, Kullanici
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AdminAuditService:
    """
    Service for administrative audit logging.
    Captures who did what, when, and from where.

    No session is injected — each operation opens its own UnitOfWork so that
    audit records are committed independently of the caller's transaction.
    """

    async def log_action(
        self,
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
        """
        Record an administrative action to the audit log.
        """
        from app.database.unit_of_work import UnitOfWork

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

    @classmethod
    async def log_login(cls, user: Kullanici, request: Request, basarili: bool = True):
        """Helper for login logging."""
        service = cls()
        await service.log_action(
            user=user,
            aksiyon_tipi="LOGIN",
            aciklama="Kullanıcı girişi",
            request=request,
            basarili=basarili,
        )

    @classmethod
    async def log_config_change(
        cls,
        user: Kullanici,
        key: str,
        old_val: Any,
        new_val: Any,
        request: Request,
    ):
        """Helper for config changes."""
        service = cls()
        await service.log_action(
            user=user,
            aksiyon_tipi="CONFIG_UPDATE",
            hedef_tablo="sistem_konfig",
            hedef_id=key,
            eski_deger={"deger": old_val},
            yeni_deger={"deger": new_val},
            aciklama=f"Ayar güncellendi: {key}",
            request=request,
        )
