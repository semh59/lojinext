"""Reports v2 RV2.2 — Fleet İçgörü schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

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
