"""_serialize_simulation segment koordinat + hız annotation döndürür mü."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.routes import _serialize_simulation

pytestmark = pytest.mark.unit


def _sim():
    return SimpleNamespace(
        id=42,
        created_at=datetime(2026, 6, 14, tzinfo=timezone.utc),
        total_km=150.0,
        total_eta_sec=7200.0,
        total_l=48.0,
        avg_l_per_100km=32.0,
        total_ascent_m=300.0,
        total_descent_m=280.0,
        raw_segment_count=900,
        resampled_segment_count=300,
        elevation_coverage_pct=100.0,
        ton=20.0,
        arac_yasi=5,
        target_length_km=0.5,
    )


def _seg(**kw):
    base = dict(
        seq=0,
        length_km=0.5,
        grade_pct=1.2,
        road_class="motorway",
        sim_speed_kmh=82.0,
        sim_l_per_100km=33.5,
        sim_l_total=0.17,
        eta_sec=22.0,
        mid_lon=29.01,
        mid_lat=40.98,
        maxspeed_kmh=90.0,
        traffic_speed_kmh=78.0,
        congestion="moderate",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_serialize_exposes_coords_and_speed_source():
    resp = _serialize_simulation(_sim(), [_seg()])
    seg = resp.segments[0]
    assert seg.mid_lon == 29.01
    assert seg.mid_lat == 40.98
    assert seg.maxspeed_kmh == 90.0
    assert seg.traffic_speed_kmh == 78.0
    assert seg.congestion == "moderate"
    assert seg.speed_source == "traffic"  # traffic_speed>0 → traffic


def test_serialize_speed_source_fallback_chain():
    # traffic yok → maxspeed
    s1 = _serialize_simulation(_sim(), [_seg(traffic_speed_kmh=None)]).segments[0]
    assert s1.speed_source == "maxspeed"
    # ikisi de yok → road_class
    s2 = _serialize_simulation(
        _sim(), [_seg(traffic_speed_kmh=None, maxspeed_kmh=None)]
    ).segments[0]
    assert s2.speed_source == "road_class"


def test_serialize_handles_missing_coords():
    seg = _serialize_simulation(_sim(), [_seg(mid_lon=None, mid_lat=None)]).segments[0]
    assert seg.mid_lon is None and seg.mid_lat is None
