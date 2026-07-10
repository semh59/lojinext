"""Admin-configurable external API keys (Mapbox/OpenRoute/Groq).

Write-only by design: PUT accepts a plaintext key and stores it encrypted;
every read path (GET) returns status metadata only — `configured: bool` +
who/when it was last set — the value itself is never included in any
response, matching the product requirement that nobody (including admins)
can read a previously-entered key back, only replace it.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.middleware.rate_limiter import limiter
from app.core.services.admin_audit_service import AdminAuditService
from app.core.services.integration_secrets import (
    KNOWN_SERVICES,
    get_integration_statuses,
    set_integration_secret,
)
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.permission_checker import require_yetki

router = APIRouter()
logger = get_logger(__name__)


class IntegrationStatusRead(BaseModel):
    servis_adi: str
    configured: bool
    guncellenme_tarihi: Optional[str] = None
    guncelleyen_id: Optional[int] = None


class IntegrationKeyUpdate(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=500)


@router.get("/", response_model=List[IntegrationStatusRead])
async def list_integration_statuses(
    current_user: Annotated[Kullanici, Depends(require_yetki("konfig_goruntule"))],
):
    """List every known integration's configured-status (never the value)."""
    statuses = await get_integration_statuses()
    return [
        IntegrationStatusRead(
            servis_adi=s["servis_adi"],
            configured=s["configured"],
            guncellenme_tarihi=s["guncellenme_tarihi"].isoformat()
            if s["guncellenme_tarihi"]
            else None,
            guncelleyen_id=s["guncelleyen_id"],
        )
        for s in statuses
    ]


@router.put("/{servis_adi}", response_model=IntegrationStatusRead)
@limiter.limit("20/hour")
async def update_integration_key(
    servis_adi: str,
    data: IntegrationKeyUpdate,
    request: Request,
    current_user: Annotated[Kullanici, Depends(require_yetki("konfig_duzenle"))],
):
    """Set/replace a service's API key. The plaintext is written once and
    never echoed back — response and audit log both carry only a masked
    placeholder, never the actual value."""
    if servis_adi not in KNOWN_SERVICES:
        raise HTTPException(
            status_code=404, detail=f"Bilinmeyen entegrasyon servisi: {servis_adi}"
        )
    try:
        await set_integration_secret(servis_adi, data.api_key, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Audit trail records THAT a key was changed, never the value itself.
    audit_service = AdminAuditService()
    await audit_service.log_config_change(
        user=current_user,
        key=f"entegrasyon:{servis_adi}",
        old_val="***",
        new_val="***updated***",
        request=request,
    )

    statuses = await get_integration_statuses()
    updated = next(s for s in statuses if s["servis_adi"] == servis_adi)
    return IntegrationStatusRead(
        servis_adi=updated["servis_adi"],
        configured=updated["configured"],
        guncellenme_tarihi=updated["guncellenme_tarihi"].isoformat()
        if updated["guncellenme_tarihi"]
        else None,
        guncelleyen_id=updated["guncelleyen_id"],
    )
