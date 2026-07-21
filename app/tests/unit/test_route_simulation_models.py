"""RouteSimulation + RouteSegment ORM smoke (Phase 2.1).

DB'siz: model'in import edilebilirliği, FK + cascade konfigürasyonu, ORM
relationship'in iki yönlü çalıştığı.
"""

from __future__ import annotations

from app.database.models import Base
from v2.modules.route_simulation.public import RouteSegment, RouteSimulation


def test_models_registered_in_metadata():
    assert "route_simulations" in Base.metadata.tables
    assert "route_segments" in Base.metadata.tables


def test_route_segments_fk_targets_route_simulations():
    seg_table = Base.metadata.tables["route_segments"]
    fks = list(seg_table.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "route_simulations"


def test_route_segments_cascade_on_delete():
    seg_table = Base.metadata.tables["route_segments"]
    fk = list(seg_table.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_unique_constraint_simulation_id_seq():
    seg_table = Base.metadata.tables["route_segments"]
    uniques = [
        c for c in seg_table.constraints if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert len(uniques) >= 1
    columns = {col.name for c in uniques for col in c.columns}
    assert {"simulation_id", "seq"} <= columns


def test_route_simulations_has_lokasyon_id_fk():
    """Phase 3.3 — route_simulations.lokasyon_id FK SET NULL."""
    t = Base.metadata.tables["route_simulations"]
    cols = {c.name for c in t.columns}
    assert "lokasyon_id" in cols
    # FK target
    lokasyon_fk = [fk for fk in t.foreign_keys if fk.column.table.name == "lokasyonlar"]
    assert len(lokasyon_fk) == 1
    assert lokasyon_fk[0].ondelete == "SET NULL"


def test_back_population_relationship():
    sim = RouteSimulation(
        cikis_lon=28.0,
        cikis_lat=41.0,
        varis_lon=29.0,
        varis_lat=40.0,
        ton=15.0,
        arac_yasi=5,
        target_length_km=0.5,
    )
    seg = RouteSegment(seq=0, length_km=0.5, simulation=sim)
    # back_populates → segments list otomatik dolar
    assert seg in sim.segments
    assert seg.simulation is sim
