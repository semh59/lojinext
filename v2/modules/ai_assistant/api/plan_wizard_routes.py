"""Feature C — Sefer Planlama Sihirbazı.

Dalga 14 — ``app/api/v1/endpoints/trips.py``'den taşındı. Task dosyası
(``TASKS/modules/trip.md``) bu route'u yanlışlıkla ``route_simulation``'a
atfetmişti; gerçek kod her zaman ``v2.modules.ai_assistant.public.
TripPlannerEngine``'i çağırıyordu (route_simulation'la ilgisi yok) — kök
CLAUDE.md'de de ai_assistant zaten "trip-planner wizard" sahibi olarak
yazıyor. ``api.py``'de hâlâ ``prefix="/trips"`` ile mount edilir — URL
DEĞİŞMEDİ.
"""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_permissions
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
from v2.modules.ai_assistant.public import (
    DriverSuggestion,
    PlanInput,
    PlanWizardRequest,
    PlanWizardResponse,
    TripPlannerEngine,
    VehicleSuggestion,
)
from v2.modules.auth_rbac.public import Kullanici

logger = get_logger(__name__)

router = APIRouter()


@router.post("/plan-wizard", response_model=PlanWizardResponse)
async def plan_wizard(
    payload: PlanWizardRequest,
    _: Annotated[
        None, Depends(RateLimiterDependency("plan_wizard", rate=20.0, period=60.0))
    ],
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
) -> PlanWizardResponse:
    """Feature C — yeni sefer için 3 araç + 3 şoför önerisi.

    Feature flag `TRIP_PLANNER_ENABLED` kapalıysa 503.
    Hard filter boş ise 200 + boş listeler (404 değil).
    """
    from app.config import settings
    from app.infrastructure.audit.audit_logger import log_audit_event
    from v2.modules.prediction_ml.public import PredictionService

    if not settings.TRIP_PLANNER_ENABLED:
        raise HTTPException(status_code=503, detail="Sefer planlama sihirbazı kapalı")

    # route_analysis: payload.guzergah_id verilirse engine kendi UoW'sunda
    # Lokasyon'u fetch eder — endpoint layer DB'ye direkt erişmez.
    inp = PlanInput(
        cikis_yeri=payload.cikis_yeri,
        varis_yeri=payload.varis_yeri,
        mesafe_km=payload.mesafe_km,
        tarih=payload.tarih,
        ascent_m=payload.ascent_m,
        descent_m=payload.descent_m,
        flat_distance_km=payload.flat_distance_km,
        route_analysis=None,  # engine içinde guzergah_id varsa fetch eder
        weight_kg=payload.weight_kg,
        guzergah_id=payload.guzergah_id,
    )

    engine = TripPlannerEngine(PredictionService())
    try:
        result = await engine.plan(inp, top_n=payload.top_n)
    except Exception as exc:
        logger.error("plan_wizard engine failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Planlama motoru başarısız")

    # Audit-iz (PII'siz; sadece kullanım kanıtı)
    try:
        creator_id = (
            current_admin.id if current_admin.id and current_admin.id > 0 else None
        )
        await log_audit_event(
            action="plan_wizard_used",
            module="trip_planner",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "tarih": payload.tarih.isoformat(),
                "mesafe_km": payload.mesafe_km,
                "guzergah_id": payload.guzergah_id,
                "top_n": payload.top_n,
                "vehicle_count": len(result.vehicles),
                "driver_count": len(result.drivers),
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("plan_wizard audit log failed: %s", exc)

    return PlanWizardResponse(
        weather_impact=result.weather_impact,
        risk_label=cast("Any", result.risk_label),
        route_type=cast("Any", result.route_type),
        vehicles=[VehicleSuggestion.model_validate(v) for v in result.vehicles],
        drivers=[DriverSuggestion.model_validate(d) for d in result.drivers],
        generated_at=result.generated_at,
        cache_hit=result.cache_hit,
    )
