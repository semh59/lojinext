"""RouteSimulator — end-to-end segment simulation orchestration (Phase 1.4).

Pipeline:

    cikis/varis koordinatları
        ↓ MapboxClient.get_segments
    raw Mapbox segments (avg 30-100m) + geometry coords (N+1)
        ↓ resample_segments(target=500m)
    coarse buckets (~500m) + boundary coords (M+1)
        ↓ OpenMeteoElevationClient.get_elevations
    boundary elevations (M+1, SRTM 30m DEM)
        ↓ delta_h / length × 100
    enriched segments with grade_pct
        ↓ simulate_route (PhysicsBasedFuelPredictor wrapper)
    SegmentSummary (total_km, total_l, avg_l_per_100km, eta, ascent, descent,
                    + per-segment outputs)

DB veya endpoint dependency YOK — coords + simülasyon param'larıyla çalışır.
P1.5 endpoint katmanı arac_id'den arac_yasi/ton/dorse'yi UoW ile yükleyip
bu service'i çağırır.

Sentinel davranışlar:
- Mapbox çağrısı None döndü → None döner (caller 502)
- Bütün elevation çağrısı None → grade_pct=0 default (degrade ama tamamlanır)
- Bazı elevation None → o bucket için grade=0 fallback
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.core.ml.physics_fuel_predictor import VehicleSpecs
from app.core.ml.segment_simulator import (
    SegmentInput,
    SegmentSummary,
    simulate_route,
)
from app.core.services.segment_resampler import resample_segments
from app.infrastructure.elevation.open_meteo_client import (
    OpenMeteoElevationClient,
    get_elevation_client,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.routing.mapbox_client import MapboxClient

logger = get_logger(__name__)


@dataclass
class SimulationResult:
    """RouteSimulator çıktısı."""

    summary: SegmentSummary
    boundary_coords: List[Tuple[float, float]]
    elevations: List[Optional[float]]
    raw_segment_count: int
    resampled_segment_count: int
    elevation_coverage_pct: float
    meta: dict = field(default_factory=dict)


class RouteSimulator:
    """Mapbox → resample → Open-Meteo → SegmentSimulator orkestrasyonu."""

    def __init__(
        self,
        mapbox_client: Optional[MapboxClient] = None,
        elevation_client: Optional[OpenMeteoElevationClient] = None,
    ) -> None:
        self._mapbox = mapbox_client or MapboxClient()
        self._elev = elevation_client or get_elevation_client()

    async def simulate(
        self,
        *,
        cikis_lon: float,
        cikis_lat: float,
        varis_lon: float,
        varis_lat: float,
        ton: float = 15.0,
        arac_yasi: int = 5,
        target_length_km: float = 0.5,
        vehicle: Optional[VehicleSpecs] = None,
    ) -> Optional[SimulationResult]:
        """End-to-end simülasyon. Mapbox veya Open-Meteo hatasında None.

        Args:
            cikis_lon/lat, varis_lon/lat: Başlangıç ve bitiş koordinatları.
            ton: Yük (0 = boş sefer).
            arac_yasi: Gravity recovery hesabı için araç yaşı.
            target_length_km: Bucket boyutu (default 500m).
            vehicle: Araç teknik özellikleri. None → default TIR specs.

        Returns:
            SimulationResult (None → Mapbox routing başarısız).
        """
        # 1. Mapbox segments
        mb_result = await self._mapbox.get_segments(
            (cikis_lon, cikis_lat), (varis_lon, varis_lat)
        )
        if mb_result is None:
            logger.warning(
                "RouteSimulator: Mapbox segments unavailable (%.4f,%.4f → %.4f,%.4f)",
                cikis_lon,
                cikis_lat,
                varis_lon,
                varis_lat,
            )
            return None

        raw_segs, raw_coords = mb_result
        if not raw_segs:
            logger.warning("RouteSimulator: empty segment list")
            return None

        # 2. Resample 500m
        resamp_segs, boundary_coords = resample_segments(
            raw_segs, raw_coords, target_length_km=target_length_km
        )
        if not resamp_segs:
            logger.warning("RouteSimulator: empty resampled segment list")
            return None

        # 3. Elevation enrichment — boundary coords için batch çağrı.
        # M bucket için M+1 boundary coord → bucket grade = delta_h / length × 100.
        elevations = await self._elev.get_elevations(boundary_coords)
        elev_filled = sum(1 for e in elevations if e is not None)
        elev_coverage = (elev_filled / len(elevations) * 100.0) if elevations else 0.0
        if elev_coverage < 100.0:
            logger.info(
                "RouteSimulator: elevation coverage %.1f%% (%d/%d)",
                elev_coverage,
                elev_filled,
                len(elevations),
            )

        # 4. Grade computation per bucket
        enriched: List[SegmentInput] = []
        for i, seg in enumerate(resamp_segs):
            grade = seg.grade_pct  # 0 default
            if i + 1 < len(elevations):
                e_start = elevations[i]
                e_end = elevations[i + 1]
                if e_start is not None and e_end is not None and seg.length_km > 0:
                    grade = (e_end - e_start) / (seg.length_km * 1000.0) * 100.0
            enriched.append(
                SegmentInput(
                    length_km=seg.length_km,
                    grade_pct=grade,
                    road_class=seg.road_class,
                    maxspeed_kmh=seg.maxspeed_kmh,
                    traffic_speed_kmh=seg.traffic_speed_kmh,
                    congestion=seg.congestion,
                )
            )

        # 5. Simulate
        summary = simulate_route(
            enriched, vehicle=vehicle, ton=ton, arac_yasi=arac_yasi
        )

        return SimulationResult(
            summary=summary,
            boundary_coords=boundary_coords,
            elevations=elevations,
            raw_segment_count=len(raw_segs),
            resampled_segment_count=len(resamp_segs),
            elevation_coverage_pct=round(elev_coverage, 1),
            meta={
                "ton": ton,
                "arac_yasi": arac_yasi,
                "target_length_km": target_length_km,
            },
        )


_default_simulator: Optional[RouteSimulator] = None


def get_route_simulator() -> RouteSimulator:
    """Lazy singleton."""
    global _default_simulator
    if _default_simulator is None:
        _default_simulator = RouteSimulator()
    return _default_simulator


__all__ = ["RouteSimulator", "SimulationResult", "get_route_simulator"]
