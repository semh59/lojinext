"""LokasyonHydrator — Phase 3.2 unit testleri.

Mapbox ve Open-Meteo client'larını mock'luyoruz; lokasyon objesini
in-memory dolduruyoruz (DB commit caller'da).
"""

from __future__ import annotations

from typing import List

import pytest

from v2.modules.location.application.hydration import LokasyonHydrator
from v2.modules.location.public import Lokasyon
from v2.modules.route_simulation.domain.segment_simulator import SegmentInput


class FakeMapbox:
    def __init__(self, result):
        self._result = result
        self.calls: List = []

    async def get_segments(self, start, end):
        self.calls.append((start, end))
        return self._result


class FakeElev:
    def __init__(self, elevations):
        self._elevations = elevations
        self.calls: List = []

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


def _lokasyon(**kw) -> Lokasyon:
    base = dict(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=10.0,
        cikis_lat=41.0,
        cikis_lon=28.0,
        varis_lat=40.0,
        varis_lon=29.0,
    )
    base.update(kw)
    return Lokasyon(**base)


async def test_full_hydration_populates_segments_and_meta():
    raw = [_seg(0.25), _seg(0.25), _seg(0.25), _seg(0.25)]
    raw_coords = [(28.0 + i * 0.0025, 41.0) for i in range(5)]
    mb = FakeMapbox((raw, raw_coords))
    elev = FakeElev([0.0, 25.0, 25.0])

    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()

    result = await hyd.hydrate(lok)

    assert result is not None
    assert result.raw_segment_count == 4
    assert result.resampled_segment_count == 2
    assert result.elevation_coverage_pct == 100.0

    # lokasyon.segments doldurulmuş, header güncellenmiş
    assert len(lok.segments) == 2
    assert lok.raw_segment_count == 4
    assert lok.resampled_segment_count == 2
    assert lok.hydrated_at is not None


async def test_mapbox_failure_returns_none_and_no_change():
    mb = FakeMapbox(None)
    elev = FakeElev([])
    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()

    result = await hyd.hydrate(lok)
    assert result is None
    assert lok.segments == []
    assert lok.hydrated_at is None
    assert len(elev.calls) == 0  # elevation çağrılmamış


async def test_missing_coords_returns_none():
    mb = FakeMapbox(None)
    elev = FakeElev([])
    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon(cikis_lat=None)

    result = await hyd.hydrate(lok)
    assert result is None
    assert len(mb.calls) == 0  # Mapbox bile çağrılmamış


async def test_grade_computed_from_elevation_delta():
    # Tek bucket 500m, elevation 0 → 25 → grade = 5%
    raw = [_seg(0.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mb = FakeMapbox((raw, raw_coords))
    elev = FakeElev([0.0, 25.0])

    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()
    await hyd.hydrate(lok)

    assert lok.segments[0].grade_pct == pytest.approx(5.0, abs=0.01)


async def test_idempotent_clears_old_segments():
    """Yeniden hidrate → eski segment listesi temizlenir."""
    raw = [_seg(0.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mb = FakeMapbox((raw, raw_coords))
    elev = FakeElev([0.0, 10.0])

    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()
    await hyd.hydrate(lok)
    assert len(lok.segments) == 1

    # Tekrar çağır — eski segment YOK, yeni listede tek segment
    await hyd.hydrate(lok)
    assert len(lok.segments) == 1
    assert len(mb.calls) == 2  # iki kez fetch edildi


async def test_partial_elevation_falls_back_to_input_grade():
    raw = [_seg(0.5, grade=1.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mb = FakeMapbox((raw, raw_coords))
    elev = FakeElev([None, None])

    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()
    result = await hyd.hydrate(lok)
    assert result is not None
    # Elevation hiç yok → input grade (resampler weighted avg sonucu) korunur
    assert lok.segments[0].grade_pct == pytest.approx(1.5, abs=0.01)


async def test_traffic_not_persisted_phase35():
    """Phase 3.5: trafik artık lokasyon_segments'e YAZILMIYOR.
    Trafik zamansal veri — sefer simülasyonu route_segments'a yazar.
    """
    raw = [_seg(0.5, traffic=42, congestion="heavy")]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mb = FakeMapbox((raw, raw_coords))
    elev = FakeElev([0.0, 0.0])

    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()
    await hyd.hydrate(lok)

    # LokasyonSegment'te artık bu alanlar YOK
    seg = lok.segments[0]
    assert not hasattr(seg, "traffic_speed_kmh") or seg.traffic_speed_kmh is None
    assert not hasattr(seg, "congestion") or seg.congestion is None
    # Statik veriler doğru
    assert seg.length_km == pytest.approx(0.5)
    assert seg.road_class == "motorway"
    assert seg.maxspeed_kmh == 130.0


async def test_midpoint_calculated_per_segment():
    raw = [_seg(0.5)]
    raw_coords = [(28.0, 41.0), (28.005, 41.0)]
    mb = FakeMapbox((raw, raw_coords))
    elev = FakeElev([0.0, 0.0])

    hyd = LokasyonHydrator(mapbox_client=mb, elevation_client=elev)
    lok = _lokasyon()
    await hyd.hydrate(lok)

    seg = lok.segments[0]
    # midpoint = boundary[0] ile boundary[1] ortası
    assert seg.mid_lon == pytest.approx(28.0025, abs=0.0001)
    assert seg.mid_lat == pytest.approx(41.0)
