"""segment_resampler — Phase 1.3 unit tests.

Bucket aggregation invariant'ları + boundary coord interpolasyonu.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from v2.modules.route_simulation.domain.segment_resampler import resample_segments
from v2.modules.route_simulation.domain.segment_simulator import SegmentInput
from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient

SAMPLES_DIR = Path(
    "docs/superpowers/plans/2026-05-29-route-segment-simulation-plan-mapbox-samples"
)


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


def _coords(n: int):
    """N+1 boundary coord — basit horizontal projeksiyon."""
    return [(28.0 + i * 0.001, 41.0) for i in range(n + 1)]


def test_empty_input_returns_empty():
    segs, coords = resample_segments([], [])
    assert segs == []
    assert coords == []


def test_single_segment_under_target_yields_single_bucket():
    inp = [_seg(0.3)]
    segs, coords = resample_segments(inp, _coords(1), target_length_km=0.5)
    assert len(segs) == 1
    assert segs[0].length_km == pytest.approx(0.3, abs=1e-6)
    assert len(coords) == 2  # start + end


def test_exact_multiple_yields_clean_buckets():
    # 4 × 250m segment = 1000m → 500m target → 2 bucket
    inp = [_seg(0.25), _seg(0.25), _seg(0.25), _seg(0.25)]
    segs, coords = resample_segments(inp, _coords(4), target_length_km=0.5)
    assert len(segs) == 2
    assert all(s.length_km == pytest.approx(0.5, abs=1e-6) for s in segs)
    assert len(coords) == 3


def test_short_remainder_creates_final_partial_bucket():
    # 0.5 + 0.5 + 0.3 = 1.3 km → 500m target → 3 bucket (0.5/0.5/0.3)
    inp = [_seg(0.5), _seg(0.5), _seg(0.3)]
    segs, _ = resample_segments(inp, _coords(3), target_length_km=0.5)
    assert len(segs) == 3
    assert segs[0].length_km == pytest.approx(0.5)
    assert segs[1].length_km == pytest.approx(0.5)
    assert segs[2].length_km == pytest.approx(0.3, abs=1e-6)


def test_weighted_avg_for_numeric_attributes():
    # Bucket'a düşen iki overlap: 100m@grade=4, 400m@grade=0 → weighted avg = 0.8
    inp = [_seg(0.1, grade=4.0, traffic=80), _seg(0.4, grade=0.0, traffic=90)]
    segs, _ = resample_segments(inp, _coords(2), target_length_km=0.5)
    assert len(segs) == 1
    s = segs[0]
    assert s.grade_pct == pytest.approx(0.8, abs=0.01)
    # traffic weighted: (80*0.1 + 90*0.4) / 0.5 = 88
    assert s.traffic_speed_kmh == pytest.approx(88.0, abs=0.5)


def test_mode_picks_dominant_road_class():
    # 60% primary, 40% motorway → primary mode beklenir
    inp = [_seg(0.3, road_class="primary"), _seg(0.2, road_class="motorway")]
    segs, _ = resample_segments(inp, _coords(2), target_length_km=0.5)
    assert segs[0].road_class == "primary"


def test_mode_picks_dominant_congestion():
    inp = [
        _seg(0.1, congestion="heavy"),
        _seg(0.3, congestion="moderate"),
        _seg(0.1, congestion="low"),
    ]
    segs, _ = resample_segments(inp, _coords(3), target_length_km=0.5)
    assert segs[0].congestion == "moderate"


def test_none_maxspeed_skipped_in_weighted_avg():
    # İki segment, biri None maxspeed
    inp = [_seg(0.25, maxspeed=120), _seg(0.25, maxspeed=None)]
    segs, _ = resample_segments(inp, _coords(2), target_length_km=0.5)
    # Sadece 120 km/h olan segment ortalamaya katılır
    assert segs[0].maxspeed_kmh == pytest.approx(120.0)


def test_boundary_coords_interpolated_linearly():
    # 2 input segment, lineer coord projeksiyonu — bucket boundary'leri tam ortada
    inp = [_seg(0.25), _seg(0.25)]
    coords = [(28.0, 41.0), (28.25, 41.0), (28.5, 41.0)]  # cum: 0, 0.25, 0.5
    segs, b_coords = resample_segments(inp, coords, target_length_km=0.5)
    # Tek bucket — boundary'ler [0, 0.5] → (28.0, 41) ve (28.5, 41)
    assert len(segs) == 1
    assert b_coords[0] == pytest.approx((28.0, 41.0))
    assert b_coords[1] == pytest.approx((28.5, 41.0))


def test_bucket_count_matches_total_distance():
    # 5400m route, 500m bucket → 11 bucket (10 full + 1 final 400m)
    inp = [_seg(0.05) for _ in range(108)]  # 108 × 50m = 5.4 km
    segs, _ = resample_segments(inp, _coords(108), target_length_km=0.5)
    total = sum(s.length_km for s in segs)
    assert total == pytest.approx(5.4, abs=1e-6)
    assert len(segs) == 11  # 10 × 500m + 1 × 400m


def test_invalid_target_raises():
    inp = [_seg(0.5)]
    with pytest.raises(ValueError, match="target_length_km"):
        resample_segments(inp, _coords(1), target_length_km=0)


def test_negative_lengths_treated_as_zero():
    # Ham Mapbox bazen 0 uzunluklu segment'ler döndürebilir; resampler skip
    inp = [_seg(0.5), _seg(0.0), _seg(0.5)]
    segs, _ = resample_segments(inp, _coords(3), target_length_km=0.5)
    total = sum(s.length_km for s in segs)
    assert total == pytest.approx(1.0, abs=1e-6)


# ---------- Real Mapbox sample ----------


def test_real_maslak_kadikoy_resamples_to_500m_buckets():
    sample = SAMPLES_DIR / "maslak-kadikoy-sehir-raw.json"
    if not sample.exists():
        pytest.skip("Sample yok")

    data = json.loads(sample.read_text(encoding="utf-8"))
    route = data["routes"][0]
    raw_segs, raw_coords = MapboxClient.extract_segments(route)
    total_raw_km = sum(s.length_km for s in raw_segs)

    resamp_segs, resamp_coords = resample_segments(
        raw_segs, raw_coords, target_length_km=0.5
    )

    # Toplam km korunmalı
    total_resamp_km = sum(s.length_km for s in resamp_segs)
    assert total_resamp_km == pytest.approx(total_raw_km, rel=0.001)

    # 18.91 km / 0.5 = ~38 bucket
    assert 35 <= len(resamp_segs) <= 40

    # N+1 coords
    assert len(resamp_coords) == len(resamp_segs) + 1

    # Bucket length'lerinin son hariç hepsi 500m ± 0.001
    for s in resamp_segs[:-1]:
        assert s.length_km == pytest.approx(0.5, abs=0.001)

    # En az 1 motorway bucket (FSM köprüsü)
    assert any(s.road_class == "motorway" for s in resamp_segs)
