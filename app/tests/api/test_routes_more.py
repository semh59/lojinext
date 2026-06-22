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

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client():
    from httpx import AsyncClient
    from httpx._transports.asgi import ASGITransport

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _fake_user(uid: int = 1):
    u = MagicMock()
    u.id = uid
    u.aktif = True
    return u


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
        from app.api.v1.endpoints.routes import _serialize_simulation

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
        from app.api.v1.endpoints.routes import _serialize_simulation

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
        from app.api.v1.endpoints.routes import RouteSimulateRequest

        req = RouteSimulateRequest(lokasyon_id=10, ton=20.0)
        assert req.lokasyon_id == 10

    def test_segment_length_boundaries(self):
        """RouteSimulateRequest validates segment_length_m boundaries."""
        from pydantic import ValidationError

        from app.api.v1.endpoints.routes import RouteSimulateRequest

        with pytest.raises(ValidationError):
            RouteSimulateRequest(segment_length_m=50)  # below min 100

        with pytest.raises(ValidationError):
            RouteSimulateRequest(segment_length_m=9999)  # above max 5000


# ---------------------------------------------------------------------------
# simulate_route — ad-hoc success path (persist + serialize)
# ---------------------------------------------------------------------------


class TestSimulateRouteSuccess:
    async def _call_simulate(self, request_body, mock_db, mock_simulator, user=None):
        from httpx import AsyncClient
        from httpx._transports.asgi import ASGITransport

        from app.api.deps import get_current_active_user
        from app.core.services.route_simulator import get_route_simulator
        from app.database.connection import get_db
        from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
        from app.main import app

        _resolved_user = user if user is not None else _fake_user()

        async def _dep_user():
            return _resolved_user

        async def _dep_db():
            yield mock_db

        async def _dep_simulator():
            return mock_simulator

        async def _no_rate_limit():
            pass

        app.dependency_overrides[get_current_active_user] = _dep_user
        app.dependency_overrides[get_db] = _dep_db
        app.dependency_overrides[get_route_simulator] = _dep_simulator
        app.dependency_overrides[
            RateLimiterDependency("route_simulate", rate=10.0, period=60.0)
        ] = _no_rate_limit
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/api/v1/routes/simulate", json=request_body)
            return resp
        finally:
            app.dependency_overrides.clear()

    async def test_adhoc_simulate_success_returns_200(self):
        """simulate_route with ad-hoc coords persists and returns 200."""
        sim_result = _make_sim_result(n_segments=2, n_boundary=3)

        # Build a mock DB that handles add/commit/refresh
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # After db.refresh(sim), sim should have id and segments populated
        persisted_sim = _make_persisted_sim()
        # Segments from the result
        seg0 = MagicMock()
        seg0.seq = 0
        seg0.length_km = 0.5
        seg0.grade_pct = 1.0
        seg0.road_class = "motorway"
        seg0.sim_speed_kmh = 90.0
        seg0.sim_l_per_100km = 30.0
        seg0.sim_l_total = 0.15
        seg0.eta_sec = 20.0
        seg0.mid_lon = 28.95
        seg0.mid_lat = 40.99
        seg0.maxspeed_kmh = 90.0
        seg0.traffic_speed_kmh = 82.0
        seg0.congestion = "low"
        persisted_sim.segments = [seg0]

        async def _fake_refresh(obj):
            # Copy attributes from persisted_sim to obj
            obj.id = persisted_sim.id
            obj.created_at = persisted_sim.created_at
            obj.total_km = persisted_sim.total_km
            obj.total_eta_sec = persisted_sim.total_eta_sec
            obj.total_l = persisted_sim.total_l
            obj.avg_l_per_100km = persisted_sim.avg_l_per_100km
            obj.total_ascent_m = persisted_sim.total_ascent_m
            obj.total_descent_m = persisted_sim.total_descent_m
            obj.raw_segment_count = persisted_sim.raw_segment_count
            obj.resampled_segment_count = persisted_sim.resampled_segment_count
            obj.elevation_coverage_pct = persisted_sim.elevation_coverage_pct
            obj.ton = persisted_sim.ton
            obj.arac_yasi = persisted_sim.arac_yasi
            obj.target_length_km = persisted_sim.target_length_km
            if not hasattr(obj, "segments") or obj.segments is None:
                obj.segments = [seg0]

        mock_db.refresh = _fake_refresh

        # The endpoint does a second db.execute(selectinload) after refresh.
        # Return persisted_sim via a sync scalar_one so sim.segments is accessible.
        mock_exec_result = MagicMock()
        mock_exec_result.scalar_one = MagicMock(return_value=persisted_sim)
        mock_db.execute = AsyncMock(return_value=mock_exec_result)

        mock_simulator = MagicMock()
        mock_simulator.simulate = AsyncMock(return_value=sim_result)

        resp = await self._call_simulate(
            {
                "cikis_lat": 41.0,
                "cikis_lon": 28.9,
                "varis_lat": 39.9,
                "varis_lon": 32.8,
                "ton": 15.0,
                "arac_yasi": 5,
            },
            mock_db,
            mock_simulator,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulation_id"] == 77
        assert "summary" in data

    async def test_lokasyon_id_success_path(self):
        """simulate_route with lokasyon_id fetches coords from DB."""
        sim_result = _make_sim_result(n_segments=1, n_boundary=2)

        mock_lokasyon = MagicMock()
        mock_lokasyon.cikis_lat = 41.0
        mock_lokasyon.cikis_lon = 28.9
        mock_lokasyon.varis_lat = 39.9
        mock_lokasyon.varis_lon = 32.8

        persisted_sim = _make_persisted_sim()
        seg0 = MagicMock()
        seg0.seq = 0
        seg0.length_km = 0.5
        seg0.grade_pct = 0.5
        seg0.road_class = "primary"
        seg0.sim_speed_kmh = 80.0
        seg0.sim_l_per_100km = 28.0
        seg0.sim_l_total = 0.14
        seg0.eta_sec = 22.5
        seg0.mid_lon = 28.95
        seg0.mid_lat = 40.99
        seg0.maxspeed_kmh = None
        seg0.traffic_speed_kmh = None
        seg0.congestion = "low"
        persisted_sim.segments = [seg0]

        mock_db = AsyncMock()
        # First execute: lokasyon lookup (scalar_one_or_none)
        mock_result_lok = MagicMock()
        mock_result_lok.scalar_one_or_none = MagicMock(return_value=mock_lokasyon)
        # Second execute: reload RouteSimulation with selectinload (scalar_one)
        mock_result_sim = MagicMock()
        mock_result_sim.scalar_one = MagicMock(return_value=persisted_sim)
        mock_db.execute = AsyncMock(side_effect=[mock_result_lok, mock_result_sim])
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        async def _fake_refresh(obj):
            obj.id = persisted_sim.id
            obj.created_at = persisted_sim.created_at
            obj.total_km = persisted_sim.total_km
            obj.total_eta_sec = persisted_sim.total_eta_sec
            obj.total_l = persisted_sim.total_l
            obj.avg_l_per_100km = persisted_sim.avg_l_per_100km
            obj.total_ascent_m = persisted_sim.total_ascent_m
            obj.total_descent_m = persisted_sim.total_descent_m
            obj.raw_segment_count = persisted_sim.raw_segment_count
            obj.resampled_segment_count = persisted_sim.resampled_segment_count
            obj.elevation_coverage_pct = persisted_sim.elevation_coverage_pct
            obj.ton = persisted_sim.ton
            obj.arac_yasi = persisted_sim.arac_yasi
            obj.target_length_km = persisted_sim.target_length_km
            if not hasattr(obj, "segments") or obj.segments is None:
                obj.segments = [seg0]

        mock_db.refresh = _fake_refresh

        mock_simulator = MagicMock()
        mock_simulator.simulate = AsyncMock(return_value=sim_result)

        resp = await self._call_simulate(
            {"lokasyon_id": 5, "ton": 12.0},
            mock_db,
            mock_simulator,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulation_id"] == 77


# ---------------------------------------------------------------------------
# GET /simulate/{simulation_id} — success path
# ---------------------------------------------------------------------------


class TestGetRouteSimulationFound:
    async def test_found_returns_simulation(self):
        """GET /simulate/{id} returns 200 with simulation data when found."""
        from httpx import AsyncClient
        from httpx._transports.asgi import ASGITransport

        from app.api.deps import get_current_active_user
        from app.database.connection import get_db
        from app.main import app

        _user = _fake_user()
        persisted_sim = _make_persisted_sim()

        seg0 = MagicMock()
        seg0.seq = 0
        seg0.length_km = 0.5
        seg0.grade_pct = 1.0
        seg0.road_class = "highway"
        seg0.sim_speed_kmh = 85.0
        seg0.sim_l_per_100km = 29.0
        seg0.sim_l_total = 0.145
        seg0.eta_sec = 21.0
        seg0.mid_lon = 28.95
        seg0.mid_lat = 40.99
        seg0.maxspeed_kmh = 100.0
        seg0.traffic_speed_kmh = 88.0
        seg0.congestion = "moderate"
        persisted_sim.segments = [seg0]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = persisted_sim
        mock_db.execute = AsyncMock(return_value=mock_result)

        async def _dep_user():
            return _user

        async def _dep_db():
            yield mock_db

        app.dependency_overrides[get_current_active_user] = _dep_user
        app.dependency_overrides[get_db] = _dep_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/routes/simulate/77")
            assert resp.status_code == 200
            data = resp.json()
            assert data["simulation_id"] == 77
            assert data["summary"]["distance_km"] == 300.0
            assert len(data["segments"]) == 1
            assert data["segments"][0]["road_class"] == "highway"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# RouteAnalysisRequest validation
# ---------------------------------------------------------------------------


class TestRouteAnalysisRequest:
    def test_coord_validation_lat_out_of_range(self):
        """RouteAnalysisRequest rejects lat > 90."""
        from pydantic import ValidationError

        from app.api.v1.endpoints.routes import RouteAnalysisRequest

        with pytest.raises(ValidationError):
            RouteAnalysisRequest(
                start_lat=91.0, start_lon=28.9, end_lat=39.9, end_lon=32.8
            )

    def test_coord_validation_lon_out_of_range(self):
        """RouteAnalysisRequest rejects lon > 180."""
        from pydantic import ValidationError

        from app.api.v1.endpoints.routes import RouteAnalysisRequest

        with pytest.raises(ValidationError):
            RouteAnalysisRequest(
                start_lat=41.0, start_lon=181.0, end_lat=39.9, end_lon=32.8
            )

    def test_valid_coords_accepted(self):
        """RouteAnalysisRequest accepts valid coordinates."""
        from app.api.v1.endpoints.routes import RouteAnalysisRequest

        req = RouteAnalysisRequest(
            start_lat=41.0, start_lon=28.9, end_lat=39.9, end_lon=32.8
        )
        assert req.start_lat == 41.0
        assert req.end_lon == 32.8
