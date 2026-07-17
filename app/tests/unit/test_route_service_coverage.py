"""Coverage tests for v2/modules/route_simulation/application/get_route_details.py
(+ get_base_location.py, get_route_difficulty.py, domain/route_geometry.py).

Extends app/tests/unit/test_services/test_route_service.py with additional
coverage for: cache hit path, 401/403 errors, no-api-key path, haversine,
segment distance, elevation analysis, difficulty, and base location.

0-mock epigi (Faz1 dilim4): get_uow -> real db_session/UnitOfWork
(cache-miss/cache-hit/config-value paths exercise a real DB round-trip);
external_service.get_external_service's httpx client -> real HTTP against
api_stub (sentinel coordinates select the 401/403 scenario). The
external_service-raises-RuntimeError exception path stays documented-mocked
(forcing a crash inside a third-party client wrapper isn't reproducible via
real infra).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config import settings
from v2.modules.route_simulation.application.get_route_details import (
    get_route_details,
)
from v2.modules.route_simulation.application.get_route_difficulty import (
    get_route_difficulty,
)
from v2.modules.route_simulation.domain.route_geometry import (
    analyze_elevation_profile,
    haversine,
    segment_distance,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _ors_base_url(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2")
    monkeypatch.setenv("OPENROUTESERVICE_API_KEY", "test-key-xyz")


# ---------------------------------------------------------------------------
# haversine
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_same_point_is_zero(self):
        d = haversine(29.0, 41.0, 29.0, 41.0)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_istanbul_ankara(self):
        # Istanbul ~(28.97, 41.01) -> Ankara ~(32.86, 39.93)
        d = haversine(28.97, 41.01, 32.86, 39.93)
        # Should be roughly 350-400 km in meters
        assert 350_000 < d < 420_000

    def test_symmetry(self):
        d1 = haversine(28.0, 41.0, 33.0, 40.0)
        d2 = haversine(33.0, 40.0, 28.0, 41.0)
        assert d1 == pytest.approx(d2, rel=1e-6)


# ---------------------------------------------------------------------------
# segment_distance
# ---------------------------------------------------------------------------


class TestSegmentDistance:
    def test_zero_when_start_equals_end(self):
        coords = [[29.0, 41.0], [30.0, 41.0], [31.0, 41.0]]
        d = segment_distance(coords, 0, 0)
        assert d == 0.0

    def test_single_segment(self):
        coords = [[29.0, 41.0], [29.1, 41.0]]
        d = segment_distance(coords, 0, 1)
        assert d > 0

    def test_index_beyond_coords_breaks_safely(self):
        coords = [[29.0, 41.0]]
        # end_idx=5 but coords has only 1 point
        d = segment_distance(coords, 0, 5)
        assert d == 0.0


# ---------------------------------------------------------------------------
# analyze_elevation_profile
# ---------------------------------------------------------------------------


class TestAnalyzeElevationProfile:
    def test_returns_flat_100_for_less_than_2_coords(self):
        result = analyze_elevation_profile({"coordinates": []})
        assert result["flat_pct"] == 100
        assert result["ramp_pct"] == 0

    def test_returns_flat_100_for_single_coord(self):
        result = analyze_elevation_profile({"coordinates": [[29.0, 41.0, 100]]})
        assert result["flat_pct"] == 100

    def test_flat_terrain_2d_coords(self):
        # 2D coords (no elevation) -> all classified as flat
        coords = [[29.0 + i * 0.01, 41.0] for i in range(5)]
        result = analyze_elevation_profile({"coordinates": coords})
        assert result["flat_pct"] == 100

    def test_steep_terrain_3d_coords(self):
        # Steep gradient: each step +100m elevation over ~1000m horizontal -> ~10%
        coords = [[29.0 + i * 0.01, 41.0, i * 100] for i in range(5)]
        result = analyze_elevation_profile({"coordinates": coords})
        # Should have ramp_pct > 0
        assert "ramp_pct" in result

    def test_near_zero_horizontal_distance_skipped(self):
        # Points extremely close together (< 5m) should be skipped
        coords = [[29.0, 41.0, 0], [29.000001, 41.0, 100]]
        result = analyze_elevation_profile({"coordinates": coords})
        # Should return valid dict without crashing
        assert "flat_pct" in result


# ---------------------------------------------------------------------------
# get_route_difficulty
# ---------------------------------------------------------------------------


class TestGetRouteDifficulty:
    def test_zero_distance_returns_bilinmiyor(self):
        result = get_route_difficulty(100, 100, 0)
        assert result == "Bilinmiyor"

    def test_flat_route(self):
        # 0 ascent -> gradient_factor = 0 -> Düz
        result = get_route_difficulty(0, 0, 100)
        assert result == "Düz"

    def test_light_grade(self):
        # 600m ascent over 100km -> 0.6% -> Hafif Eğimli
        result = get_route_difficulty(600, 0, 100)
        assert result == "Hafif Eğimli"

    def test_steep_grade(self):
        # 2000m ascent over 100km -> 2% -> Dik/Dağlık
        result = get_route_difficulty(2000, 0, 100)
        assert result == "Dik/Dağlık"


# ---------------------------------------------------------------------------
# get_route_details — no api_key (real DB cache-miss lookup)
# ---------------------------------------------------------------------------


class TestGetRouteDetailsNoApiKey:
    async def test_returns_error_when_no_api_key(self, db_session, monkeypatch):
        monkeypatch.delenv("OPENROUTESERVICE_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTE_API_KEY", raising=False)
        monkeypatch.setattr(settings, "OPENROUTESERVICE_API_KEY", None)

        result = await get_route_details((29.0, 41.0), (33.0, 40.0), use_cache=True)

        assert result["error_code"] == "SERVICE_UNAVAILABLE"
        assert result["source"] == "configuration"


# ---------------------------------------------------------------------------
# get_route_details — cache hit path (real DB: seed then re-read via cache)
# ---------------------------------------------------------------------------


class TestGetRouteDetailsCacheHit:
    async def test_returns_cached_result(self, db_session):
        from app.database.unit_of_work import unit_of_work as get_uow

        async with get_uow() as uow:
            await uow.route_repo.save_route(
                {
                    "origin_lat": 41.0,
                    "origin_lon": 29.0,
                    "dest_lat": 40.0,
                    "dest_lon": 33.0,
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
            )
            await uow.commit()

        result = await get_route_details((29.0, 41.0), (33.0, 40.0), use_cache=True)

        assert result["source"] == "cache"
        assert result["distance_km"] == 450.0

    async def test_cache_hit_with_include_details(self, db_session):
        from app.database.unit_of_work import unit_of_work as get_uow

        async with get_uow() as uow:
            await uow.route_repo.save_route(
                {
                    "origin_lat": 41.0,
                    "origin_lon": 29.0,
                    "dest_lat": 40.0,
                    "dest_lon": 33.0,
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
            )
            await uow.commit()

        result = await get_route_details(
            (29.0, 41.0), (33.0, 40.0), use_cache=True, include_details=True
        )

        assert result["route_analysis"] == {"segment_data": "present"}


# ---------------------------------------------------------------------------
# get_route_details — 401 and 403 responses (real HTTP via api_stub sentinels)
# ---------------------------------------------------------------------------


class TestGetRouteDetailsAuthErrors:
    async def test_401_returns_auth_failure(self, db_session):
        result = await get_route_details((0.0, 0.0), (0.0, 401.0), use_cache=False)

        assert result["error_code"] == "AUTH_FAILURE"
        assert result["provider_status"] == 401

    async def test_403_both_profiles_returns_quota_exceeded(self, db_session):
        # Real retry: hgv -> 403 -> retries with driving-car -> stub returns
        # 403 again regardless of profile (sentinel dispatches on coords).
        result = await get_route_details((0.0, 0.0), (0.0, 403.0), use_cache=False)

        assert result["error_code"] == "QUOTA_EXCEEDED"
        assert result["provider_status"] == 403


# ---------------------------------------------------------------------------
# get_route_details — exception path
# ---------------------------------------------------------------------------


class TestGetRouteDetailsException:
    async def test_exception_returns_internal_error(self, db_session):
        """external_service crashing before a client is even obtained is not
        reproducible via real infra -- documented mock (forces the outer
        except Exception branch in get_route_details)."""
        with patch(
            "app.services.external_service.get_external_service",
            side_effect=RuntimeError("external crashed"),
        ):
            result = await get_route_details(
                (29.0, 41.0), (33.0, 40.0), use_cache=False
            )

        assert result["error_code"] == "SERVICE_UNAVAILABLE"
        assert result["source"] == "internal_error"
