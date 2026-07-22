"""LokasyonHydrator — güzergahın ham haritasını oluşturur (Phase 3.2).

Pipeline (RouteSimulator'dan simulate_route adımı çıkarılmış sürümü):

    cikis/varis koordinatları
        ↓ MapboxClient.get_segments  (Phase 2.3 cache + retry)
    raw segments + geometry coords (N+1)
        ↓ resample_segments(target=500m)
    coarse buckets + boundary coords (M+1)
        ↓ OpenMeteoElevationClient.get_elevations
    boundary elevations
        ↓ grade_pct = delta_h / length × 100
    enriched static segments (length, grade, road_class, maxspeed,
                              mid_lon/lat)
        ↓ DB persist
    Lokasyon.segments + Lokasyon.hydrated_at güncellenir

Idempotent: yeniden çağrılırsa Lokasyon.segments silinir + yeniden insert.
NOT: traffic/congestion snapshot BURADA yazılmıyor — bunlar sefer
simülasyonu anında Mapbox cache'inden o anki trafik çekilerek
route_segments tablosuna yazılır (bkz. inline yorum, satır ~152).
Sefer simülasyonu bu hidrasyondan beslenir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from v2.modules.location.infrastructure.models import Lokasyon, LokasyonSegment
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.route_simulation.public import (
    MapboxClient,
    OpenMeteoElevationClient,
    get_elevation_client,
    resample_segments,
)

logger = get_logger(__name__)


@dataclass
class HydrationResult:
    """Hidrate sonucu istatistik özet (DB tarafı çağıran tarafından commit)."""

    lokasyon_id: int
    raw_segment_count: int
    resampled_segment_count: int
    elevation_coverage_pct: float
    total_km: float
    total_ascent_m: float
    total_descent_m: float


class LokasyonHydrator:
    """Lokasyon kaydını güzergah segmentleriyle doldurur."""

    def __init__(
        self,
        mapbox_client: Optional[MapboxClient] = None,
        elevation_client: Optional[OpenMeteoElevationClient] = None,
    ) -> None:
        self._mapbox = mapbox_client or MapboxClient()
        self._elev = elevation_client or get_elevation_client()

    async def hydrate(
        self, lokasyon: Lokasyon, *, target_length_km: float = 0.5
    ) -> Optional[HydrationResult]:
        """Lokasyona ait Mapbox+elevation pipeline'ını çalıştır.

        lokasyon.cikis_lat/lon ve varis_lat/lon zorunlu. Mapbox veya
        Open-Meteo başarısız olursa None.

        ÖNEMLİ: lokasyon.segments listesi YENİDEN doldurulur (eski segments
        cascade ile drop, yeni segments append). Caller commit eder.
        """
        if (
            lokasyon.cikis_lat is None
            or lokasyon.cikis_lon is None
            or lokasyon.varis_lat is None
            or lokasyon.varis_lon is None
        ):
            logger.warning(
                "LokasyonHydrator: lokasyon %s missing cikis/varis coords",
                lokasyon.id,
            )
            return None

        # 1. Mapbox raw segments
        mb_result = await self._mapbox.get_segments(
            (lokasyon.cikis_lon, lokasyon.cikis_lat),
            (lokasyon.varis_lon, lokasyon.varis_lat),
        )
        if mb_result is None:
            logger.warning(
                "LokasyonHydrator: Mapbox segments unavailable (lokasyon %s)",
                lokasyon.id,
            )
            return None
        raw_segs, raw_coords = mb_result
        if not raw_segs:
            logger.warning(
                "LokasyonHydrator: empty Mapbox segment list (lokasyon %s)",
                lokasyon.id,
            )
            return None

        # 2. Resample 500m
        resamp_segs, boundary_coords = resample_segments(
            raw_segs, raw_coords, target_length_km=target_length_km
        )
        if not resamp_segs:
            return None

        # 3. Elevation
        elevations = await self._elev.get_elevations(boundary_coords)
        elev_filled = sum(1 for e in elevations if e is not None)
        elev_coverage = (elev_filled / len(elevations) * 100.0) if elevations else 0.0

        # 4. Grade hesapla + DB rows oluştur
        # Eski segments cascade ile silinir (lokasyon.segments = [])
        lokasyon.segments.clear()

        total_km = 0.0
        total_ascent = 0.0
        total_descent = 0.0

        for i, seg in enumerate(resamp_segs):
            mid_lon: Optional[float] = None
            mid_lat: Optional[float] = None
            if i + 1 < len(boundary_coords):
                mid_lon = (boundary_coords[i][0] + boundary_coords[i + 1][0]) / 2.0
                mid_lat = (boundary_coords[i][1] + boundary_coords[i + 1][1]) / 2.0

            grade = seg.grade_pct
            if i + 1 < len(elevations):
                e_start = elevations[i]
                e_end = elevations[i + 1]
                if e_start is not None and e_end is not None and seg.length_km > 0:
                    grade = (e_end - e_start) / (seg.length_km * 1000.0) * 100.0

            total_km += seg.length_km
            delta_h = seg.length_km * 1000.0 * (grade / 100.0)
            if delta_h > 0:
                total_ascent += delta_h
            else:
                total_descent += -delta_h

            lokasyon.segments.append(
                LokasyonSegment(
                    seq=i,
                    length_km=seg.length_km,
                    grade_pct=grade,
                    road_class=seg.road_class or None,
                    maxspeed_kmh=seg.maxspeed_kmh,
                    # Phase 3.5: traffic / congestion BURADA YOK — sefer
                    # simülasyonu Mapbox cache'ten o anki trafiği çekip
                    # route_segments'a yazar.
                    mid_lon=mid_lon,
                    mid_lat=mid_lat,
                )
            )

        # 5. Lokasyon header'ını güncelle
        lokasyon.hydrated_at = datetime.now(timezone.utc)
        lokasyon.raw_segment_count = len(raw_segs)
        lokasyon.resampled_segment_count = len(resamp_segs)
        lokasyon.elevation_coverage_pct = round(elev_coverage, 1)

        return HydrationResult(
            lokasyon_id=lokasyon.id,
            raw_segment_count=len(raw_segs),
            resampled_segment_count=len(resamp_segs),
            elevation_coverage_pct=round(elev_coverage, 1),
            total_km=round(total_km, 3),
            total_ascent_m=round(total_ascent, 1),
            total_descent_m=round(total_descent, 1),
        )


_default_hydrator: Optional[LokasyonHydrator] = None


def get_lokasyon_hydrator() -> LokasyonHydrator:
    """Lazy singleton."""
    global _default_hydrator
    if _default_hydrator is None:
        _default_hydrator = LokasyonHydrator()
    return _default_hydrator


__all__ = ["LokasyonHydrator", "HydrationResult", "get_lokasyon_hydrator"]
