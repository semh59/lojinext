from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.config import settings
from v2.modules.auth_rbac.public import (
    Kullanici,
    get_current_active_user,
    require_yetki,
)
from v2.modules.platform_infra.audit.audit_logger import log_audit_event
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.middleware.slowapi_limiter import limiter
from v2.modules.prediction_ml.schemas import MLTaskRead, ModelVersionRead
from v2.modules.shared_kernel.exceptions import DomainError

logger = get_logger(__name__)


def _headers() -> dict:
    secret = settings.INTERNAL_API_SECRET
    return {"X-Internal-Token": secret} if secret else {}


async def _service_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(
        base_url=settings.PREDICTION_ML_SERVICE_URL, timeout=5.0
    ) as client:
        resp = await client.get(path, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def _service_post(path: str, payload: dict):
    async with httpx.AsyncClient(
        base_url=settings.PREDICTION_ML_SERVICE_URL, timeout=5.0
    ) as client:
        resp = await client.post(path, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


router = APIRouter()


@router.post(
    "/train/{arac_id}",
    response_model=MLTaskRead,
    dependencies=[Depends(require_yetki(["model_egit", "all", "*"]))],
)
@limiter.limit("3/hour")
async def trigger_training(
    arac_id: int,
    request: Request,
    current_user: Kullanici = Depends(get_current_active_user),
):
    """
    Manually trigger model training for a specific vehicle.
    Calculates next version automatically.
    """
    try:
        # Synthetic super-admin has id<=0 and no row in `kullanicilar` —
        # passing it straight through as tetikleyen_kullanici_id violates
        # egitim_kuyrugu_tetikleyen_kullanici_id_fkey (confirmed via curl:
        # POST as the super-admin 500'd with ForeignKeyViolationError).
        # Same pattern already used for the audit-log call below and in
        # the push/subscribe fix (commit b2351f9).
        user_id = current_user.id if current_user.id and current_user.id > 0 else None
        try:
            task = await _service_post(
                f"/train/{arac_id}/schedule", {"user_id": user_id}
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code, detail=exc.response.text
            )
        try:
            await log_audit_event(
                action="ml.train_triggered",
                module="ml",
                entity_id=str(arac_id),
                user_id=user_id,
                new_value={"arac_id": arac_id},
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Audit log failed: %s", exc)
        return task
    except HTTPException as e:
        raise e
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Eğitim başlatılamadı: {str(e)}",
        )


@router.get(
    "/queue",
    response_model=List[MLTaskRead],
    dependencies=[Depends(require_yetki("model_goruntule"))],
)
async def get_training_queue(
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent and pending training tasks."""
    return await _service_get("/queue", params={"limit": limit})


@router.get(
    "/versions/{arac_id}",
    response_model=List[ModelVersionRead],
    dependencies=[Depends(require_yetki("model_goruntule"))],
)
async def get_model_versions(arac_id: int):
    """Get all model versions for a vehicle."""
    return await _service_get(f"/versions/{arac_id}")
