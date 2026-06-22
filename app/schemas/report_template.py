"""Reports v2 RV2.5 — Reports Studio şablon meta schema'ları.

Plan §5: 6 statik şablon (statik metadata; mevcut PDF/Excel endpoint'leri reuse).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TemplateId = Literal[
    "ceo_1pager",
    "fleet_weekly",
    "fuel_cost_analysis",
    "vehicle_comparison",
    "carbon_report",
    "what_if",
]

TemplateCategory = Literal["executive", "fleet", "fuel", "compliance"]

TemplateFormat = Literal["pdf", "excel"]


class TemplateMeta(BaseModel):
    """Tek bir rapor şablonu meta verisi."""

    model_config = ConfigDict(from_attributes=True)

    id: TemplateId
    title: str
    description: str
    category: TemplateCategory
    formats: list[TemplateFormat] = Field(
        ..., description="Şablonun desteklediği indirme formatları"
    )
    endpoint_hint: str = Field(
        ...,
        description=(
            "Bilgi amaçlı — UI tarafında hangi service çağrılacağını belirler"
        ),
    )
    supports_period: bool = Field(
        False, description="True ise UI period seçim widget'ı gösterir"
    )
    supports_vehicle: bool = Field(
        False, description="True ise UI araç seçim widget'ı gösterir"
    )


class TemplateListResponse(BaseModel):
    """GET /studio/templates response zarfı."""

    model_config = ConfigDict(from_attributes=True)

    templates: list[TemplateMeta]
    count: int
