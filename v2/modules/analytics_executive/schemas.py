"""Feature E — Strategic Cockpit schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScenarioType = Literal["fleet_renewal", "training", "route_portfolio"]


class FleetEfficiencyResponse(BaseModel):
    """E.1 — Filo Verimliliği Endeksi response."""

    model_config = ConfigDict(from_attributes=True)

    fvi: float = Field(..., ge=0, le=100, description="0-100 composite endeks")
    fuel_score: float = Field(..., ge=0, le=100)
    maintenance_score: float = Field(..., ge=0, le=100)
    driver_score: float = Field(..., ge=0, le=100)
    anomaly_quality_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(
        ..., ge=0, le=1, description="0-1; kaç alt-skor cold-start değil"
    )
    trend_30d: Optional[float] = Field(
        None, description="Geçen ayla karşılaştırma (delta puan)"
    )
    reasons: List[str] = Field(default_factory=list, max_length=10)
    computed_at: datetime


# ── E.2 What-if schemas ─────────────────────────────────────────────────


class FleetRenewalInputs(BaseModel):
    max_age_years: int = Field(..., ge=1, le=50)
    replacement_cost_per_vehicle_tl: float = Field(..., gt=0, le=10_000_000)
    expected_l_100km_improvement_pct: float = Field(15.0, gt=0, le=50)
    diesel_price_tl: float = Field(50.0, gt=0, le=500)


class TrainingInputs(BaseModel):
    improvement_pct: float = Field(..., gt=0, le=30)
    training_cost_per_driver_tl: float = Field(..., gt=0, le=500_000)
    diesel_price_tl: float = Field(50.0, gt=0, le=500)


class RoutePortfolioInputs(BaseModel):
    drop_bottom_n: int = Field(..., ge=1, le=20)
    iterations: int = Field(100, ge=10, le=1000)
    diesel_price_tl: float = Field(50.0, gt=0, le=500)


class WhatIfRequest(BaseModel):
    """Tek endpoint; scenario_type'a göre 3 input variant'tan biri gerekir."""

    scenario_type: ScenarioType
    fleet_renewal: Optional[FleetRenewalInputs] = None
    training: Optional[TrainingInputs] = None
    route_portfolio: Optional[RoutePortfolioInputs] = None

    @model_validator(mode="after")
    def check_inputs_present(self) -> "WhatIfRequest":
        required = {
            "fleet_renewal": self.fleet_renewal,
            "training": self.training,
            "route_portfolio": self.route_portfolio,
        }
        if required[self.scenario_type] is None:
            raise ValueError(f"'{self.scenario_type}' senaryosu için inputs gerekli")
        return self


class MonteCarloBand(BaseModel):
    p10: float
    p50: float
    p90: float
    iterations: int


class WhatIfResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_type: ScenarioType
    inputs: Dict[str, Any]
    yearly_savings_tl: float
    upfront_cost_tl: float
    payback_years: Optional[float]
    five_year_roi_pct: float
    co2_reduction_kg: float = 0.0
    confidence: float = Field(..., ge=0, le=1)
    monte_carlo: Optional[MonteCarloBand] = None
    reasons: List[str] = Field(default_factory=list, max_length=10)


# ── E.3 Carbon schemas ─────────────────────────────────────────────────


class TopEmitterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    plaka: str
    co2_kg: float
    euro_class: str
    yearly_l: float


class FleetCarbonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    period_end: date
    total_co2_kg: float
    total_km: float
    co2_per_km: float = Field(..., description="Filo CO2 yoğunluğu (kg/km)")
    benchmark_co2_per_km: float = Field(
        ..., description="AB ortalama heavy-truck (kg/km)"
    )
    delta_pct: float = Field(
        ..., description="Benchmark üstü pozitif, altı negatif (%)"
    )
    by_euro_class: Dict[str, float] = Field(
        default_factory=dict,
        description="Euro sınıfı bazında toplam CO2 (kg)",
    )
    top_emitters: List[TopEmitterResponse] = Field(default_factory=list, max_length=10)
    vehicle_count: int


# ── E.4 Compliance schemas ──────────────────────────────────────────────


EntityType = Literal["arac", "dorse"]
RiskLevelCompliance = Literal["overdue", "soon", "normal", "low"]


class ComplianceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_type: EntityType
    entity_id: int
    plaka: str
    field: str = Field(..., description="v1: 'muayene'")
    expiry_date: date
    days_until: int = Field(..., description="Negatif = geçmiş, pozitif = gelecek")
    risk_level: RiskLevelCompliance


class ComplianceHeatmapResponse(BaseModel):
    """E.4 — Compliance scanner çıktısı (sıralı, en kritik en başta)."""

    days_horizon: int
    total_items: int
    overdue_count: int
    soon_count: int
    items: List[ComplianceItemResponse] = Field(default_factory=list)


# ── E.5 Cashflow schemas ──────────────────────────────────────────────


class CashflowWeekResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    week_start: date
    fuel_tl: float
    maintenance_tl: float
    # penalty_tl: None ise ceza tablosu kurulu değil; UI bu hücreyi "—" ile
    # göstermeli. 0.0 vs None ayrımı önemli: 0 "ceza yok" demek, None "veri yok".
    penalty_tl: Optional[float] = None
    total_tl: float


class CashflowProjectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon_days: int
    weeks: List[CashflowWeekResponse] = Field(default_factory=list)
    total_fuel_tl: float
    total_maintenance_tl: float
    total_penalty_tl: Optional[float] = None
    # True ise ceza tablosu (cezalar) DB'de yok; sıfır değil, "veri yok".
    penalty_data_available: bool = False
    grand_total_tl: float
    confidence: float = Field(..., ge=0, le=1)
    assumptions: Dict[str, float] = Field(default_factory=dict)


# ── E.6 Cross-feature schemas ─────────────────────────────────────────


class CrossFeatureImpactResponse(BaseModel):
    """E.6 — D.4 + A.5 + B motorlarının cross-feature etkisi."""

    model_config = ConfigDict(from_attributes=True)

    period_days: int
    maintenance_delay_loss_tl: float = Field(
        ..., description="D.4: factor > 1 araçların ekstra yakıt × fiyat"
    )
    coaching_savings_tl: float = Field(
        ..., description="A.5: ölçülen koçluk score delta'sından tasarruf"
    )
    theft_loss_tl: float = Field(
        ..., description="B: resolved real_theft × ortalama kayıp × fiyat"
    )
    confidence: float = Field(..., ge=0, le=1, description="v1 heuristic → 0.55")


# ── E.7 Bus factor schemas ────────────────────────────────────────────


RiskLevelBus = Literal["high", "medium", "low"]


class TopDriverAnonymized(BaseModel):
    """PII koruma: ad/id yok, sadece skor + km."""

    model_config = ConfigDict(from_attributes=True)
    score: float = Field(..., ge=0, le=2.0)
    yearly_km: int = Field(..., ge=0)


class BusFactorResponse(BaseModel):
    """E.7 — Top-N şoför ayrılırsa filo verim kaybı."""

    model_config = ConfigDict(from_attributes=True)

    n: int = Field(..., ge=1, le=10, description="Top-N şoför")
    top_n_drivers_loss_tl: float
    top_n_drivers: List[TopDriverAnonymized] = Field(default_factory=list)
    bottlenecked_routes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="v1'de boş; v2'de güzergah bottleneck'i eklenecek",
    )
    risk_level: RiskLevelBus


# ─── Yakıt performans analitiği response şemaları (dalga 16 — eski app/schemas/api_responses.py'den taşındı) ───────


class FuelPerformanceKpis(BaseModel):
    mae: float
    rmse: float
    total_compared: int
    high_deviation_ratio: float


class FuelPerformanceTrendPoint(BaseModel):
    week: str
    avg_consumption: float
    count: int


class FuelPerformanceDistributionBucket(BaseModel):
    range: str
    count: int


class FuelPerformanceOutlier(BaseModel):
    sefer_id: int
    tarih: Optional[str] = None
    actual: float
    predicted: float
    deviation_pct: float


class FuelPerformanceAnalyticsResponse(BaseModel):
    kpis: FuelPerformanceKpis
    trend: List[FuelPerformanceTrendPoint]
    distribution: List[FuelPerformanceDistributionBucket]
    outliers: List[FuelPerformanceOutlier]
    low_data: bool
