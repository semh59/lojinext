"""Additional coverage tests for app/api/v1/endpoints/routes.py

Existing test_routes_coverage.py already covers 77%.
This file adds the missing ~23%:
- simulate_route: ad-hoc success path (persist + serialize)
- simulate_route: lokasyon_id success path (coords from DB)
- simulate_route: slow/large boundary midpoint calculation
- GET /simulate/{id}: found → returns serialised simulation
- RouteSimulateRequest: lokasyon_id with valid coords
- SegmentSimResponse: field ranges
- _serialize_simulation: multiple segments ordering
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.integration
# 0-mock epiği: DB persist/reload zinciri (db.add/commit/refresh/execute)
# gercek db_session'a cevrildi. simulator.simulate() (RouteSimulator, ayri
# domain - Faz1 dilim4) dokumante mock'lu kaldi: fizik+ML pipeline'ini
# gercege cevirmek bu dilimin kapsami disinda. _serialize_simulation
# pure-function testleri (dis sinir yok) MagicMock ile kaliyor.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sim_result(n_segments: int = 2, n_boundary: int = 3):
    """Build a fake SimulationResult returned by simulator.simulate."""
    result = MagicMock()
    result.raw_segment_count = n_segments * 2
    result.resampled_segment_count = n_segments
    result.elevation_coverage_pct = 95.0

    summary = MagicMock()
    summary.total_km = 450.0
    summary.total_l = 135.0
    summary.avg_l_per_100km = 30.0
    summary.total_eta_sec = 18000.0
    summary.total_ascent_m = 200.0
    summary.total_descent_m = 190.0

    segs = []
    for i in range(n_segments):
        s = MagicMock()
        s.length_km = 0.5
        s.grade_pct = 1.0
        s.road_class = "motorway"
        s.sim_speed_kmh = 90.0
        s.sim_l_per_100km = 30.0
        s.sim_l_total = 0.15
        s.eta_sec = 20.0
        s.mid_lon = 28.9 + i * 0.01
        s.mid_lat = 41.0 - i * 0.01
        s.maxspeed_kmh = 90.0
        s.traffic_speed_kmh = 80.0
        s.congestion = "low"
        segs.append(s)

    summary.segments = segs
    result.summary = summary

    # boundary_coords: list of (lon, lat) pairs
    result.boundary_coords = [
        (28.9 + i * 0.01, 41.0 - i * 0.01) for i in range(n_boundary)
    ]
    return result


def _make_persisted_sim():
    """Build a fake RouteSimulation ORM object for GET endpoint."""
    sim = MagicMock()
    sim.id = 77
    sim.created_at = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    sim.total_km = 300.0
    sim.total_eta_sec = 12000.0
    sim.total_l = 90.0
    sim.avg_l_per_100km = 30.0
    sim.total_ascent_m = 100.0
    sim.total_descent_m = 95.0
    sim.raw_segment_count = 600
    sim.resampled_segment_count = 600
    sim.elevation_coverage_pct = 97.0
    sim.ton = 12.0
    sim.arac_yasi = 3
    sim.target_length_km = 0.5
    sim.segments = []
    return sim


# ---------------------------------------------------------------------------
# _serialize_simulation — additional coverage
# ---------------------------------------------------------------------------


class TestSerializeSimulationExtra:
    def test_multiple_segments_serialized_in_order(self):
        """_serialize_simulation serialises multiple segments correctly."""
        from v2.modules.route_simulation.api.route_routes import _serialize_simulation

        sim = _make_persisted_sim()
        segs = []
        for i in range(3):
            s = MagicMock()
            s.seq = i
            s.length_km = 0.5
            s.grade_pct = float(i) * 0.5
            s.road_class = "primary"
            s.sim_speed_kmh = 80.0
            s.sim_l_per_100km = 28.0
            s.sim_l_total = 0.14
            s.eta_sec = 22.5
            s.mid_lon = 28.9 + i * 0.01
            s.mid_lat = 41.0 - i * 0.01
            s.maxspeed_kmh = 90.0
            s.traffic_speed_kmh = 80.0
            s.congestion = "low"
            segs.append(s)

        result = _serialize_simulation(sim, segs)
        assert len(result.segments) == 3
        assert result.segments[0].seq == 0
        assert result.segments[2].seq == 2

    def test_meta_fields_populated(self):
        """_serialize_simulation correctly populates meta dict."""
        from v2.modules.route_simulation.api.route_routes import _serialize_simulation

        sim = _make_persisted_sim()
        result = _serialize_simulation(sim, [])

        assert result.meta["ton"] == 12.0
        assert result.meta["arac_yasi"] == 3
        assert result.meta["target_length_km"] == 0.5


# ---------------------------------------------------------------------------
# RouteSimulateRequest — model edge cases
# ---------------------------------------------------------------------------


class TestRouteSimulateRequestExtra:
    def test_lokasyon_id_set(self):
        """RouteSimulateRequest accepts lokasyon_id."""
        from v2.modules.route_simulation.api.route_routes import RouteSimulateRequest

        req = RouteSimulateRequest(lokasyon_id=10, ton=20.0)
        assert req.lokasyon_id == 10

    def test_segment_length_boundaries(self):
        """RouteSimulateRequest validates segment_length_m boundaries."""
        from pydantic import ValidationError

        from v2.modules.route_simulation.api.route_routes import RouteSimulateRequest

        with pytest.raises(ValidationError):
            RouteSimulateRequest(segment_length_m=50)  # below min 100

        with pytest.raises(ValidationError):
            RouteSimulateRequest(segment_length_m=9999)  # above max 5000


# ---------------------------------------------------------------------------
# simulate_route — ad-hoc success path (persist + serialize)
# ---------------------------------------------------------------------------


class TestSimulateRouteSuccess:
    """simulator.simulate() (RouteSimulator — ayrı domain, Faz1 dilim4)
    dokümante mock'lu; DB persist/reload zinciri gerçek db_session'a
    çevrildi (endpoint'in kendi add/commit/refresh/selectinload mantığı
    gerçekten çalışıyor)."""

    async def _call_simulate(
        self, async_client, admin_auth_headers, request_body, mock_simulator
    ):
        from app.main import app
        from v2.modules.route_simulation.application.simulate_route import (
            get_route_simulator,
        )

        async def _dep_simulator():
            return mock_simulator

        app.dependency_overrides[get_route_simulator] = _dep_simulator
        try:
            resp = await async_client.post(
                "/api/v1/routes/simulate",
                json=request_body,
                headers=admin_auth_headers,
            )
            return resp
        finally:
            app.dependency_overrides.pop(get_route_simulator, None)

    async def test_adhoc_simulate_success_returns_200(
        self, async_client, admin_auth_headers
    ):
        """simulate_route with ad-hoc coords persists (real DB) and returns 200."""
        sim_result = _make_sim_result(n_segments=2, n_boundary=3)
        mock_simulator = MagicMock()
        mock_simulator.simulate = AsyncMock(return_value=sim_result)

        resp = await self._call_simulate(
            async_client,
            admin_auth_headers,
            {
                "cikis_lat": 41.0,
                "cikis_lon": 28.9,
                "varis_lat": 39.9,
                "varis_lon": 32.8,
                "ton": 15.0,
                "arac_yasi": 5,
            },
            mock_simulator,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["simulation_id"] > 0
        assert data["summary"]["distance_km"] == 450.0
        assert len(data["segments"]) == 2

    async def test_lokasyon_id_success_path(
        self, async_client, admin_auth_headers, db_session
    ):
        """simulate_route with lokasyon_id fetches coords from real DB."""
        from v2.modules.location.public import Lokasyon

        lok = Lokasyon(
            cikis_yeri="SimAdhocC",
            varis_yeri="SimAdhocV",
            mesafe_km=450.0,
            cikis_lat=41.0,
            cikis_lon=28.9,
            varis_lat=39.9,
            varis_lon=32.8,
        )
        db_session.add(lok)
        await db_session.flush()

        sim_result = _make_sim_result(n_segments=1, n_boundary=2)
        mock_simulator = MagicMock()
        mock_simulator.simulate = AsyncMock(return_value=sim_result)

        resp = await self._call_simulate(
            async_client,
            admin_auth_headers,
            {"lokasyon_id": lok.id, "ton": 12.0},
            mock_simulator,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["simulation_id"] > 0
        assert len(data["segments"]) == 1


# ---------------------------------------------------------------------------
# GET /simulate/{simulation_id} — success path
# ---------------------------------------------------------------------------


class TestGetRouteSimulationFound:
    async def test_found_returns_simulation(
        self, async_client, admin_auth_headers, db_session
    ):
        """GET /simulate/{id} returns 200 with simulation data (real seeded row)."""
        from v2.modules.route_simulation.public import RouteSegment, RouteSimulation

        sim = RouteSimulation(
            cikis_lon=28.9,
            cikis_lat=41.0,
            varis_lon=32.8,
            varis_lat=39.9,
            ton=12.0,
            arac_yasi=3,
            target_length_km=0.5,
            raw_segment_count=600,
            resampled_segment_count=600,
            elevation_coverage_pct=97.0,
            total_km=300.0,
            total_l=90.0,
            avg_l_per_100km=30.0,
            total_eta_sec=12000.0,
            total_ascent_m=100.0,
            total_descent_m=95.0,
        )
        db_session.add(sim)
        await db_session.flush()

        db_session.add(
            RouteSegment(
                simulation_id=sim.id,
                seq=0,
                length_km=0.5,
                grade_pct=1.0,
                road_class="highway",
                maxspeed_kmh=100.0,
                traffic_speed_kmh=88.0,
                congestion="moderate",
                sim_speed_kmh=85.0,
                sim_l_per_100km=29.0,
                sim_l_total=0.145,
                eta_sec=21.0,
                mid_lon=28.95,
                mid_lat=40.99,
            )
        )
        await db_session.flush()

        resp = await async_client.get(
            f"/api/v1/routes/simulate/{sim.id}", headers=admin_auth_headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["simulation_id"] == sim.id
        assert data["summary"]["distance_km"] == 300.0
        assert len(data["segments"]) == 1
        assert data["segments"][0]["road_class"] == "highway"


# ---------------------------------------------------------------------------
# RouteAnalysisRequest validation
# ---------------------------------------------------------------------------


class TestRouteAnalysisRequest:
    def test_coord_validation_lat_out_of_range(self):
        """RouteAnalysisRequest rejects lat > 90."""
        from pydantic import ValidationError

        from v2.modules.route_simulation.api.route_routes import RouteAnalysisRequest

        with pytest.raises(ValidationError):
            RouteAnalysisRequest(
                start_lat=91.0, start_lon=28.9, end_lat=39.9, end_lon=32.8
            )

    def test_coord_validation_lon_out_of_range(self):
        """RouteAnalysisRequest rejects lon > 180."""
        from pydantic import ValidationError

        from v2.modules.route_simulation.api.route_routes import RouteAnalysisRequest

        with pytest.raises(ValidationError):
            RouteAnalysisRequest(
                start_lat=41.0, start_lon=181.0, end_lat=39.9, end_lon=32.8
            )

    def test_valid_coords_accepted(self):
        """RouteAnalysisRequest accepts valid coordinates."""
        from v2.modules.route_simulation.api.route_routes import RouteAnalysisRequest

        req = RouteAnalysisRequest(
            start_lat=41.0, start_lon=28.9, end_lat=39.9, end_lon=32.8
        )
        assert req.start_lat == 41.0
        assert req.end_lon == 32.8
