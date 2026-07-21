import json
import logging
from datetime import datetime
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.deps import get_current_active_user
from app.config import settings
from app.database.models import BakimTipi, Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from v2.modules.auth_rbac.public import require_yetki
from v2.modules.fleet.application.create_maintenance_record import (
    create_maintenance_record,
)
from v2.modules.fleet.application.export_maintenance_calendar import (
    generate_ics_for_maintenance,
)
from v2.modules.fleet.application.get_maintenance_ics_data import (
    get_maintenance_ics_data,
)
from v2.modules.fleet.application.get_maintenance_predictions import (
    get_all_maintenance_predictions,
    get_maintenance_prediction_for_vehicle,
)
from v2.modules.fleet.application.get_vehicle_maintenance_history import (
    get_upcoming_maintenance_alerts,
    get_vehicle_maintenance_history,
    mark_maintenance_completed,
)
from v2.modules.fleet.application.maintenance_cache import PREDICTIONS_CACHE_ALL
from v2.modules.fleet.schemas import (
    MaintenanceAlertItem,
    MaintenanceCompleteResponse,
    MaintenancePrediction,
    MaintenanceRecordResponse,
)
from v2.modules.shared_kernel.schemas.api_responses import ICS_RESPONSES

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_redis():
    """Async Redis client; başarısızlıkta None."""
    try:
        import redis.asyncio as aioredis

        return aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
    except Exception as exc:
        logger.debug("Maintenance redis init failed: %s", exc)
        return None


class MaintenanceCreateSchema(BaseModel):
    arac_id: int
    bakim_tipi: BakimTipi
    km_bilgisi: int
    bakim_tarihi: datetime
    maliyet: float = 0.0
    detaylar: str = ""


@router.post(
    "/",
    response_model=MaintenanceRecordResponse,
    dependencies=[Depends(require_yetki(["ariza_bildir", "bakim_ekle", "all", "*"]))],
)
async def create_maintenance(
    data: MaintenanceCreateSchema,
) -> MaintenanceRecordResponse:
    """Admin: create a new maintenance record."""
    record = await create_maintenance_record(
        arac_id=data.arac_id,
        bakim_tipi=data.bakim_tipi,
        km_bilgisi=data.km_bilgisi,
        bakim_tarihi=data.bakim_tarihi,
        maliyet=data.maliyet,
        detaylar=data.detaylar,
    )
    return MaintenanceRecordResponse.model_validate(record)


@router.get(
    "/alerts",
    response_model=List[MaintenanceAlertItem],
    dependencies=[Depends(require_yetki(["admin", "super_admin", "fleet_manager"]))],
)
async def get_upcoming_alerts() -> List[MaintenanceAlertItem]:
    """List maintenance tasks that are due or overdue."""
    alerts = await get_upcoming_maintenance_alerts()
    return [MaintenanceAlertItem.model_validate(a) for a in alerts]


# ── Feature D — Tahmine Dayalı Bakım endpoint'leri ─────────────────────
# NOT: `/predictions` literal route, `/{arac_id}` catch-all'dan ÖNCE
# kayıtlı olmak zorundadır (FastAPI registration-order matching).


@router.get(
    "/predictions",
    response_model=List[MaintenancePrediction],
    dependencies=[
        Depends(require_yetki(["bakim_oku", "admin", "super_admin", "fleet_manager"]))
    ],
)
async def get_all_predictions(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> List[MaintenancePrediction]:
    """Tüm aktif araçlar için PERIYODIK bakım tahmini.

    Feature flag `MAINTENANCE_PREDICTOR_ENABLED=False` → 503.
    Redis cache (TTL 1 saat); bakım create/complete'te invalidate edilir.
    """
    if not settings.MAINTENANCE_PREDICTOR_ENABLED:
        raise HTTPException(status_code=503, detail="Bakım tahmin modülü devre dışı")

    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            cached = await redis_client.get(PREDICTIONS_CACHE_ALL)
            if cached:
                return [
                    MaintenancePrediction.model_validate_json(j)
                    for j in json.loads(cached)
                ]
        except Exception as exc:
            logger.warning("Predictions cache read failed: %s", exc)

    preds = await get_all_maintenance_predictions()
    result = [MaintenancePrediction.model_validate(p) for p in preds]

    if redis_client is not None:
        try:
            await redis_client.setex(
                PREDICTIONS_CACHE_ALL,
                settings.MAINTENANCE_PREDICTOR_CACHE_TTL_S,
                json.dumps([p.model_dump_json() for p in result]),
            )
        except Exception as exc:
            logger.warning("Predictions cache write failed: %s", exc)

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="predictions_viewed",
            module="maintenance",
            entity_id=None,
            user_id=creator_id,
            new_value={"count": len(result), "scope": "all"},
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)

    return result


@router.get(
    "/predictions/{arac_id}",
    response_model=MaintenancePrediction,
    dependencies=[
        Depends(require_yetki(["bakim_oku", "admin", "super_admin", "fleet_manager"]))
    ],
)
async def get_prediction_for_arac(
    arac_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> MaintenancePrediction:
    """Tek araç için PERIYODIK bakım tahmini."""
    if not settings.MAINTENANCE_PREDICTOR_ENABLED:
        raise HTTPException(status_code=503, detail="Bakım tahmin modülü devre dışı")
    pred = await get_maintenance_prediction_for_vehicle(arac_id)
    if pred is None:
        raise HTTPException(status_code=404, detail="Araç bulunamadı")

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="predictions_viewed",
            module="maintenance",
            entity_id=str(arac_id),
            user_id=creator_id,
            new_value={"scope": "single"},
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)

    return MaintenancePrediction.model_validate(pred)


@router.get(
    "/{bakim_id}/ics",
    dependencies=[
        Depends(RateLimiterDependency("ics_download", rate=10.0, period=60.0)),
        Depends(require_yetki(["bakim_oku", "admin", "super_admin", "fleet_manager"])),
    ],
    responses=ICS_RESPONSES,
    response_model=None,
    response_class=Response,
)
async def download_ics(
    bakim_id: int,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> Response:
    """RFC 5545 .ics dosyası — Outlook/Google Calendar için takvim aktarımı.

    UTF-8 charset, line folding dahil; Türkçe karakterler korunur.
    """
    result = await get_maintenance_ics_data(bakim_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Bakım bulunamadı")
    bakim_row, arac_row = result

    ics_body = generate_ics_for_maintenance(bakim_row, arac_row)
    return Response(
        content=ics_body.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": (f'attachment; filename="bakim-{bakim_id}.ics"'),
        },
    )


# ── Mevcut endpoint'ler (route ordering için /predictions sonrası) ─────


@router.get(
    "/{arac_id}",
    response_model=List[MaintenanceRecordResponse],
    dependencies=[Depends(require_yetki(["admin", "super_admin", "fleet_manager"]))],
)
async def get_vehicle_history(arac_id: int) -> List[MaintenanceRecordResponse]:
    """Full maintenance history for a single vehicle."""
    history = await get_vehicle_maintenance_history(arac_id)
    return [MaintenanceRecordResponse.model_validate(r) for r in history]


@router.patch(
    "/{bakim_id}/complete",
    response_model=MaintenanceCompleteResponse,
    dependencies=[Depends(require_yetki(["bakim_duzenle", "all", "*"]))],
)
async def mark_complete(bakim_id: int) -> MaintenanceCompleteResponse:
    """Mark a maintenance record as completed."""
    success = await mark_maintenance_completed(bakim_id)
    return MaintenanceCompleteResponse(success=success)
