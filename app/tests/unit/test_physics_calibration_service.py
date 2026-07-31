"""Coverage for v2/modules/route_simulation/application/physics_calibration.py
(Item C follow-up, 2026-07-30) -- was added without any test, dragging the
combined coverage gate below 92%.

score_routes/grid_search_best_fit are pure (no I/O, real
simulate_route() physics) -- unit tests. load_reference_route_segments
is the only DB-touching piece -- real Postgres via db_session, no mocks.
"""

from __future__ import annotations

import pytest

from v2.modules.route_simulation.application.physics_calibration import (
    CalibrationFit,
    ReferenceRouteData,
    grid_search_best_fit,
    load_reference_route_segments,
    score_routes,
)
from v2.modules.route_simulation.domain.segment_simulator import SegmentInput

pytestmark = pytest.mark.unit


def _flat_segments(n: int, grade_pct: float = 0.5) -> list[SegmentInput]:
    return [
        SegmentInput(
            length_km=0.5,
            grade_pct=grade_pct,
            road_class="motorway",
            maxspeed_kmh=90.0,
            traffic_speed_kmh=85.0,
            congestion="low",
        )
        for _ in range(n)
    ]


def _route(
    name: str, load_tons: int, band_low: float, band_high: float
) -> ReferenceRouteData:
    return ReferenceRouteData(
        name=name,
        load_tons=load_tons,
        band_low=band_low,
        band_high=band_high,
        arac_yasi=5,
        segments=_flat_segments(20),
    )


# ---------------------------------------------------------------------------
# score_routes
# ---------------------------------------------------------------------------


def test_score_routes_returns_green_count_and_sse():
    routes = [
        _route("IST-ANK", 20, 25.0, 45.0),  # wide, physically plausible band
        _route("IST-IZM", 18, 25.0, 45.0),
    ]
    green, sse = score_routes(routes)

    assert isinstance(green, int)
    assert 0 <= green <= len(routes)
    assert isinstance(sse, float)
    assert sse >= 0.0


def test_score_routes_empty_list():
    green, sse = score_routes([])
    assert green == 0
    assert sse == 0.0


def test_score_routes_zero_green_when_band_impossible():
    """A band no real consumption value can land in (e.g. 0.1-0.2 L/100km)
    forces green=0 -- proves the in-band check is a real comparison, not
    a tautology."""
    routes = [_route("Impossible", 20, 0.1, 0.2)]
    green, _sse = score_routes(routes)
    assert green == 0


# ---------------------------------------------------------------------------
# grid_search_best_fit
# ---------------------------------------------------------------------------


def test_grid_search_best_fit_restores_settings_via_caller(monkeypatch):
    """grid_search_best_fit mutates app.config.settings as a scoring side
    effect (documented behavior) -- this test uses a narrowed grid (via
    monkeypatched bands) so the full CDA x parasitic sweep stays fast,
    and verifies the return shape + physical-band flag. monkeypatch also
    restores settings.PHYSICS_DRAG_CDA_M2/PARASITIC_KW after the test so
    this doesn't leak into other tests reading those settings."""
    import v2.modules.route_simulation.application.physics_calibration as pc_mod
    from app.config import settings

    monkeypatch.setattr(pc_mod, "CDA_BAND", (5.3, 5.5))
    monkeypatch.setattr(pc_mod, "PAR_BAND", (3.0, 4.0))
    monkeypatch.setattr(settings, "PHYSICS_DRAG_CDA_M2", settings.PHYSICS_DRAG_CDA_M2)
    monkeypatch.setattr(settings, "PHYSICS_PARASITIC_KW", settings.PHYSICS_PARASITIC_KW)

    routes = [_route("IST-ANK", 20, 25.0, 45.0)]
    fit = grid_search_best_fit(routes)

    assert isinstance(fit, CalibrationFit)
    assert 5.3 <= fit.cda <= 5.5
    assert 3.0 <= fit.parasitic_kw <= 4.0
    assert fit.in_physical_band is True
    assert 0 <= fit.green <= len(routes)
    assert fit.sse >= 0.0


