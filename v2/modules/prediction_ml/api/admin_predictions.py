"""Faz 1 — Admin tahmin backfill manuel tetik endpoint'i."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from starlette.responses import JSONResponse

from app.api.deps import get_background_job_manager, get_current_active_admin
from app.database.models import Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.background.job_manager import (
    AsyncJobStatus,
    BackgroundJobManager,
)
from app.infrastructure.logging.logger import get_logger
from v2.modules.prediction_ml.application.prediction_backfill_service import (
    PredictionBackfillService,
)
from v2.modules.prediction_ml.schemas import BackfillTriggerResponse

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/predictions/backfill",
    status_code=202,
    response_model=BackfillTriggerResponse,
)
async def trigger_prediction_backfill(
    limit: int = Query(50, ge=1, le=500),
    admin: Kullanici = Depends(get_current_active_admin),
    job_manager: BackgroundJobManager = Depends(get_background_job_manager),
) -> JSONResponse:
    """tahmini_tuketim=NULL seferleri estimator ile doldurur (arka planda çalışır).

    Gece beat task'i (prediction.backfill_missing) ile aynı servisi kullanır.
    limit=500 ve throttle_s=0.5 ile çalışma süresi 250+ saniye olabileceğinden
    istek senkron değil, arka plan job'u olarak yürütülür.
    GET /trips/tasks/{task_id}/status ile durum izlenebilir.
    """
    svc = PredictionBackfillService()
    job_id = await job_manager.submit(svc.backfill, limit=limit)
    user_id = admin.id if admin.id and admin.id > 0 else None
    try:
        await log_audit_event(
            action="predictions.backfill_triggered",
            module="predictions",
            entity_id=None,
            user_id=user_id,
            new_value={"limit": limit, "job_id": job_id},
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)
    return JSONResponse(
        status_code=202,
        content={"status": AsyncJobStatus.PROCESSING.value, "task_id": job_id},
    )
