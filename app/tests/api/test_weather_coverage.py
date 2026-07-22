"""Weather endpoint unit tests — v2/modules/route_simulation/api/weather_routes.py

Tests cover:
- POST /weather/forecast: success, service failure 503
- POST /weather/trip-impact: success, service failure 503
- GET /weather/dashboard-summary: no active trips, trips without guzergah_id,
  high risk, medium risk, normal, unavailable, exception result
- WeatherRequest/TripWeatherRequest/WeatherResponse model validation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_client():
    from httpx import AsyncClient
    from httpx._transports.asgi import ASGITransport

    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _override_deps(fake_user, weather_svc, sefer_svc=None, db_mock=None):
    """Return a context dict of dependency overrides."""
    from app.api.deps import get_current_active_user, get_sefer_service
    from v2.modules.platform_infra.database.connection import get_db
    from v2.modules.route_simulation.application.weather_service import (
        get_weather_service,
    )

    overrides = {}

    async def _fake_user():
        return fake_user

    overrides[get_current_active_user] = _fake_user

    async def _fake_weather():
        return weather_svc

    overrides[get_weather_service] = _fake_weather

    if sefer_svc is not None:

        async def _fake_sefer():
            return sefer_svc

        overrides[get_sefer_service] = _fake_sefer

    if db_mock is not None:

        async def _fake_db():
            yield db_mock

        overrides[get_db] = _fake_db

    return overrides


# ---------------------------------------------------------------------------
# POST /weather/forecast
# ---------------------------------------------------------------------------


class TestWeatherForecastEndpoint:
    async def test_success_returns_200(self):
        """POST /weather/forecast returns 200 on success."""
        from app.main import app

        fake_user = MagicMock()
        fake_user.id = 1

        weather_svc = MagicMock()
        weather_svc.get_forecast_analysis = AsyncMock(
            return_value={
                "success": True,
                "daily": [
                    {
                        "date": "2026-06-01",
                        "temperature_max": 25.0,
                        "precipitation_sum": 0.0,
                        "wind_speed_max": 10.0,
                        "impact_factor": 1.0,
                    }
                ],
                "fuel_impact_factor": 1.0,
                "recommendation": "Normal conditions",
            }
        )

        overrides = _override_deps(fake_user, weather_svc)
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.post(
                    "/api/v1/weather/forecast",
                    json={"lat": 41.0, "lon": 28.9},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["location"]["lat"] == 41.0
        finally:
            app.dependency_overrides.clear()

    async def test_service_failure_returns_503(self):
        """POST /weather/forecast returns 503 when service reports failure."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_forecast_analysis = AsyncMock(
            return_value={"success": False, "error": "Weather API down"}
        )

        overrides = _override_deps(fake_user, weather_svc)
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.post(
                    "/api/v1/weather/forecast",
                    json={"lat": 41.0, "lon": 28.9},
                )
            assert resp.status_code == 503
        finally:
            app.dependency_overrides.clear()

    async def test_service_failure_without_error_key_uses_default(self):
        """POST /weather/forecast uses default message when error key missing."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_forecast_analysis = AsyncMock(return_value={"success": False})

        overrides = _override_deps(fake_user, weather_svc)
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.post(
                    "/api/v1/weather/forecast",
                    json={"lat": 39.9, "lon": 32.8},
                )
            assert resp.status_code == 503
            body = resp.json()
            # detail may be nested under error.message or be a plain string
            detail = body.get("detail") or body.get("error", {}).get("message", "")
            assert detail is not None
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /weather/trip-impact
# ---------------------------------------------------------------------------


class TestTripImpactEndpoint:
    async def test_success_returns_200(self):
        """POST /weather/trip-impact returns 200 on success."""
        from app.main import app

        # Tier E madde 33: shape matches
        # WeatherService.get_trip_impact_analysis's real success return dict
        # — endpoint now has response_model=TripWeatherImpactResponse.
        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            return_value={
                "success": True,
                "weather_summary": {
                    "avg_temperature": 22.0,
                    "avg_precipitation": 0.0,
                    "avg_wind_speed": 20.0,
                },
                "fuel_impact_factor": 1.05,
                "fuel_impact_percent": 5.0,
                "conditions": ["Moderate wind impact"],
                "recommendation": "Moderate wind impact",
            }
        )

        overrides = _override_deps(fake_user, weather_svc)
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.post(
                    "/api/v1/weather/trip-impact",
                    json={
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                    },
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    async def test_service_failure_returns_503(self):
        """POST /weather/trip-impact returns 503 when service reports failure."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            return_value={"success": False, "error": "API error"}
        )

        overrides = _override_deps(fake_user, weather_svc)
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.post(
                    "/api/v1/weather/trip-impact",
                    json={
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                    },
                )
            assert resp.status_code == 503
        finally:
            app.dependency_overrides.clear()

    async def test_with_trip_date(self):
        """POST /weather/trip-impact accepts optional trip_date."""
        from app.main import app

        # Tier E madde 33: shape matches
        # WeatherService.get_trip_impact_analysis's real success return dict
        # — endpoint now has response_model=TripWeatherImpactResponse.
        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            return_value={
                "success": True,
                "weather_summary": {
                    "avg_temperature": 20.0,
                    "avg_precipitation": 0.0,
                    "avg_wind_speed": 10.0,
                },
                "fuel_impact_factor": 1.0,
                "fuel_impact_percent": 0.0,
                "conditions": [],
                "recommendation": "OK",
            }
        )

        overrides = _override_deps(fake_user, weather_svc)
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.post(
                    "/api/v1/weather/trip-impact",
                    json={
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                        "trip_date": "2026-06-01",
                    },
                )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /weather/dashboard-summary
