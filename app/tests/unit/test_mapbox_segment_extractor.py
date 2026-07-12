"""MapboxClient.extract_segments — Phase 1.2 unit tests.

Synthetic + gerçek sample. SegmentInput'un tüm field'larını doldurmayı,
N+1 coord invariant'ını, _link variant'ı ana sınıfa indirme + birim
dönüşümlerini doğrular.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from v2.modules.route_simulation.domain.segment_simulator import SegmentInput
from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient

SAMPLES_DIR = Path(
    "docs/superpowers/plans/2026-05-29-route-segment-simulation-plan-mapbox-samples"
)


def _build_route(
    *,
    distances,
    speeds=None,
    maxspeeds=None,
    congestions=None,
    intersection_points=None,
    coords=None,
):
    intersections = [
        {"geometry_index": gi, "mapbox_streets_v8": {"class": cls}}
        for gi, cls in (intersection_points or [])
    ]
    leg = {
        "annotation": {
            "distance": distances,
            "speed": speeds or [None] * len(distances),
            "maxspeed": maxspeeds or [{"unknown": True}] * len(distances),
            "congestion": congestions or ["low"] * len(distances),
        },
        "steps": [{"intersections": intersections}],
    }
    return {
        "legs": [leg],
        "geometry": {
            "type": "LineString",
            "coordinates": coords
            or [[0.0, float(i)] for i in range(len(distances) + 1)],
        },
    }


def test_extract_segments_returns_one_per_distance_entry():
    route = _build_route(
        distances=[100.0, 200.0, 300.0],
        intersection_points=[(0, "motorway")],
    )
    segs, coords = MapboxClient.extract_segments(route)
    assert len(segs) == 3
    assert all(isinstance(s, SegmentInput) for s in segs)
    # N segment için N+1 coord
    assert len(coords) == 4


def test_length_converted_to_km():
    route = _build_route(distances=[500.0, 1500.0, 50.0])
    segs, _ = MapboxClient.extract_segments(route)
    assert segs[0].length_km == 0.5
    assert segs[1].length_km == 1.5
    assert segs[2].length_km == 0.05


def test_link_variant_stripped_to_base_class():
    route = _build_route(
        distances=[100.0, 100.0],
        intersection_points=[(0, "motorway_link")],
    )
    segs, _ = MapboxClient.extract_segments(route)
    assert segs[0].road_class == "motorway"
    assert segs[1].road_class == "motorway"


def test_traffic_speed_converted_ms_to_kmh():
    route = _build_route(
        distances=[100.0, 100.0, 100.0],
        speeds=[10.0, 20.0, None],  # m/s
    )
    segs, _ = MapboxClient.extract_segments(route)
    assert segs[0].traffic_speed_kmh == pytest.approx(36.0)
    assert segs[1].traffic_speed_kmh == pytest.approx(72.0)
    assert segs[2].traffic_speed_kmh is None


def test_maxspeed_extracts_km_h_and_skips_unknown():
    route = _build_route(
        distances=[100.0, 100.0, 100.0],
        maxspeeds=[
            {"speed": 130, "unit": "km/h"},
            {"unknown": True},
            {"speed": 55, "unit": "mph"},
        ],
    )
    segs, _ = MapboxClient.extract_segments(route)
    assert segs[0].maxspeed_kmh == 130.0
    assert segs[1].maxspeed_kmh is None
    assert segs[2].maxspeed_kmh == pytest.approx(55 * 1.60934, rel=0.001)


def test_congestion_preserved():
    route = _build_route(
        distances=[100.0, 100.0, 100.0, 100.0],
        congestions=["low", "moderate", "heavy", "severe"],
    )
    segs, _ = MapboxClient.extract_segments(route)
    assert [s.congestion for s in segs] == ["low", "moderate", "heavy", "severe"]


def test_grade_pct_defaults_zero_for_phase1_elevation_to_be_added_later():
    route = _build_route(distances=[100.0])
    segs, _ = MapboxClient.extract_segments(route)
    assert segs[0].grade_pct == 0.0


def test_empty_legs_returns_empty_segments():
    segs, coords = MapboxClient.extract_segments({"legs": []})
    assert segs == []
    assert coords == []


def test_missing_geometry_returns_empty_coords():
    route = _build_route(distances=[100.0])
    route.pop("geometry")
    segs, coords = MapboxClient.extract_segments(route)
    assert len(segs) == 1
    assert coords == []


# ---------- Gerçek sample JSON ile smoke ----------


@pytest.mark.parametrize(
    "sample_name",
    [
        "istanbul-ankara-otoyol-raw.json",
        "maslak-kadikoy-sehir-raw.json",
        "bursa-antalya-daglik-raw.json",
    ],
)
def test_real_sample_segment_count_matches_geometry_count(sample_name):
    sample = SAMPLES_DIR / sample_name
    if not sample.exists():
        pytest.skip("Sample yok")

    data = json.loads(sample.read_text(encoding="utf-8"))
    route = data["routes"][0]
    segs, coords = MapboxClient.extract_segments(route)

    expected_count = sum(len(leg["annotation"]["distance"]) for leg in route["legs"])
    assert len(segs) == expected_count
    assert len(coords) == expected_count + 1  # N+1 invariant

    # %95+ doluluk (intersections_with_mapbox_streets_v8 ≥ 99%)
    non_empty = sum(1 for s in segs if s.road_class)
    assert non_empty / len(segs) >= 0.95

    # Traffic speed annotation %100 doluluk (Phase 0.1 ölçüm)
    speed_present = sum(1 for s in segs if s.traffic_speed_kmh is not None)
    assert speed_present == len(segs)


def test_real_maslak_kadikoy_segment_summary():
    """Aggregate sanity check: Maslak-Kadıköy 19km, FSM köprü dahil."""
    sample = SAMPLES_DIR / "maslak-kadikoy-sehir-raw.json"
    if not sample.exists():
        pytest.skip("Sample yok")

    data = json.loads(sample.read_text(encoding="utf-8"))
    route = data["routes"][0]
    segs, _ = MapboxClient.extract_segments(route)

    total_km = sum(s.length_km for s in segs)
    # Mapbox metadata distance: 18908.667m → 18.91 km
    assert total_km == pytest.approx(18.91, abs=0.05)

    # Motorway segment'leri olmalı (FSM köprüsü O-1)
    motorway_segs = [s for s in segs if s.road_class == "motorway"]
    assert len(motorway_segs) > 0
