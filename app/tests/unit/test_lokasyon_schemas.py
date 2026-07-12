"""Lokasyon schemas — Phase 3.4 unit tests (ad + segments)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from v2.modules.location.schemas import (
    LokasyonBase,
    LokasyonCreate,
    LokasyonResponse,
    LokasyonSegmentResponse,
    LokasyonSegmentsResponse,
    LokasyonUpdate,
)


def test_lokasyon_base_accepts_ad_field():
    obj = LokasyonBase(
        ad="Sabah Kargosu — İST-BUR",
        cikis_yeri="İstanbul",
        varis_yeri="Bursa",
        mesafe_km=240.0,
    )
    assert obj.ad == "Sabah Kargosu — İST-BUR"


def test_lokasyon_base_ad_optional():
    obj = LokasyonBase(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=10.0,
    )
    assert obj.ad is None


def test_lokasyon_base_ad_max_length():
    with pytest.raises(ValidationError):
        LokasyonBase(
            ad="x" * 151,
            cikis_yeri="A",
            varis_yeri="B",
            mesafe_km=10.0,
        )


def test_lokasyon_update_ad_partial():
    upd = LokasyonUpdate(ad="Yeni isim")
    dumped = upd.model_dump(exclude_unset=True)
    assert dumped == {"ad": "Yeni isim"}


def test_lokasyon_response_includes_hydration_meta():
    resp = LokasyonResponse(
        id=1,
        ad="Test",
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=10.0,
        hydrated_at=datetime.now(timezone.utc),
        raw_segment_count=100,
        resampled_segment_count=20,
        elevation_coverage_pct=98.5,
    )
    assert resp.hydrated_at is not None
    assert resp.raw_segment_count == 100
    assert resp.elevation_coverage_pct == 98.5


def test_lokasyon_response_hydration_meta_defaults():
    resp = LokasyonResponse(
        id=1,
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=10.0,
    )
    # Hidrate edilmemiş güzergah
    assert resp.hydrated_at is None
    assert resp.raw_segment_count == 0
    assert resp.resampled_segment_count == 0
    assert resp.elevation_coverage_pct == 0.0


def test_segments_response_shape():
    obj = LokasyonSegmentsResponse(
        lokasyon_id=42,
        ad="Test",
        hydrated_at=datetime.now(timezone.utc),
        raw_segment_count=100,
        resampled_segment_count=20,
        elevation_coverage_pct=98.5,
        segments=[
            LokasyonSegmentResponse(
                seq=0,
                length_km=0.5,
                grade_pct=2.0,
                road_class="motorway",
                maxspeed_kmh=130.0,
                mid_lon=28.5,
                mid_lat=40.5,
            ),
        ],
    )
    assert obj.lokasyon_id == 42
    assert len(obj.segments) == 1
    assert obj.segments[0].road_class == "motorway"


def test_segment_response_has_no_traffic_fields_phase35():
    """Phase 3.5 — trafik artık LokasyonSegmentResponse'ta YOK."""
    seg = LokasyonSegmentResponse(seq=0, length_km=0.5, grade_pct=0.0)
    fields = seg.model_dump().keys()
    assert "traffic_speed_kmh" not in fields
    assert "congestion" not in fields


def test_create_dumps_with_ad():
    payload = LokasyonCreate(
        ad="Test güzergah",
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=10.0,
    )
    dump = payload.model_dump()
    assert dump["ad"] == "Test güzergah"
    assert dump["cikis_yeri"] == "A"
