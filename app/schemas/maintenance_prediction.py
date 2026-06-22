"""Feature D — Tahmine Dayalı Bakım schema'ları."""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["overdue", "soon", "normal", "low"]


class MaintenancePrediction(BaseModel):
    """D.1 — tek araç + bakım tipi için tahmin çıktısı."""

    model_config = ConfigDict(from_attributes=True)

    arac_id: int
    plaka: str
    bakim_tipi: str
    predictable: bool = Field(
        ..., description="False ise diğer tüm alanlar None/0/low olabilir"
    )
    predicted_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    confidence: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel = "low"
    savings_pct: float = Field(0.0, ge=0, le=100)
    reasons: List[str] = Field(default_factory=list, max_length=10)
