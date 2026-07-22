from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_sefer_service
from v2.modules.auth_rbac.public import Kullanici, require_permissions
from v2.modules.platform_infra.audit.audit_logger import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.resilience.rate_limiter import RateLimiterDependency
from v2.modules.trip.public import (
    SeferBulkCancel,
    SeferBulkDelete,
    SeferBulkResponse,
    SeferBulkStatusUpdate,
    SeferService,
)

logger = get_logger(__name__)

router = APIRouter()


@router.patch(
    "/bulk/status",
    response_model=SeferBulkResponse,
    dependencies=[Depends(RateLimiterDependency("bulk_status", rate=1.0, period=5.0))],
)
async def bulk_update_trip_status(
    data: SeferBulkStatusUpdate,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Secili seferlerin durumunu toplu guncelle (SUPERVISOR+)."""
    if len(data.sefer_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit: maksimum 500 sefer")
    try:
        return await service.bulk_update_status(
            data.sefer_ids, data.new_status, user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch(
    "/bulk/cancel",
    response_model=SeferBulkResponse,
    dependencies=[Depends(RateLimiterDependency("bulk_cancel", rate=1.0, period=5.0))],
)
async def bulk_cancel_trips(
    data: SeferBulkCancel,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
):
    """Secili seferleri toplu iptal et (SUPERVISOR+)."""
    if len(data.sefer_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit: maksimum 500 sefer")
    return await service.bulk_cancel(
        data.sefer_ids, data.iptal_nedeni, user_id=current_user.id
    )


@router.post("/bulk-delete", response_model=Dict[str, Any])
async def bulk_delete_trips(
    data: SeferBulkDelete,
    current_user: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
    service: SeferService = Depends(get_sefer_service),
) -> Any:
    """Secilen seferleri toplu sil."""
    sefer_ids = data.sefer_ids
    if len(sefer_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk limit: maksimum 500 sefer")
    logger.info(f"Bulk Delete Request: User={current_user.email}, IDs={sefer_ids}")
    if not sefer_ids:
        logger.warning("Bulk delete called with empty ID list")
        return {"success_count": 0, "failed_count": 0, "failed": []}
    actor_id = current_user.id  # capture pre-commit (see create_sefer)
    result = await service.bulk_delete(sefer_ids)
    await log_audit_event(
        module="sefer",
        action="bulk_delete",
        new_value={
            "sefer_ids": sefer_ids,
            "success_count": result.get("success_count"),
        },
        user_id=actor_id,
    )
    return result
