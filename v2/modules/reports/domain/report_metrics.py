"""Saf yardımcılar — fleet/vehicle rapor hesaplamaları (I/O yok)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional


@dataclass
class TrendReport:
    """Trend report model."""

    period: str
    start_date: date
    end_date: date
    toplam_sefer: int
    toplam_km: int
    toplam_yakit: float
    ortalama_tuketim: float
    onceki_tuketim: Optional[float] = None
    tuketim_degisim: Optional[float] = None


def calculate_performance_score(
    actual_consumption: Optional[float], target_consumption: Optional[float]
) -> float:
    """Target-vs-actual consumption score (0-100) for report generation.

    Scale: 0-100. 100 = actual matches target exactly, decreases as actual
    exceeds target. Clamps at 0 (never negative). Distinct from the fleet-
    average score in `sofor_analiz_service.calculate_performance_score` and
    from the ML-deviation elite score — all three 0-100 scales are report-
    or dashboard-specific and are not interchangeable.
    """
    actual = float(actual_consumption or 0)
    target = float(target_consumption or 0)
    if actual <= 0 or target <= 0:
        return 0.0
    deviation_pct = ((actual - target) / target) * 100
    return round(max(0.0, min(100.0, 100.0 - max(0.0, deviation_pct))), 1)


def get_first_available(data: Dict, *keys, default=0):
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def prefer_positive(primary, fallback):
    try:
        if float(primary) > 0:
            return primary
    except (TypeError, ValueError):
        if primary:
            return primary
    return fallback
