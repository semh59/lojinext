"""Weather/route-analysis response schemas (dalga 16 — eski app/schemas/api_responses.py'den taşındı)."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WeatherTripDetail(BaseModel):
    trip_id: int
    plaka: str
    risk: str = Field(..., description="High | Unavailable")
    impact: Optional[float] = None
    error_code: Optional[str] = None


class WeatherDashboardResponse(BaseModel):
    total_active: int
    high_risk: int
    medium_risk: int
    normal: int
    unavailable: int
    details: List[WeatherTripDetail]


class RouteAnalysisResponse(BaseModel):
    """Result of a route analysis with computed difficulty. Provider returns extra
    fields (geometry, segments, elevation profile) — kept under `extra=allow` so
    callers can read them, but the documented core is mandatory.

    Self-contained (not inherited from location's RouteInfoResponse): route_simulation
    and location are separate modules with no cross-module schema-inheritance
    precedent elsewhere in the codebase, so the shared field set is duplicated here
    rather than importing across module boundaries.
    """

    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    otoban_mesafe_km: Optional[float] = None
    sehir_ici_mesafe_km: Optional[float] = None
    source: Optional[str] = None
    difficulty: Optional[str] = Field(
        None, description="Düz | Hafif Eğimli | Dik/Dağlık (computed by service)"
    )

    @field_validator(
        "distance_km",
        "duration_min",
        "ascent_m",
        "descent_m",
        "otoban_mesafe_km",
        "sehir_ici_mesafe_km",
        mode="before",
    )
    @classmethod
    def heal_floats(cls, v: Any) -> Optional[float]:
        """Bozuk float değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = float(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("source", mode="before")
    @classmethod
    def heal_source(cls, v: Any) -> Optional[str]:
        """Boş source alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("difficulty", mode="before")
    @classmethod
    def heal_difficulty(cls, v: Any) -> Optional[str]:
        """Boş difficulty alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    model_config = ConfigDict(extra="allow")


class WeatherSummary(BaseModel):
    avg_temperature: float
    avg_precipitation: float
    avg_wind_speed: float


class TripWeatherImpactResponse(BaseModel):
    success: bool
    weather_summary: WeatherSummary
    fuel_impact_factor: float
    fuel_impact_percent: float
    conditions: List[str]
    recommendation: str
