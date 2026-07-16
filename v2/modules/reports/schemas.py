"""Reports v2 — Pydantic request/response şemaları.

Üç eski dosyanın (schemas/report_template.py, schemas/today.py,
schemas/fleet_insights.py) birleşimi — hepsi Reports-v2 özelliğinin
parçası, ayrı dosyalarda tutmanın gerekçesi yoktu.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ── Reports Studio (RV2.5) ──────────────────────────────────────────────

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


# ── Today/Triage (RV2.1) ────────────────────────────────────────────────

TriageCategory = Literal[
    "anomaly",
    "maintenance",
    "investigation",
    "telegram_approval",
    "active_trip",
]
TriageSeverity = Literal["critical", "high", "medium", "low"]


class TriageAction(BaseModel):
    """Tek item için yapılabilecek aksiyon (CTA)."""

    label: str = Field(..., max_length=40)
    url: str  # frontend route
    action_type: Literal["navigate", "modal", "external"] = "navigate"


class TriageItem(BaseModel):
    """Today sayfasında gösterilen tek aksiyon item'ı."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="örn. 'anomaly:42', 'maintenance:7'")
    category: TriageCategory
    severity: TriageSeverity
    title: str = Field(..., max_length=140)
    subtitle: str = Field("", max_length=200)
    timestamp: datetime
    plaka: Optional[str] = Field(None, max_length=20)
    actions: List[TriageAction] = Field(default_factory=list, max_length=4)


class TodayTriageResponse(BaseModel):
    """Today/Triage çıktısı — priority sıralı."""

    model_config = ConfigDict(from_attributes=True)

    critical_count: int = Field(..., ge=0)
    pending_count: int = Field(..., ge=0)
    items: List[TriageItem] = Field(default_factory=list)
    active_trips_count: int = Field(..., ge=0)
    completed_today_count: int = Field(..., ge=0)
    computed_at: datetime


# ── Fleet İçgörü (RV2.2) ─────────────────────────────────────────────────

PeriodType = Literal["week", "month"]


class PeriodMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    fuel_l: float = Field(..., ge=0)
    fuel_cost_tl: float = Field(..., ge=0)
    anomaly_count: int = Field(..., ge=0)
    trip_count: int = Field(..., ge=0)


class FleetComparisonResponse(BaseModel):
    """Period-over-period karşılaştırma çıktısı."""

    model_config = ConfigDict(from_attributes=True)

    period: PeriodType
    current: PeriodMetricsResponse
    previous: PeriodMetricsResponse
    fuel_l_delta_pct: Optional[float] = Field(
        None, description="None ise önceki periyot 0 idi"
    )
    fuel_cost_delta_pct: Optional[float] = None
    anomaly_delta_pct: Optional[float] = None
    trip_delta_pct: Optional[float] = None
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
