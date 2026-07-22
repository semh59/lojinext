from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.admin_platform.application.health_service import (
    HealthService,
    get_health_service,
)
from v2.modules.admin_platform.schemas import (
    AdminHealthResponse,
    BackupTriggerResponse,
    CircuitBreakerResetResponse,
)
from v2.modules.auth_rbac.public import Kullanici, require_yetki
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=AdminHealthResponse,
    dependencies=[Depends(require_yetki("sistem_saglik_goruntule"))],
)
async def get_admin_health(
    service: HealthService = Depends(get_health_service),
) -> AdminHealthResponse:
    """Admin: detailed health snapshot covering DB, AI, Sentry, breakers, backups."""
    payload = await service.get_admin_health_details()
    return AdminHealthResponse.model_validate(payload)


@router.post(
    "/circuit-breaker/reset",
    response_model=CircuitBreakerResetResponse,
    dependencies=[
        Depends(require_yetki(["circuit_breaker_reset", "backup_al", "all", "*"]))
    ],
)
async def reset_circuit_breaker(
    service_name: str,
    service: HealthService = Depends(get_health_service),
    current_user: Kullanici = Depends(get_current_active_user),
) -> CircuitBreakerResetResponse:
    """Admin: reset the named circuit breaker."""
    payload = await service.reset_circuit_breaker(service_name)
    user_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="health.circuit_breaker_reset",
            module="health",
            entity_id=service_name,
            user_id=user_id,
            new_value={"service_name": service_name},
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)
    return CircuitBreakerResetResponse.model_validate(payload)


@router.post(
    "/backup/trigger",
    response_model=BackupTriggerResponse,
    dependencies=[Depends(require_yetki(["backup_al", "all", "*"]))],
)
async def trigger_manual_backup(
    service: HealthService = Depends(get_health_service),
    current_user: Kullanici = Depends(get_current_active_user),
) -> BackupTriggerResponse:
    """Admin: kick off an asynchronous database backup."""
    payload = await service.trigger_manual_backup()
    user_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="health.backup_triggered",
            module="health",
            entity_id=None,
            user_id=user_id,
            new_value=None,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)
    return BackupTriggerResponse.model_validate(payload)
