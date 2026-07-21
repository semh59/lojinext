"""Route endpoint unit tests — app/api/v1/endpoints/routes.py

Tests cover:
- POST /routes/analyze: success, routing provider error (503)
- POST /routes/simulate: missing coords 422, lokasyon_id not found 404,
  lokasyon_id missing coords 422, simulator returns None 502,
  ad-hoc success path
- GET /routes/simulate/{id}: not found 404, found returns simulation
- _serialize_simulation helper
- RouteSimulateRequest/SegmentSimResponse/SimulationSummaryResponse models
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration
# 0-mock epiği: Lokasyon lookup dallari (404/422) ve simulator-None (502)
# gercek DB + gercek RouteSimulator->api_stub zincirine cevrildi (sentinel
# koordinat teknigi). RouteService (analyze_route) ayri domain (route_service.py,
# Faz1 dilim4) - dokumante mock'lu kaldi. _serialize_simulation pure-function
# testleri (dis sinir yok, duck-typed girdi) MagicMock ile kaliyor.


# ---------------------------------------------------------------------------
# _serialize_simulation helper
# ---------------------------------------------------------------------------


class TestSerializeSimulation:
    def _make_sim(self):
        sim = MagicMock()
        sim.id = 1
        sim.created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        sim.total_km = 450.0
        sim.total_eta_sec = 18000.0
        sim.total_l = 135.0
        sim.avg_l_per_100km = 30.0
        sim.total_ascent_m = 200.0
        sim.total_descent_m = 190.0
        sim.raw_segment_count = 900
        sim.resampled_segment_count = 900
        sim.elevation_coverage_pct = 98.5
        sim.ton = 15.0
        sim.arac_yasi = 5
        sim.target_length_km = 0.5
        return sim

    def _make_segment(self, seq=0):
        s = MagicMock()
        s.seq = seq
        s.length_km = 0.5
        s.grade_pct = 1.2
        s.road_class = "motorway"
        s.sim_speed_kmh = 90.0
        s.sim_l_per_100km = 30.0
        s.sim_l_total = 0.15
        s.eta_sec = 20.0
        s.mid_lon = 28.95
        s.mid_lat = 40.99
        s.maxspeed_kmh = 90.0
        s.traffic_speed_kmh = 80.0
        s.congestion = "low"
        return s

    def test_serialize_simulation_basic(self):
        """_serialize_simulation converts ORM to response shape."""
        from v2.modules.route_simulation.api.route_routes import _serialize_simulation

        sim = self._make_sim()
        seg = self._make_segment(seq=0)
        result = _serialize_simulation(sim, [seg])

        assert result.simulation_id == 1
        assert result.summary.distance_km == 450.0
        assert result.summary.total_l == 135.0
        assert len(result.segments) == 1
        assert result.segments[0].road_class == "motorway"
        assert result.meta["ton"] == 15.0

    def test_serialize_simulation_empty_segments(self):
        """_serialize_simulation works with no segments."""
        from v2.modules.route_simulation.api.route_routes import _serialize_simulation

        sim = self._make_sim()
        result = _serialize_simulation(sim, [])
        assert result.segments == []

    def test_serialize_simulation_none_road_class(self):
        """_serialize_simulation converts None road_class to empty string."""
        from v2.modules.route_simulation.api.route_routes import _serialize_simulation

        sim = self._make_sim()
        seg = self._make_segment()
        seg.road_class = None
        result = _serialize_simulation(sim, [seg])
        assert result.segments[0].road_class == ""

    def test_serialize_duration_in_minutes(self):
        """duration_min is correctly computed from total_eta_sec / 60."""
        from v2.modules.route_simulation.api.route_routes import _serialize_simulation

        sim = self._make_sim()
        sim.total_eta_sec = 3600.0  # 1 hour
        result = _serialize_simulation(sim, [])
        assert result.summary.duration_min == 60.0


# ---------------------------------------------------------------------------
# Request/Response model validation
# ---------------------------------------------------------------------------


class TestRouteSimulateRequest:
    def test_defaults(self):
        """RouteSimulateRequest defaults are applied."""
        from v2.modules.route_simulation.api.route_routes import RouteSimulateRequest

        req = RouteSimulateRequest()
        assert req.ton == 15.0
        assert req.arac_yasi == 5
        assert req.segment_length_m == 500
        assert req.lokasyon_id is None

    def test_with_coords(self):
        """RouteSimulateRequest accepts optional coordinates."""
        from v2.modules.route_simulation.api.route_routes import RouteSimulateRequest

        req = RouteSimulateRequest(
            cikis_lat=41.0,
            cikis_lon=28.9,
            varis_lat=39.9,
            varis_lon=32.8,
        )
        assert req.cikis_lat == 41.0


# ---------------------------------------------------------------------------
# analyze_route endpoint
# ---------------------------------------------------------------------------


class TestAnalyzeRouteEndpoint:
    def _make_client(self):
        from httpx import AsyncClient
        from httpx._transports.asgi import ASGITransport

        from app.main import app

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def test_analyze_route_provider_error_returns_503(self):
        """analyze_route returns 503 when get_route_details reports error."""
        from app.api.deps import get_current_active_user
        from app.database.connection import get_db
        from app.main import app

        fake_user = MagicMock()
        fake_user.id = 1
        fake_user.aktif = True

        async def _fake_user():
            return fake_user

        async def _fake_db():
            yield AsyncMock()

        with (
            patch(
                "v2.modules.route_simulation.api.route_routes.get_route_details",
                new=AsyncMock(return_value={"error": "Provider unavailable"}),
            ),
            patch(
                "v2.modules.route_simulation.api.route_routes.get_route_difficulty",
                new=MagicMock(return_value="Normal"),
            ),
        ):
            app.dependency_overrides[get_current_active_user] = _fake_user
            app.dependency_overrides[get_db] = _fake_db
            try:
                async with self._make_client() as client:
                    resp = await client.post(
                        "/api/v1/routes/analyze",
                        json={
                            "start_lat": 41.0,
                            "start_lon": 28.9,
                            "end_lat": 39.9,
                            "end_lon": 32.8,
                        },
                    )
                assert resp.status_code == 503
            finally:
                app.dependency_overrides.clear()

    async def test_analyze_route_success_returns_200(self):
        """analyze_route returns 200 when get_route_details succeeds."""
        from app.api.deps import get_current_active_user
        from app.database.connection import get_db
        from app.main import app

        fake_user = MagicMock()
        fake_user.id = 1

        async def _fake_user():
            return fake_user

        async def _fake_db():
            yield AsyncMock()

        with (
            patch(
                "v2.modules.route_simulation.api.route_routes.get_route_details",
                new=AsyncMock(
                    return_value={
                        "distance_km": 450.0,
                        "duration_min": 300.0,
                        "ascent_m": 200.0,
                        "descent_m": 190.0,
                        "source": "mapbox",
                    }
                ),
            ),
            patch(
                "v2.modules.route_simulation.api.route_routes.get_route_difficulty",
                new=MagicMock(return_value="Normal"),
            ),
        ):
            app.dependency_overrides[get_current_active_user] = _fake_user
            app.dependency_overrides[get_db] = _fake_db
            try:
                async with self._make_client() as client:
                    resp = await client.post(
                        "/api/v1/routes/analyze",
                        json={
                            "start_lat": 41.0,
                            "start_lon": 28.9,
                            "end_lat": 39.9,
                            "end_lon": 32.8,
                        },
                    )
                assert resp.status_code == 200
                data = resp.json()
                assert data.get("difficulty") == "Normal"
            finally:
                app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# simulate_route endpoint — logic tests (unit, no DB writes)
# ---------------------------------------------------------------------------


class TestSimulateRouteLogic:
    """Test the coordinate-resolution logic without hitting real DB."""

    async def _call_simulate(self, request_body, db_mock, simulator_mock, fake_user):
        from httpx import AsyncClient
        from httpx._transports.asgi import ASGITransport

        from app.api.deps import get_current_active_user
        from app.database.connection import get_db
        from app.infrastructure.resilience.rate_limiter import RateLimiterDependency
        from app.main import app
        from v2.modules.route_simulation.application.simulate_route import (
            get_route_simulator,
        )

        async def _fake_user():
            return fake_user

        async def _fake_db():
            yield db_mock

        async def _fake_simulator():
            return simulator_mock

        # Bypass rate limiter
        async def _no_rate_limit():
            pass

        app.dependency_overrides[get_current_active_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db
        app.dependency_overrides[get_route_simulator] = _fake_simulator
        # Patch rate limiter as callable dependency
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

    async def test_missing_coords_no_lokasyon_id_returns_422(
        self, async_client, admin_auth_headers
    ):
        """simulate_route returns 422 when no lokasyon_id and coords missing
        (real DB, real RouteSimulator singleton — never reached before the
        validation error)."""
        resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={"ton": 15.0},  # no coords, no lokasyon_id
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422

    async def test_lokasyon_id_not_found_returns_404(
        self, async_client, admin_auth_headers
    ):
        """simulate_route returns 404 when lokasyon_id does not exist (real empty DB)."""
        resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={"lokasyon_id": 999999, "ton": 10.0},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 404

    async def test_lokasyon_id_missing_coords_returns_422(
        self, async_client, admin_auth_headers, db_session
    ):
        """simulate_route returns 422 when lokasyon has no lat/lon (real seeded row)."""
        from v2.modules.location.public import Lokasyon

        lok = Lokasyon(
            cikis_yeri="SimMissCoordsC",
            varis_yeri="SimMissCoordsV",
            mesafe_km=100.0,
        )
        db_session.add(lok)
        await db_session.flush()

        resp = await async_client.post(
            "/api/v1/routes/simulate",
            json={"lokasyon_id": lok.id, "ton": 10.0},
            headers=admin_auth_headers,
        )
        assert resp.status_code == 422

    async def test_simulator_returns_none_gives_502(
        self, async_client, admin_auth_headers, db_session, monkeypatch
    ):
        """simulate_route returns 502 when the real RouteSimulator's Mapbox
        call fails — sentinel koordinat (varis_lat=401.0) api_stub'ın gerçek
        401 dönmesini tetikler → get_segments None → simulate() None → 502.

        RouteSimulateRequest'in cikis/varis_lat alanları ge=-90/le=90
        Pydantic kısıtına sahip (401.0 doğrudan payload'da 422'ye düşer) —
        sentinel bu yüzden lokasyon_id yolundan geçiriliyor: Lokasyon.cikis_lat/
        varis_lat düz DB float kolonu, Pydantic kısıtı yok."""
        import v2.modules.route_simulation.application.simulate_route as sim_mod
        from app.config import settings
        from v2.modules.location.public import Lokasyon

        fake_key = MagicMock()
        fake_key.__bool__ = lambda self: True
        fake_key.get_secret_value = lambda: "fake_test_key"
        monkeypatch.setattr(settings, "MAPBOX_API_KEY", fake_key)
        monkeypatch.setattr(
            settings,
            "MAPBOX_API_BASE_URL",
            "http://localhost:9000/directions/v5/mapbox/driving-traffic",
        )

        lok = Lokasyon(
            cikis_yeri="Sim502C",
            varis_yeri="Sim502V",
            mesafe_km=100.0,
            cikis_lat=0.0,
            cikis_lon=0.0,
            varis_lat=401.0,
            varis_lon=0.0,
        )
        db_session.add(lok)
        await db_session.flush()

        # Modül-seviyesi singleton; ayarlar sadece construction anında
        # okunur — önce ve sonra sıfırlanmazsa başka testlerin gerçek
        # prod URL'e sahip MapboxClient'ı yeniden kullanılır.
        sim_mod._default_simulator = None
        try:
            resp = await async_client.post(
                "/api/v1/routes/simulate",
                json={"lokasyon_id": lok.id, "ton": 15.0},
                headers=admin_auth_headers,
            )
        finally:
            sim_mod._default_simulator = None
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# GET /simulate/{simulation_id}
# ---------------------------------------------------------------------------


class TestGetRouteSimulation:
    async def test_not_found_returns_404(self, async_client, admin_auth_headers):
        """GET /simulate/{id} returns 404 when simulation not found (real empty DB)."""
        resp = await async_client.get(
            "/api/v1/routes/simulate/999999", headers=admin_auth_headers
        )
        assert resp.status_code == 404