# ---------------------------------------------------------------------------


class TestDashboardWeatherSummary:
    def _make_trip(self, trip_id=1, guzergah_id=None, plaka="34 TEST 001"):
        trip = MagicMock()
        trip.id = trip_id
        trip.guzergah_id = guzergah_id
        trip.plaka = plaka
        return trip

    async def test_no_active_trips_returns_empty_summary(self):
        """dashboard-summary with no active trips returns zero counts."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(return_value={"success": True})

        sefer_svc = MagicMock()
        sefer_svc.get_all_paged = AsyncMock(return_value={"items": []})

        overrides = _override_deps(
            fake_user, weather_svc, sefer_svc=sefer_svc, db_mock=AsyncMock()
        )
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/weather/dashboard-summary")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_active"] == 0
            assert data["high_risk"] == 0
        finally:
            app.dependency_overrides.clear()

    async def test_trip_without_guzergah_id_marked_unavailable(self):
        """Trips with no guzergah_id are counted as unavailable."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()

        trip = self._make_trip(trip_id=1, guzergah_id=None)
        sefer_svc = MagicMock()
        sefer_svc.get_all_paged = AsyncMock(return_value={"items": [trip]})

        overrides = _override_deps(
            fake_user, weather_svc, sefer_svc=sefer_svc, db_mock=AsyncMock()
        )
        app.dependency_overrides.update(overrides)
        try:
            async with _make_client() as client:
                resp = await client.get("/api/v1/weather/dashboard-summary")
            data = resp.json()
            assert data["total_active"] == 1
            assert data["unavailable"] == 1
        finally:
            app.dependency_overrides.clear()

    async def test_high_risk_trip_counted(self):
        """Trips with impact_factor > 1.10 are counted as high_risk."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            return_value={"success": True, "fuel_impact_factor": 1.15}
        )

        trip = self._make_trip(trip_id=2, guzergah_id=10)
        sefer_svc = MagicMock()
        sefer_svc.get_all_paged = AsyncMock(return_value={"items": [trip]})

        # Mock lokasyon repo with matching route
        # get_lokasyon_repo is imported inline inside the endpoint function;
        # patch it in its defining module.
        mock_db = AsyncMock()
        with patch("v2.modules.location.public.get_lokasyon_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_all = AsyncMock(
                return_value=[
                    {
                        "id": 10,
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                    }
                ]
            )
            mock_get_repo.return_value = mock_repo

            overrides = _override_deps(
                fake_user, weather_svc, sefer_svc=sefer_svc, db_mock=mock_db
            )
            app.dependency_overrides.update(overrides)
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/weather/dashboard-summary")
                data = resp.json()
                assert data["high_risk"] == 1
                assert len(data["details"]) == 1
            finally:
                app.dependency_overrides.clear()

    async def test_medium_risk_trip_counted(self):
        """Trips with 1.02 < impact_factor <= 1.10 counted as medium_risk."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            return_value={"success": True, "fuel_impact_factor": 1.05}
        )

        trip = self._make_trip(trip_id=3, guzergah_id=20)
        sefer_svc = MagicMock()
        sefer_svc.get_all_paged = AsyncMock(return_value={"items": [trip]})

        mock_db = AsyncMock()
        with patch("v2.modules.location.public.get_lokasyon_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_all = AsyncMock(
                return_value=[
                    {
                        "id": 20,
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                    }
                ]
            )
            mock_get_repo.return_value = mock_repo

            overrides = _override_deps(
                fake_user, weather_svc, sefer_svc=sefer_svc, db_mock=mock_db
            )
            app.dependency_overrides.update(overrides)
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/weather/dashboard-summary")
                data = resp.json()
                assert data["medium_risk"] == 1
                assert data["high_risk"] == 0
            finally:
                app.dependency_overrides.clear()

    async def test_normal_risk_trip_counted(self):
        """Trips with impact_factor <= 1.02 counted as normal."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            return_value={"success": True, "fuel_impact_factor": 1.00}
        )

        trip = self._make_trip(trip_id=4, guzergah_id=30)
        sefer_svc = MagicMock()
        sefer_svc.get_all_paged = AsyncMock(return_value={"items": [trip]})

        mock_db = AsyncMock()
        with patch("v2.modules.location.public.get_lokasyon_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_all = AsyncMock(
                return_value=[
                    {
                        "id": 30,
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                    }
                ]
            )
            mock_get_repo.return_value = mock_repo

            overrides = _override_deps(
                fake_user, weather_svc, sefer_svc=sefer_svc, db_mock=mock_db
            )
            app.dependency_overrides.update(overrides)
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/weather/dashboard-summary")
                data = resp.json()
                assert data["normal"] == 1
            finally:
                app.dependency_overrides.clear()

    async def test_exception_result_marked_unavailable(self):
        """Trips that raise an exception during analysis are marked unavailable."""
        from app.main import app

        fake_user = MagicMock()
        weather_svc = MagicMock()
        weather_svc.get_trip_impact_analysis = AsyncMock(
            side_effect=RuntimeError("Network error")
        )

        trip = self._make_trip(trip_id=5, guzergah_id=40)
        sefer_svc = MagicMock()
        sefer_svc.get_all_paged = AsyncMock(return_value={"items": [trip]})

        mock_db = AsyncMock()
        with patch("v2.modules.location.public.get_lokasyon_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_all = AsyncMock(
                return_value=[
                    {
                        "id": 40,
                        "cikis_lat": 41.0,
                        "cikis_lon": 28.9,
                        "varis_lat": 39.9,
                        "varis_lon": 32.8,
                    }
                ]
            )
            mock_get_repo.return_value = mock_repo

            overrides = _override_deps(
                fake_user, weather_svc, sefer_svc=sefer_svc, db_mock=mock_db
            )
            app.dependency_overrides.update(overrides)
            try:
                async with _make_client() as client:
                    resp = await client.get("/api/v1/weather/dashboard-summary")
                assert resp.status_code == 200
                data = resp.json()
                assert data["unavailable"] == 1
            finally:
                app.dependency_overrides.clear()
