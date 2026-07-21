"""Reports v2 RV2.1 — Today/Triage endpoint."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_active_user
from app.config import settings
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.reports.application.aggregate_today_triage import aggregate_today_triage
from v2.modules.reports.schemas import (
    TodayTriageResponse,
)
from v2.modules.reports.schemas import (
    TriageAction as TriageActionSchema,
)
from v2.modules.reports.schemas import (
    TriageItem as TriageItemSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/triage", response_model=TodayTriageResponse)
async def get_today_triage(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> TodayTriageResponse:
    """Today/Triage — bugünün acil + bekleyen aksiyon listesi.

    Anomali + bakım + soruşturma kaynaklarını topla; priority sıralı döner.
    Critical önce. Plan §3.
    """
    if not settings.REPORTS_V2_ENABLED:
        raise HTTPException(status_code=503, detail="Reports v2 devre dışı")

    async with UnitOfWork() as uow:
        result = await aggregate_today_triage(
            uow,
            limit=settings.REPORTS_V2_TRIAGE_LIMIT,
            lookback_days=7,
        )

    # Audit (PII'siz; sadece count + kullanıcı)
    try:
        creator_id = (
            current_user.id if current_user.id and current_user.id > 0 else None
        )
        await log_audit_event(
            action="today_triage_viewed",
            module="reports_v2",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "total_items": len(result.items),
                "critical_count": result.critical_count,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Triage audit failed: %s", exc)

    return TodayTriageResponse(
        critical_count=result.critical_count,
        pending_count=result.pending_count,
        items=[
            TriageItemSchema(
                id=i.id,
                category=i.category,
                severity=i.severity,
                title=i.title,
                subtitle=i.subtitle,
                timestamp=i.timestamp,
                plaka=i.plaka,
                actions=[
                    TriageActionSchema(
                        label=a.label, url=a.url, action_type=a.action_type
                    )
                    for a in i.actions
                ],
            )
            for i in result.items
        ],
        active_trips_count=result.active_trips_count,
        completed_today_count=result.completed_today_count,
        computed_at=result.computed_at,
    )
