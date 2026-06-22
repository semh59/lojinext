"""RouteSimulator orkestrasyonu — Phase 1.4 unit tests.

Mapbox ve Open-Meteo client'larını mock'luyoruz; pipeline'ın doğru
sırayla aktığını ve elevation'dan grade hesabının doğru olduğunu
doğruluyoruz.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from app.core.ml.segment_simulator import SegmentInput
from app.core.services.route_simulator import RouteSimulator, SimulationResult


class FakeMapboxClient:
    """get_segments stub."""

    def __init__(self, result):
        self._result = result
        self.calls: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []

    async def get_segments(self, start, end):
        self.calls.append((start, end))
        return self._result


class FakeElevationClient:
    """get_elevations stub."""

    def __init__(self, elevations):
        self._elevations = elevations
        self.calls: List[List[Tuple[float, float]]] = []

    async def get_elevations(self, coords):
        self.calls.append(list(coords))
        return list(self._elevations)


def _seg(
    length_km,
    road_class="motorway",
    maxspeed=130,
    traffic=85,
    congestion="low",
    grade=0.0,
) -> SegmentInput:
    return SegmentInput(
        length_km=length_km,
        grade_pct=grade,
        road_class=road_class,
        maxspeed_kmh=float(maxspeed) if maxspeed is not None else None,
        traffic_speed_kmh=float(traffic) if traffic is not None else None,
        congestion=congestion,
    )


async def test_full_pipeline_returns_summary():
    # 4 × 250m = 1000m, 500m target → 2 bucket
    raw = [_seg(0.25), _seg(0.25), _seg(0.25), _seg(0.25)]
    raw_coords = [(28.0 + i * 0.0025, 41.0) for i in range(5)]  # N+1
    mapbox = FakeMapboxClient((raw, raw_coords))

    # 3 boundary coord → 3 elevation (M+1, M=2)
    elev = FakeElevationClient([0.0, 25.0, 25.0])

    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.01,
        varis_lat=41.0,
        ton=15.0,
        arac_yasi=5,
    )

    assert result is not None
    assert isinstance(result, SimulationResult)
    assert result.raw_segment_count == 4
    assert result.resampled_segment_count == 2
    assert result.elevation_coverage_pct == 100.0
    assert result.summary.total_km == pytest.approx(1.0)
    assert len(result.summary.segments) == 2


async def test_mapbox_failure_returns_none():
    mapbox = FakeMapboxClient(None)
    elev = FakeElevationClient([])
    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)

    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=29.0,
        varis_lat=40.0,
    )
    assert result is None
    # Elevation çağrılmamalı
    assert len(elev.calls) == 0


async def test_empty_segments_returns_none():
    raw_coords = [(28.0, 41.0), (28.001, 41.0)]
    mapbox = FakeMapboxClient(([], raw_coords))
    elev = FakeElevationClient([])
    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)

    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.001,
        varis_lat=41.0,
    )
    assert result is None


async def test_grade_pct_computed_from_elevation_delta():
    # Tek bucket 500m, elevation 0 → 25 → grade = 25/500 * 100 = 5%
    raw = [_seg(0.5, grade=0.0)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mapbox = FakeMapboxClient((raw, raw_coords))
    elev = FakeElevationClient([0.0, 25.0])

    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.005,
        varis_lat=41.0,
    )
    assert result is not None
    seg_out = result.summary.segments[0]
    assert seg_out.grade_pct == pytest.approx(5.0, abs=0.01)


async def test_negative_grade_for_descent():
    raw = [_seg(0.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mapbox = FakeMapboxClient((raw, raw_coords))
    elev = FakeElevationClient([100.0, 80.0])  # 20m iniş / 500m

    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.005,
        varis_lat=41.0,
    )
    assert result is not None
    # grade = -20 / 500 * 100 = -4%
    assert result.summary.segments[0].grade_pct == pytest.approx(-4.0, abs=0.01)


async def test_missing_elevation_fallback_grade_zero():
    raw = [_seg(0.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mapbox = FakeMapboxClient((raw, raw_coords))
    elev = FakeElevationClient([None, None])

    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.005,
        varis_lat=41.0,
    )
    assert result is not None
    # Elevation yok → grade fallback = input default = 0
    assert result.summary.segments[0].grade_pct == 0.0
    assert result.elevation_coverage_pct == 0.0


async def test_partial_elevation_coverage_reported():
    # 4 boundary, 3 dolu → %75
    raw = [_seg(0.5), _seg(0.5), _seg(0.5)]
    raw_coords = [(28.0 + i * 0.005, 41.0) for i in range(4)]
    mapbox = FakeMapboxClient((raw, raw_coords))
    # 3 bucket boundary (M+1=4) — 3 dolu 1 None
    elev = FakeElevationClient([0.0, 10.0, None, 20.0])

    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.015,
        varis_lat=41.0,
    )
    assert result is not None
    assert result.elevation_coverage_pct == 75.0


async def test_phase35_simulate_from_lokasyon_method_removed():
    """Phase 3.5: simulate_from_lokasyon kaldırıldı.

    Endpoint lokasyon_id verildiğinde koordinatları lokasyondan alıp
    standart simulate() çağırır — Mapbox 24h cache + Open-Meteo 30 gün
    cache zaten ucuz; her sefer GÜNCEL trafik alır.
    """
    sim = RouteSimulator(
        mapbox_client=FakeMapboxClient(None),
        elevation_client=FakeElevationClient([]),
    )
    assert not hasattr(sim, "simulate_from_lokasyon")


async def test_meta_carries_simulation_params():
    raw = [_seg(0.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mapbox = FakeMapboxClient((raw, raw_coords))
    elev = FakeElevationClient([0.0, 0.0])

    sim = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    result = await sim.simulate(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=28.005,
        varis_lat=41.0,
        ton=22.5,
        arac_yasi=10,
        target_length_km=0.25,
    )
    assert result is not None
    assert result.meta == {
        "ton": 22.5,
        "arac_yasi": 10,
        "target_length_km": 0.25,
    }
