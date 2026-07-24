"""Lokasyon zenginleştirme + LokasyonSegment ORM (Phase 3.1).

DB'siz model smoke testleri.
"""

from __future__ import annotations

from v2.modules.location.public import Lokasyon, LokasyonSegment
from v2.modules.shared_kernel.infrastructure.base import Base


def test_lokasyon_segments_registered():
    # FAZ2 (schema-per-module): a table with __table_args__ = {"schema": ...}
    # is keyed in Base.metadata.tables as "<schema>.<table>", not the bare name.
    assert "location.lokasyon_segments" in Base.metadata.tables


def test_lokasyonlar_has_new_phase3_columns():
    cols = {c.name for c in Base.metadata.tables["location.lokasyonlar"].columns}
    assert "ad" in cols
    assert "hydrated_at" in cols
    assert "raw_segment_count" in cols
    assert "resampled_segment_count" in cols
    assert "elevation_coverage_pct" in cols


def test_lokasyon_segments_fk_cascade_on_delete():
    t = Base.metadata.tables["location.lokasyon_segments"]
    fk = list(t.foreign_keys)[0]
    assert fk.column.table.name == "lokasyonlar"
    assert fk.ondelete == "CASCADE"


def test_unique_lokasyon_seq():
    t = Base.metadata.tables["location.lokasyon_segments"]
    uniques = [c for c in t.constraints if c.__class__.__name__ == "UniqueConstraint"]
    cols = {col.name for c in uniques for col in c.columns}
    assert {"lokasyon_id", "seq"} <= cols


def test_back_population():
    lok = Lokasyon(
        cikis_yeri="İstanbul",
        varis_yeri="Ankara",
        mesafe_km=443.5,
        ad="Sabah Kargosu — IST-ANK",
    )
    seg = LokasyonSegment(
        seq=0,
        length_km=0.5,
        grade_pct=1.2,
        road_class="motorway",
        maxspeed_kmh=130.0,
        lokasyon=lok,
    )
    assert seg in lok.segments
    assert seg.lokasyon is lok


def test_default_phase3_counts_are_zero():
    lok = Lokasyon(cikis_yeri="A", varis_yeri="B", mesafe_km=10.0)
    # ORM-only smoke — DB default'lar 0
    assert lok.raw_segment_count in (0, None)
    assert lok.resampled_segment_count in (0, None)
