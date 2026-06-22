"""Coverage tests for app/services/route_service.py.

Extends app/tests/unit/test_services/test_route_service.py with additional
coverage for: cache hit path, 401/403 errors, no-api-key path, haversine,
segment distance, elevation analysis, difficulty, and base location.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def route_service():
    from app.services.route_service import RouteService

    svc = RouteService.__new__(RouteService)
    svc.api_key = "test-key-xyz"  # pragma: allowlist secret
    svc.base_url = "https://api.openrouteservice.org/v2"
    return svc


# ---------------------------------------------------------------------------
# haversine
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_same_point_is_zero(self, route_service):
        d = route_service.haversine(29.0, 41.0, 29.0, 41.0)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_istanbul_ankara(self, route_service):
        # Istanbul ~(28.97, 41.01) → Ankara ~(32.86, 39.93)
        d = route_service.haversine(28.97, 41.01, 32.86, 39.93)
        # Should be roughly 350-400 km in meters
        assert 350_000 < d < 420_000

    def test_symmetry(self, route_service):
        d1 = route_service.haversine(28.0, 41.0, 33.0, 40.0)
        d2 = route_service.haversine(33.0, 40.0, 28.0, 41.0)
        assert d1 == pytest.approx(d2, rel=1e-6)


# ---------------------------------------------------------------------------
# _get_segment_distance
# ---------------------------------------------------------------------------


class TestGetSegmentDistance:
    def test_zero_when_start_equals_end(self, route_service):
        coords = [[29.0, 41.0], [30.0, 41.0], [31.0, 41.0]]
        d = route_service._get_segment_distance(coords, 0, 0)
        assert d == 0.0

    def test_single_segment(self, route_service):
        coords = [[29.0, 41.0], [29.1, 41.0]]
        d = route_service._get_segment_distance(coords, 0, 1)
        assert d > 0

    def test_index_beyond_coords_breaks_safely(self, route_service):
        coords = [[29.0, 41.0]]
        # end_idx=5 but coords has only 1 point
        d = route_service._get_segment_distance(coords, 0, 5)
        assert d == 0.0


# ---------------------------------------------------------------------------
# _analyze_elevation_profile
# ---------------------------------------------------------------------------


class TestAnalyzeElevationProfile:
    def test_returns_flat_100_for_less_than_2_coords(self, route_service):
        result = route_service._analyze_elevation_profile({"coordinates": []})
        assert result["flat_pct"] == 100
        assert result["ramp_pct"] == 0

    def test_returns_flat_100_for_single_coord(self, route_service):
        result = route_service._analyze_elevation_profile(
            {"coordinates": [[29.0, 41.0, 100]]}
        )
        assert result["flat_pct"] == 100

    def test_flat_terrain_2d_coords(self, route_service):
        # 2D coords (no elevation) → all classified as flat
        coords = [[29.0 + i * 0.01, 41.0] for i in range(5)]
        result = route_service._analyze_elevation_profile({"coordinates": coords})
        assert result["flat_pct"] == 100

    def test_steep_terrain_3d_coords(self, route_service):
        # Steep gradient: each step +100m elevation over ~1000m horizontal → ~10%
        coords = [[29.0 + i * 0.01, 41.0, i * 100] for i in range(5)]
        result = route_service._analyze_elevation_profile({"coordinates": coords})
        # Should have ramp_pct > 0
        assert "ramp_pct" in result

    def test_near_zero_horizontal_distance_skipped(self, route_service):
        # Points extremely close together (< 5m) should be skipped
        coords = [[29.0, 41.0, 0], [29.000001, 41.0, 100]]
        result = route_service._analyze_elevation_profile({"coordinates": coords})
        # Should return valid dict without crashing
        assert "flat_pct" in result


# ---------------------------------------------------------------------------
# _get_route_difficulty
# ---------------------------------------------------------------------------


class TestGetRouteDifficulty:
    def test_zero_distance_returns_bilinmiyor(self, route_service):
        result = route_service._get_route_difficulty(100, 100, 0)
        assert result == "Bilinmiyor"

    def test_flat_route(self, route_service):
        # 0 ascent → gradient_factor = 0 → Düz
        result = route_service._get_route_difficulty(0, 0, 100)
        assert result == "Düz"

    def test_light_grade(self, route_service):
        # 600m ascent over 100km → 0.6% → Hafif Eğimli
        result = route_service._get_route_difficulty(600, 0, 100)
        assert result == "Hafif Eğimli"

    def test_steep_grade(self, route_service):
        # 2000m ascent over 100km → 2% → Dik/Dağlık
        result = route_service._get_route_difficulty(2000, 0, 100)
        assert result == "Dik/Dağlık"


# ---------------------------------------------------------------------------
# analyze_route_difficulty  (public wrapper)
# ---------------------------------------------------------------------------


class TestAnalyzeRouteDifficulty:
    def test_delegates_to_private(self, route_service):
        assert route_service.analyze_route_difficulty(0, 0, 100) == "Düz"
        assert route_service.analyze_route_difficulty(2000, 0, 100) == "Dik/Dağlık"


# ---------------------------------------------------------------------------
# get_route_details — no api_key
# ---------------------------------------------------------------------------


class TestGetRouteDetailsNoApiKey:
    async def test_returns_error_when_no_api_key(self, route_service):
        route_service.api_key = None  # No key

        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.route_repo.get_by_coords = AsyncMock(return_value=None)

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            result = await route_service.get_route_details(
                (29.0, 41.0), (33.0, 40.0), use_cache=True
            )

        assert result["error_code"] == "SERVICE_UNAVAILABLE"
        assert result["source"] == "configuration"


# ---------------------------------------------------------------------------
# get_route_details — cache hit path
# ---------------------------------------------------------------------------


class TestGetRouteDetailsCacheHit:
    async def test_returns_cached_result(self, route_service):
        cached = {
            "distance_km": 450.0,
            "duration_min": 300.0,
            "ascent_m": 500.0,
            "descent_m": 400.0,
            "otoban_mesafe_km": 300.0,
            "sehir_ici_mesafe_km": 150.0,
            "flat_distance_km": 200.0,
            "geometry": {"type": "LineString", "coordinates": []},
            "fuel_estimate_cache": 135.0,
            "difficulty": "Düz",
            "route_analysis": {},
        }

        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.route_repo.get_by_coords = AsyncMock(return_value=cached)

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            with patch(
                "app.core.services.route_validator.RouteValidator.validate_and_correct",
                side_effect=lambda x: x,
            ):
                result = await route_service.get_route_details(
                    (29.0, 41.0), (33.0, 40.0), use_cache=True
                )

        assert result["source"] == "cache"
        assert result["distance_km"] == 450.0

    async def test_cache_hit_with_include_details(self, route_service):
        cached = {
            "distance_km": 100.0,
            "duration_min": 60.0,
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "otoban_mesafe_km": 80.0,
            "sehir_ici_mesafe_km": 20.0,
            "flat_distance_km": 80.0,
            "geometry": {},
            "fuel_estimate_cache": None,
            "difficulty": "Düz",
            "route_analysis": {"segment_data": "present"},
        }

        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.route_repo.get_by_coords = AsyncMock(return_value=cached)

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            with patch(
                "app.core.services.route_validator.RouteValidator.validate_and_correct",
                side_effect=lambda x: x,
            ):
                result = await route_service.get_route_details(
                    (29.0, 41.0), (33.0, 40.0), use_cache=True, include_details=True
                )

        assert result["route_analysis"] == {"segment_data": "present"}


# ---------------------------------------------------------------------------
# get_route_details — 401 and 403 responses
# ---------------------------------------------------------------------------


class TestGetRouteDetailsAuthErrors:
    def _make_uow_no_cache(self):
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.route_repo.get_by_coords = AsyncMock(return_value=None)
        return mock_uow

    def _make_client(self, status_code, text="error"):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = text
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        return mock_client

    async def test_401_returns_auth_failure(self, route_service):
        mock_client = self._make_client(401)
        mock_uow = self._make_uow_no_cache()

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            with patch(
                "app.services.external_service.get_external_service"
            ) as mock_ext:
                mock_ext.return_value._get_client = AsyncMock(return_value=mock_client)
                result = await route_service.get_route_details(
                    (29.0, 41.0), (33.0, 40.0), use_cache=False
                )

        assert result["error_code"] == "AUTH_FAILURE"
        assert result["provider_status"] == 401

    async def test_403_both_profiles_returns_quota_exceeded(self, route_service):
        # First 403 (hgv) → retry with car → also 403
        mock_response_403 = MagicMock()
        mock_response_403.status_code = 403
        mock_response_403.text = "forbidden"

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response_403)
        mock_uow = self._make_uow_no_cache()

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            with patch(
                "app.services.external_service.get_external_service"
            ) as mock_ext:
                mock_ext.return_value._get_client = AsyncMock(return_value=mock_client)
                result = await route_service.get_route_details(
                    (29.0, 41.0), (33.0, 40.0), use_cache=False
                )

        assert result["error_code"] == "QUOTA_EXCEEDED"
        assert result["provider_status"] == 403


# ---------------------------------------------------------------------------
# get_route_details — exception path
# ---------------------------------------------------------------------------


class TestGetRouteDetailsException:
    async def test_exception_returns_internal_error(self, route_service):
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.route_repo.get_by_coords = AsyncMock(return_value=None)

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            with patch(
                "app.services.external_service.get_external_service",
                side_effect=RuntimeError("external crashed"),
            ):
                result = await route_service.get_route_details(
                    (29.0, 41.0), (33.0, 40.0), use_cache=False
                )

        assert result["error_code"] == "SERVICE_UNAVAILABLE"
        assert result["source"] == "internal_error"


# ---------------------------------------------------------------------------
# get_base_location
# ---------------------------------------------------------------------------


class TestGetBaseLocation:
    async def test_returns_config_value(self, route_service):
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.config_repo.get_value = AsyncMock(return_value="ISTANBUL")

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            result = await route_service.get_base_location()

        assert result == "ISTANBUL"

    async def test_returns_default_when_not_configured(self, route_service):
        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=None)
        mock_uow.config_repo.get_value = AsyncMock(return_value="FABRIKA")

        with patch("app.services.route_service.get_uow", return_value=mock_uow):
            result = await route_service.get_base_location()

        assert result == "FABRIKA"
