"""Use-case: fetch a location's hydrated 500m bucket segments (Phase 3.4)."""

from typing import Any, Dict, Optional

from v2.modules.location.infrastructure.repository import LokasyonRepository


async def get_location_segments(
    repo: LokasyonRepository, lokasyon_id: int
) -> Optional[Dict[str, Any]]:
    lok = await repo.get_with_segments(lokasyon_id)
    if lok is None:
        return None

    return {
        "lokasyon_id": lok.id,
        "ad": lok.ad,
        "hydrated_at": lok.hydrated_at,
        "raw_segment_count": lok.raw_segment_count,
        "resampled_segment_count": lok.resampled_segment_count,
        "elevation_coverage_pct": lok.elevation_coverage_pct,
        "segments": [
            {
                "seq": s.seq,
                "length_km": round(s.length_km, 3),
                "grade_pct": round(s.grade_pct, 2),
                "road_class": s.road_class,
                "maxspeed_kmh": s.maxspeed_kmh,
                "mid_lon": s.mid_lon,
                "mid_lat": s.mid_lat,
            }
            for s in lok.segments
        ],
    }
