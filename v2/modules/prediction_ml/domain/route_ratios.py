"""Rota-oranı saf yardımcıları (predict_consumption'dan ayrıldı, dalga 13).

I/O yok — sadece ``route_analysis`` dict'ini normalize eder ve otoyol/devlet
yolu/şehir içi km oranlarını hesaplar. `PredictionService.predict_consumption`
ve ensemble path'i bu fonksiyonları çağırır.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from v2.modules.shared_kernel.utils.type_helpers import safe_float


def sum_segment_km(segment: Any) -> float:
    if not isinstance(segment, dict):
        return 0.0
    total = 0.0
    for key in ("flat", "up", "down"):
        total += safe_float(segment.get(key)) or 0.0
    return total


def derive_route_ratios(
    route_analysis: Optional[Dict[str, Any]],
) -> Optional[Dict[str, float]]:
    if not isinstance(route_analysis, dict):
        return None

    existing = route_analysis.get("ratios")
    if isinstance(existing, dict):
        return {
            "otoyol": round(float(existing.get("otoyol", 0.0) or 0.0), 3),
            "devlet_yolu": round(float(existing.get("devlet_yolu", 0.0) or 0.0), 3),
            "sehir_ici": round(float(existing.get("sehir_ici", 0.0) or 0.0), 3),
        }

    motorway_km = sum_segment_km(route_analysis.get("motorway"))
    trunk_km = sum_segment_km(route_analysis.get("trunk"))
    primary_km = sum_segment_km(route_analysis.get("primary"))
    residential_km = sum_segment_km(route_analysis.get("residential"))
    unclassified_km = sum_segment_km(route_analysis.get("unclassified"))
    other_km = sum_segment_km(route_analysis.get("other"))
    highway_km = sum_segment_km(route_analysis.get("highway"))

    if highway_km > 0 and (trunk_km + primary_km) == 0:
        trunk_km = highway_km

    total_km = (
        motorway_km + trunk_km + primary_km + residential_km + unclassified_km + other_km
    )
    if total_km <= 0:
        return None

    return {
        "otoyol": round(motorway_km / total_km, 3),
        "devlet_yolu": round((trunk_km + primary_km) / total_km, 3),
        "sehir_ici": round((residential_km + unclassified_km + other_km) / total_km, 3),
    }


def normalize_route_analysis(
    route_analysis: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(route_analysis, dict):
        return None

    normalized: Dict[str, Any] = {}
    nested = route_analysis.get("route_analysis")
    if isinstance(nested, dict):
        normalized.update(nested)

    for key in (
        "ratios",
        "weather_factor",
        "historical_stats",
        "granular_nodes",
        "distributions",
        "motorway",
        "trunk",
        "primary",
        "residential",
        "unclassified",
        "highway",
        "other",
    ):
        value = route_analysis.get(key)
        if value is not None and key not in normalized:
            normalized[key] = value

    ratios = derive_route_ratios(normalized)
    if ratios is not None:
        normalized["ratios"] = ratios

    return normalized or None


__all__ = ["sum_segment_km", "derive_route_ratios", "normalize_route_analysis"]