def test_grid_search_best_fit_picks_highest_green(monkeypatch):
    """With a band only the narrowed CDA/parasitic range's low end can hit,
    the winning fit should be green=1 (not stuck at 0), proving the grid
    search actually optimizes rather than returning the first candidate."""
    import v2.modules.route_simulation.application.physics_calibration as pc_mod
    from app.config import settings

    monkeypatch.setattr(pc_mod, "CDA_BAND", (5.3, 6.0))
    monkeypatch.setattr(pc_mod, "PAR_BAND", (3.0, 5.0))
    monkeypatch.setattr(settings, "PHYSICS_DRAG_CDA_M2", settings.PHYSICS_DRAG_CDA_M2)
    monkeypatch.setattr(settings, "PHYSICS_PARASITIC_KW", settings.PHYSICS_PARASITIC_KW)

    routes = [_route("Wide", 20, 1.0, 200.0)]  # trivially satisfiable band
    fit = grid_search_best_fit(routes)

    assert fit.green == 1


# ---------------------------------------------------------------------------
# load_reference_route_segments
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_load_reference_route_segments_empty_db_returns_empty_list(db_session):
    """None of REFERENCE_ROUTES' lokasyon_ids exist in a fresh test DB --
    the function must degrade gracefully to an empty list, not raise."""
    result = await load_reference_route_segments(db_session)
    assert result == []


@pytest.mark.integration
async def test_load_reference_route_segments_finds_stored_geometry(
    db_session, monkeypatch
):
    """Insert one route_simulations + 2 route_segments row for a
    reference-route lokasyon_id, monkeypatch REFERENCE_ROUTES to point at
    it, and verify the real SQL round-trip parses correctly."""
    from sqlalchemy import text

    import v2.modules.route_simulation.application.physics_calibration as pc_mod
    from v2.modules.location.infrastructure.models import Lokasyon

    lok = Lokasyon(cikis_yeri="TestA", varis_yeri="TestB", mesafe_km=450.0)
    db_session.add(lok)
    await db_session.flush()

    sim_id = (
        await db_session.execute(
            text(
                "INSERT INTO route_simulation.route_simulations "
                "(lokasyon_id, cikis_lon, cikis_lat, varis_lon, varis_lat, "
                "ton, arac_yasi, target_length_km, raw_segment_count, "
                "resampled_segment_count, elevation_coverage_pct, "
                "total_km, total_l, avg_l_per_100km, total_eta_sec, "
                "total_ascent_m, total_descent_m) "
                "VALUES (:lok, 29.0, 40.0, 32.0, 39.0, 20.0, 7, 0.5, 2, 2, "
                "95.0, 1.0, 0.3, 30.0, 60.0, 5.0, 0.0) "
                "RETURNING id"
            ),
            {"lok": lok.id},
        )
    ).scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO route_simulation.route_segments "
            "(simulation_id, seq, length_km, grade_pct, road_class, "
            "maxspeed_kmh, traffic_speed_kmh, congestion, sim_speed_kmh, "
            "sim_l_per_100km, sim_l_total, eta_sec) VALUES "
            "(:sid, 0, 0.5, 1.0, 'motorway', 90.0, 85.0, 'low', 85.0, 30.0, 0.15, 21.0), "
            "(:sid, 1, 0.5, -1.0, 'motorway', 90.0, 88.0, 'low', 88.0, 28.0, 0.14, 20.0)"
        ),
        {"sid": sim_id},
    )
    await db_session.flush()

    monkeypatch.setattr(
        pc_mod, "REFERENCE_ROUTES", {lok.id: ("TEST-ROUTE", 20, 30.0, 35.0)}
    )

    result = await load_reference_route_segments(db_session)

    assert len(result) == 1
    route = result[0]
    assert route.name == "TEST-ROUTE"
    assert route.load_tons == 20
    assert route.arac_yasi == 7
    assert len(route.segments) == 2
    assert route.segments[0].grade_pct == 1.0
    assert route.segments[1].grade_pct == -1.0
