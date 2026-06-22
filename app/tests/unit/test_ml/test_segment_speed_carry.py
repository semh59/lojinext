"""SegmentOutput hız annotation'larını taşıyor mu (persist + coverage için)."""

import pytest

from app.core.ml.segment_simulator import SegmentInput, simulate_segment

pytestmark = pytest.mark.unit


def test_segment_output_carries_traffic_speed_and_source():
    seg = SegmentInput(
        length_km=1.0,
        grade_pct=0.0,
        road_class="motorway",
        maxspeed_kmh=90.0,
        traffic_speed_kmh=72.0,
        congestion="moderate",
    )
    out = simulate_segment(seg, ton=20.0, arac_yasi=5)
    assert out.maxspeed_kmh == 90.0
    assert out.traffic_speed_kmh == 72.0
    assert out.congestion == "moderate"
    assert out.speed_source == "traffic"  # traffic varsa kaynak traffic


def test_segment_output_speed_source_maxspeed_then_roadclass():
    only_max = SegmentInput(
        length_km=1.0, grade_pct=0.0, road_class="primary", maxspeed_kmh=80.0
    )
    assert simulate_segment(only_max, ton=10.0).speed_source == "maxspeed"

    none_speed = SegmentInput(length_km=1.0, grade_pct=0.0, road_class="primary")
    assert simulate_segment(none_speed, ton=10.0).speed_source == "road_class"
