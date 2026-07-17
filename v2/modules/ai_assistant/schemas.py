"""Feature C — Akıllı sefer planlama sihirbazı schema'ları."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

RiskLabel = Literal["low", "medium", "high", "unknown"]
RouteType = Literal["highway_dominant", "mountain", "urban", "mixed"]


class PlanWizardRequest(BaseModel):
    """C.3 endpoint input."""

    tarih: date
    guzergah_id: Optional[int] = Field(None, gt=0)
    cikis_yeri: str = Field(..., min_length=1, max_length=120)
    varis_yeri: str = Field(..., min_length=1, max_length=120)
    mesafe_km: float = Field(..., gt=0, le=5000)
    ascent_m: float = Field(0.0, ge=0, le=20000)
    descent_m: float = Field(0.0, ge=0, le=20000)
    flat_distance_km: float = Field(0.0, ge=0, le=5000)
    weight_kg: float = Field(0.0, ge=0, le=80000)
    top_n: int = Field(3, ge=1, le=5)


class VehicleSuggestion(BaseModel):
    """Tek araç önerisi — VehicleCandidate dataclass'ından üretilir."""

    model_config = ConfigDict(from_attributes=True)

    arac_id: int
    plaka: str
    yas: int
    score: float = Field(..., ge=0, le=1)
    predicted_liters: float
    fuel_score: float = Field(..., ge=0, le=1)
    route_history_score: float = Field(..., ge=0, le=1)
    vehicle_health_score: float = Field(..., ge=0, le=1)
    availability_score: float = Field(..., ge=0, le=1)
    similar_trip_count: int
    cold_start: bool
    reasons: List[str] = Field(default_factory=list, max_length=10)


class DriverSuggestion(BaseModel):
    """Tek şoför önerisi — DriverCandidate dataclass'ından üretilir."""

    model_config = ConfigDict(from_attributes=True)

    sofor_id: int
    ad_soyad: str
    score: float = Field(..., ge=0, le=1)
    route_type_perf: float = Field(..., ge=0, le=1)
    overall_hybrid: float = Field(..., ge=0, le=1)
    availability_score: float = Field(..., ge=0, le=1)
    route_type: RouteType
    deviation_pct: float
    cold_start: bool
    reasons: List[str] = Field(default_factory=list, max_length=10)


class PlanWizardResponse(BaseModel):
    """C.3 endpoint output."""

    weather_impact: float = Field(..., description="1.0 = nötr")
    risk_label: RiskLabel
    route_type: RouteType
    vehicles: List[VehicleSuggestion]
    drivers: List[DriverSuggestion]
    generated_at: datetime
    cache_hit: bool = False
