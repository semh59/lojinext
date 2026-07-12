"""Pure geo-math helpers (no I/O) used by route-detail analysis.

NOT: haversine/segment_distance/analyze_elevation_profile'ı hiçbir prod
kod çağırmıyor (yalnız birbirlerini ve kendi testlerini) — RouteAnalyzer'ın
kendi haversine'i (route_analyzer.py) canlı yolda kullanılan asıl
hesaplama. Bu dosya, önceki RouteService sınıfının artık ölü ama test
edilmiş yardımcı metodlarının davranış-birebir taşınmış hâli.
"""

from __future__ import annotations

import math
from typing import Dict, List


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great-circle distance in meters."""
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlamb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlamb / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def segment_distance(coordinates: List, start_idx: int, end_idx: int) -> float:
    """Calculate total distance for a coordinate slice."""
    total = 0.0
    for index in range(start_idx, end_idx):
        if index + 1 >= len(coordinates):
            break
        p1 = coordinates[index]
        p2 = coordinates[index + 1]
        total += haversine(p1[0], p1[1], p2[0], p2[1])
    return total


def analyze_elevation_profile(geometry: Dict) -> Dict:
    """Analyze flat vs ramp percentage from GeoJSON coordinates."""
    coords = geometry.get("coordinates", [])
    if len(coords) < 2:
        return {"flat_pct": 100, "ramp_pct": 0}

    flat_dist = 0.0
    ramp_dist = 0.0

    for index in range(1, len(coords)):
        p1 = coords[index - 1]
        p2 = coords[index]
        d_horiz = haversine(p1[0], p1[1], p2[0], p2[1])

        if d_horiz < 5:
            continue

        if len(p1) < 3 or len(p2) < 3:
            flat_dist += d_horiz
            continue

        d_vert = p2[2] - p1[2]
        gradient = (d_vert / d_horiz) * 100

        if abs(gradient) < 1.5:
            flat_dist += d_horiz
        else:
            ramp_dist += d_horiz

    total = flat_dist + ramp_dist
    if total == 0:
        return {"flat_pct": 100, "ramp_pct": 0}

    return {
        "flat_pct": round((flat_dist / total) * 100, 1),
        "ramp_pct": round((ramp_dist / total) * 100, 1),
        "flat_dist_m": round(flat_dist, 0),
        "total_dist_m": round(total, 0),
    }


__all__ = ["haversine", "segment_distance", "analyze_elevation_profile"]
