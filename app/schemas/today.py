"""Reports v2 RV2.1 — Today/Triage schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

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
