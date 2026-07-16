"""Reports v2 RV2.5 — Reports Studio endpoint'leri.

Plan §5: 6 statik şablon listesi. Mevcut PDF/Excel endpoint'leri reuse —
yeni rapor üretim endpoint'i yok.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_active_user
from app.config import settings
from app.database.models import Kullanici
from v2.modules.reports.schemas import TemplateListResponse, TemplateMeta

logger = logging.getLogger(__name__)

router = APIRouter()


# Plan §5.1 — 6 statik şablon. UI bu meta'ya göre kart galerisi oluşturur.
_TEMPLATES: list[TemplateMeta] = [
    TemplateMeta(
        id="ceo_1pager",
        title="CEO Aylık 1-Pager",
        description=(
            "Tek sayfalık üst yönetim özeti — FVI, maliyet, anomali ve uyum metrikleri."
        ),
        category="executive",
        formats=["pdf"],
        endpoint_hint="/reports/executive/pdf",
        supports_period=False,
        supports_vehicle=False,
    ),
    TemplateMeta(
        id="fleet_weekly",
        title="Filo Müdürü Haftalık",
        description=(
            "Haftalık operasyon özeti — FVI, period karşılaştırma, "
            "cross-feature kazanım."
        ),
        category="fleet",
        formats=["pdf", "excel"],
        endpoint_hint="/advanced-reports/pdf/fleet-summary",
        supports_period=True,
        supports_vehicle=False,
    ),
    TemplateMeta(
        id="fuel_cost_analysis",
        title="Yakıt Maliyet Analizi",
        description="Aylık yakıt maliyet trendi ve dönem karşılaştırması.",
        category="fuel",
        formats=["pdf", "excel"],
        endpoint_hint="/advanced-reports/cost/period",
        supports_period=True,
        supports_vehicle=True,
    ),
    TemplateMeta(
        id="vehicle_comparison",
        title="Araç Karşılaştırma",
        description=("Filodaki araçların ortalama tüketim ve maliyet karşılaştırması."),
        category="fleet",
        formats=["pdf", "excel"],
        endpoint_hint="/reports/vehicle-comparison",
        supports_period=True,
        supports_vehicle=False,
    ),
    TemplateMeta(
        id="carbon_report",
        title="Karbon Raporu",
        description="12 ay CO₂ emisyon özeti ve hedef sapması.",
        category="compliance",
        formats=["pdf", "excel"],
        endpoint_hint="/reports/executive/carbon",
        supports_period=True,
        supports_vehicle=False,
    ),
    TemplateMeta(
        id="what_if",
        title="What-If Sonucu",
        description=(
            "Strategic Cockpit'te çalıştırılan senaryonun PDF olarak indirilmesi."
        ),
        category="executive",
        formats=["pdf"],
        endpoint_hint="/reports/executive/what-if/export",
        supports_period=False,
        supports_vehicle=False,
    ),
]


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> TemplateListResponse:
    """6 statik rapor şablonunun meta listesi.

    Plan §5.1 — UI kart galerisi bu meta'yı kullanır. Şablonlar koddan
    geliyor (DB yok); şu an yetki ayrımı yok (auth zorunlu).
    """
    if not settings.REPORTS_V2_ENABLED:
        raise HTTPException(status_code=503, detail="Reports v2 devre dışı")

    logger.debug(
        "Reports studio templates listed",
        extra={"user_id": current_user.id, "count": len(_TEMPLATES)},
    )

    return TemplateListResponse(
        templates=_TEMPLATES,
        count=len(_TEMPLATES),
    )
