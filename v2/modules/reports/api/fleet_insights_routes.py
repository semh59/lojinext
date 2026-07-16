"""Reports v2 RV2.2 — Fleet İçgörü endpoint'leri."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.database.models import Kullanici
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.auth_rbac.domain.permission_checker import require_yetki
from v2.modules.reports.application.compute_fleet_comparison import (
    PeriodType,
    compute_fleet_comparison,
)
from v2.modules.reports.schemas import (
    FleetComparisonResponse,
    PeriodMetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/comparison", response_model=FleetComparisonResponse)
async def get_fleet_comparison(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
    period: PeriodType = "month",
) -> FleetComparisonResponse:
    """Bu periyot vs geçen periyot karşılaştırma.

    Args:
        period: 'week' (7g) veya 'month' (30g)

    Plan §4 — period-over-period delta hesabı.
    """
    if not settings.REPORTS_V2_ENABLED:
        raise HTTPException(status_code=503, detail="Reports v2 devre dışı")

    async with UnitOfWork() as uow:
        result = await compute_fleet_comparison(
            uow,
            period=period,
            diesel_price_tl=settings.LITRE_DIESEL_TL,
        )

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="fleet_insights_viewed",
            module="reports_v2",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "period": period,
                "fuel_l_delta_pct": result.fuel_l_delta_pct,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Fleet insights audit failed: %s", exc)

    return FleetComparisonResponse(
        period=result.period,
        current=PeriodMetricsResponse.model_validate(result.current),
        previous=PeriodMetricsResponse.model_validate(result.previous),
        fuel_l_delta_pct=result.fuel_l_delta_pct,
        fuel_cost_delta_pct=result.fuel_cost_delta_pct,
        anomaly_delta_pct=result.anomaly_delta_pct,
        trip_delta_pct=result.trip_delta_pct,
        current_start=result.current_start,
        current_end=result.current_end,
        previous_start=result.previous_start,
        previous_end=result.previous_end,
    )
