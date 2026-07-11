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
from app.config import settings
from app.core.services.admin_audit_service import AdminAuditService
from app.core.services.integration_secrets import (
    KNOWN_SERVICES,
    IntegrationStatus,
    get_integration_statuses,
    set_integration_secret,
)
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.container_health import get_container_status
from app.infrastructure.security.permission_checker import require_yetki

router = APIRouter()
logger = get_logger(__name__)

# servis_adi -> docker-compose service name, for the 2 services whose
# `configured` DB flag alone can't tell an admin whether the integration is
# actually running (bot tokens are typically provisioned via container
# .env, not this panel — see integration_secrets.py's BOT_TOKEN_SERVICES).
_BOT_COMPOSE_SERVICE = {
    "telegram_driver_bot": "telegram-driver-bot",
    "telegram_ops_bot": "telegram-ops-bot",
}


def _env_fallback_present(servis_adi: str) -> Optional[bool]:
    """Same underlying issue as the bot containers, one level milder: these
    3 services' `get_integration_secret()` call sites (route_service.py,
    llm_client.py, etc.) already pass settings.<X>_API_KEY as env_fallback,
    so — unlike bots — the backend itself CAN see whether an env value is
    set. Returns None for non-API-key services (the 2 bots, handled via
    container_running instead)."""
    if servis_adi == "mapbox":
        return bool(
            settings.MAPBOX_API_KEY and settings.MAPBOX_API_KEY.get_secret_value()
        )
    if servis_adi == "openroute":
        return bool(settings.OPENROUTESERVICE_API_KEY)
    if servis_adi == "groq":
        return bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.get_secret_value())
    return None


class IntegrationStatusRead(BaseModel):
    servis_adi: str
    configured: bool
    guncellenme_tarihi: Optional[str] = None
    guncelleyen_id: Optional[int] = None
    container_running: Optional[bool] = None
    container_health: Optional[str] = None
    env_fallback_configured: Optional[bool] = None


class IntegrationKeyUpdate(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=500)


async def _to_status_read(s: IntegrationStatus) -> IntegrationStatusRead:
    container_running: Optional[bool] = None
    container_health: Optional[str] = None
    compose_service = _BOT_COMPOSE_SERVICE.get(s["servis_adi"])
    if compose_service:
        container = await get_container_status(compose_service)
        container_running = container["running"] if container["found"] else None
        container_health = container["health"]
    return IntegrationStatusRead(
        servis_adi=s["servis_adi"],
        configured=s["configured"],
        guncellenme_tarihi=s["guncellenme_tarihi"].isoformat()
        if s["guncellenme_tarihi"]
        else None,
        guncelleyen_id=s["guncelleyen_id"],
        container_running=container_running,
        container_health=container_health,
        env_fallback_configured=_env_fallback_present(s["servis_adi"]),
    )


@router.get("/", response_model=List[IntegrationStatusRead])
async def list_integration_statuses(
    current_user: Annotated[Kullanici, Depends(require_yetki("konfig_goruntule"))],
):
    """List every known integration's configured-status (never the value)."""
    statuses = await get_integration_statuses()
    return [await _to_status_read(s) for s in statuses]


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
    return await _to_status_read(updated)
