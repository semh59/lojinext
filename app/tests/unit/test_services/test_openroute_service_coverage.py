"""
Coverage tests for app/core/services/openroute_service.py
Targets: haversine, offline fallback, geocode paths, circuit breaker / timeout handling.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_service(api_key="testkey123"):
    """Return an OpenRouteService instance with a controlled api_key."""
    from app.config import settings
    from app.core.services.openroute_service import OpenRouteService

    svc = OpenRouteService.__new__(OpenRouteService)
    svc.api_key = api_key
    svc.base_url = settings.OPENROUTE_API_BASE_URL
    # geocode_url is normally derived from base_url's origin in __init__
    # (see openroute_service.py) — __new__ bypasses that, so set it
    # explicitly (same pattern as OpenRouteClient's tests).
    svc.geocode_url = "https://api.openrouteservice.org/geocode/search"
    svc._client = None
    return svc


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


# ---------------------------------------------------------------------------
# RouteProfile dataclass
# ---------------------------------------------------------------------------


def test_route_profile_fields():
    from app.core.services.openroute_service import RouteProfile

    rp = RouteProfile(
        distance_km=100.0,
        duration_hours=1.5,
        ascent_m=300.0,
        descent_m=200.0,
        elevation_gain_ratio=0.6,
    )
    assert rp.distance_km == 100.0
    assert rp.elevation_gain_ratio == 0.6


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------


def test_is_configured_true_with_key():
    svc = _make_service("mykey")
    from app.core.services import openroute_service as mod

    orig = mod.HTTPX_AVAILABLE
    try:
        mod.HTTPX_AVAILABLE = True
        assert svc.is_configured() is True
    finally:
        mod.HTTPX_AVAILABLE = orig


def test_is_configured_false_without_key():
    svc = _make_service(api_key=None)
    svc.api_key = ""
    assert svc.is_configured() is False


def test_is_configured_false_when_httpx_unavailable():
    svc = _make_service("mykey")
    from app.core.services import openroute_service as mod

    orig = mod.HTTPX_AVAILABLE
    try:
        mod.HTTPX_AVAILABLE = False
        assert svc.is_configured() is False
    finally:
        mod.HTTPX_AVAILABLE = orig


# ---------------------------------------------------------------------------
# _haversine_distance
# ---------------------------------------------------------------------------


def test_haversine_same_point():
    svc = _make_service()
    d = svc._haversine_distance(28.0, 41.0, 28.0, 41.0)
    assert d == pytest.approx(0.0, abs=0.01)


def test_haversine_istanbul_ankara():
    svc = _make_service()
    # Istanbul (28.97, 41.01) → Ankara (32.86, 39.93) ≈ 352 km
    d = svc._haversine_distance(28.97, 41.01, 32.86, 39.93)
    assert 340 < d < 370


def test_haversine_returns_positive():
    svc = _make_service()
    d = svc._haversine_distance(27.0, 38.0, 30.0, 40.0)
    assert d > 0


# ---------------------------------------------------------------------------
# get_route_profile_offline
# ---------------------------------------------------------------------------


def test_offline_profile_adds_detour_factor():
    svc = _make_service()
    start = (28.97, 41.01)
    end = (32.86, 39.93)
    rp = svc.get_route_profile_offline(start, end)
    air = svc._haversine_distance(start[0], start[1], end[0], end[1])
    assert rp.distance_km == pytest.approx(air * 1.25, rel=0.01)


def test_offline_profile_speed_assumption():
    svc = _make_service()
    start = (28.0, 41.0)
    end = (32.0, 40.0)
    rp = svc.get_route_profile_offline(start, end)
    # duration = distance / 70
    expected_duration = rp.distance_km / 70.0
    assert rp.duration_hours == pytest.approx(expected_duration, rel=0.01)


def test_offline_profile_elevation_gain_ratio_fixed():
    svc = _make_service()
    rp = svc.get_route_profile_offline((28.0, 41.0), (32.0, 40.0))
    assert rp.elevation_gain_ratio == 0.53


# ---------------------------------------------------------------------------
# get_route_profile — not configured → offline fallback
# ---------------------------------------------------------------------------


async def test_get_route_profile_not_configured_falls_back_to_offline():
    svc = _make_service()
    svc.api_key = ""  # force is_configured() == False
    from app.core.services import openroute_service as mod

    orig = mod.HTTPX_AVAILABLE
    try:
        mod.HTTPX_AVAILABLE = True  # httpx available but no key
        svc.api_key = ""
        result = await svc.get_route_profile((28.97, 41.01), (32.86, 39.93))
    finally:
        mod.HTTPX_AVAILABLE = orig
    assert result is not None
    assert result.distance_km > 0


# ---------------------------------------------------------------------------
# get_route_profile — 200 OK success
# ---------------------------------------------------------------------------


async def test_get_route_profile_200_ok():
    svc = _make_service("validkey")
    response_data = {
        "routes": [
            {
                "summary": {
                    "distance": 450000,  # 450 km
                    "duration": 18000,  # 5 hours
                    "ascent": 1200,
                    "descent": 900,
                }
            }
        ]
    }

    mock_resp = _mock_response(200, response_data)

    # Mock the rate limiter and circuit breaker
    mock_rl = MagicMock()
    mock_rl.acquire = AsyncMock()
    mock_cb = MagicMock()
    mock_cb.call = AsyncMock(return_value=mock_resp)
    mock_client = MagicMock()

    with (
        patch(
            "app.core.services.openroute_service.RateLimiterRegistry.get_sync",
            return_value=mock_rl,
        ),
        patch(
            "app.core.services.openroute_service.CircuitBreakerRegistry.get_sync",
            return_value=mock_cb,
        ),
        patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)),
    ):
        result = await svc.get_route_profile((28.97, 41.01), (32.86, 39.93))

    assert result.distance_km == pytest.approx(450.0)
    assert result.duration_hours == pytest.approx(5.0)
    assert result.ascent_m == 1200
    assert result.elevation_gain_ratio == pytest.approx(1200 / 2100, rel=0.01)


# ---------------------------------------------------------------------------
# get_route_profile — non-200 → offline fallback
# ---------------------------------------------------------------------------


async def test_get_route_profile_non_200_falls_back():
    svc = _make_service("validkey")
    mock_rl = MagicMock()
    mock_rl.acquire = AsyncMock()
    mock_cb = MagicMock()
    mock_cb.call = AsyncMock(return_value=_mock_response(422, {}))
    mock_client = MagicMock()

    with (
        patch(
            "app.core.services.openroute_service.RateLimiterRegistry.get_sync",
            return_value=mock_rl,
        ),
        patch(
            "app.core.services.openroute_service.CircuitBreakerRegistry.get_sync",
            return_value=mock_cb,
        ),
        patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)),
    ):
        result = await svc.get_route_profile((28.97, 41.01), (32.86, 39.93))

    assert result is not None
    assert result.elevation_gain_ratio == 0.53  # offline indicator


# ---------------------------------------------------------------------------
# get_route_profile — timeout → offline fallback
# ---------------------------------------------------------------------------


async def test_get_route_profile_timeout_falls_back():
    import httpx

    svc = _make_service("validkey")
    mock_rl = MagicMock()
    mock_rl.acquire = AsyncMock()
    mock_cb = MagicMock()
    mock_cb.call = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client = MagicMock()

    with (
        patch(
            "app.core.services.openroute_service.RateLimiterRegistry.get_sync",
            return_value=mock_rl,
        ),
        patch(
            "app.core.services.openroute_service.CircuitBreakerRegistry.get_sync",
            return_value=mock_cb,
        ),
        patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)),
    ):
        result = await svc.get_route_profile((28.97, 41.01), (32.86, 39.93))

    assert result is not None
    assert result.elevation_gain_ratio == 0.53


# ---------------------------------------------------------------------------
# get_route_profile — circuit breaker open → offline fallback
# ---------------------------------------------------------------------------


async def test_get_route_profile_circuit_open_falls_back():
    from app.infrastructure.resilience.circuit_breaker import CircuitBreakerError

    svc = _make_service("validkey")
    mock_rl = MagicMock()
    mock_rl.acquire = AsyncMock()
    mock_cb = MagicMock()
    mock_cb.call = AsyncMock(side_effect=CircuitBreakerError("open"))
    mock_client = MagicMock()

    with (
        patch(
            "app.core.services.openroute_service.RateLimiterRegistry.get_sync",
            return_value=mock_rl,
        ),
        patch(
            "app.core.services.openroute_service.CircuitBreakerRegistry.get_sync",
            return_value=mock_cb,
        ),
        patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)),
    ):
        result = await svc.get_route_profile((28.97, 41.01), (32.86, 39.93))

    assert result is not None
    assert result.elevation_gain_ratio == 0.53


# ---------------------------------------------------------------------------
# get_route_profile — generic exception → offline fallback
# ---------------------------------------------------------------------------


async def test_get_route_profile_generic_exception_falls_back():
    svc = _make_service("validkey")
    mock_rl = MagicMock()
    mock_rl.acquire = AsyncMock()
    mock_cb = MagicMock()
    mock_cb.call = AsyncMock(side_effect=RuntimeError("network failure"))
    mock_client = MagicMock()

    with (
        patch(
            "app.core.services.openroute_service.RateLimiterRegistry.get_sync",
            return_value=mock_rl,
        ),
        patch(
            "app.core.services.openroute_service.CircuitBreakerRegistry.get_sync",
            return_value=mock_cb,
        ),
        patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)),
    ):
        result = await svc.get_route_profile((28.97, 41.01), (32.86, 39.93))

    assert result.elevation_gain_ratio == 0.53


# ---------------------------------------------------------------------------
# get_route_profile — zero total elevation → ratio 0.5
# ---------------------------------------------------------------------------


async def test_get_route_profile_zero_elevation_ratio():
    svc = _make_service("validkey")
    response_data = {
        "routes": [
            {
                "summary": {
                    "distance": 100000,
                    "duration": 3600,
                    "ascent": 0,
                    "descent": 0,
                }
            }
        ]
    }
    mock_rl = MagicMock()
    mock_rl.acquire = AsyncMock()
    mock_cb = MagicMock()
    mock_cb.call = AsyncMock(return_value=_mock_response(200, response_data))
    mock_client = MagicMock()

    with (
        patch(
            "app.core.services.openroute_service.RateLimiterRegistry.get_sync",
            return_value=mock_rl,
        ),
        patch(
            "app.core.services.openroute_service.CircuitBreakerRegistry.get_sync",
            return_value=mock_cb,
        ),
        patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)),
    ):
        result = await svc.get_route_profile((28.0, 41.0), (30.0, 40.0))

    assert result.elevation_gain_ratio == 0.5


# ---------------------------------------------------------------------------
# geocode — not configured → offline
# ---------------------------------------------------------------------------


async def test_geocode_not_configured_returns_offline():
    svc = _make_service()
    svc.api_key = ""
    result = await svc.geocode("Istanbul")
    # geocode_offline knows Istanbul
    assert result is not None
    assert isinstance(result[0], float)


# ---------------------------------------------------------------------------
# geocode — 200 OK with features
# ---------------------------------------------------------------------------


async def test_geocode_200_ok_returns_coords():
    svc = _make_service("validkey")
    geo_resp = _mock_response(
        200,
        {"features": [{"geometry": {"coordinates": [28.97, 41.01]}}]},
    )
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=geo_resp)

    with patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)):
        result = await svc.geocode("Istanbul")

    assert result == (28.97, 41.01)


def test_geocode_url_derived_from_base_url_origin():
    """Regresyon kanıtı: geocode_url artık base_url'in origin'inden türetiliyor
    (host root, /v2 altında değil) — bağımsız denetimde bulunan, daha önce
    openroute_client.py/lokasyon_service.py'de düzeltilmiş ama bu dosyada
    kaçırılmış aynı bug (f"{base_url}/geocode/search" hep /v2 altına
    ekleyip prod'da her zaman 404 dönüyordu)."""
    from app.core.services.openroute_service import OpenRouteService

    svc = OpenRouteService(api_key="test-key")

    assert svc.geocode_url == "https://api.openrouteservice.org/geocode/search"
    assert "/v2/geocode" not in svc.geocode_url


# ---------------------------------------------------------------------------
# geocode — 200 but empty features → offline
# ---------------------------------------------------------------------------


async def test_geocode_200_empty_features_offline_fallback():
    svc = _make_service("validkey")
    geo_resp = _mock_response(200, {"features": []})
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=geo_resp)

    with patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)):
        result = await svc.geocode("Bilinmeyen Şehir")

    # geocode_offline returns None for unknown city
    assert result is None


# ---------------------------------------------------------------------------
# geocode — non-200 → offline
# ---------------------------------------------------------------------------


async def test_geocode_non_200_falls_back():
    svc = _make_service("validkey")
    geo_resp = _mock_response(401, {})
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=geo_resp)

    with patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)):
        result = await svc.geocode("Ankara")

    # geocode_offline should handle Ankara
    assert result is not None


# ---------------------------------------------------------------------------
# geocode — timeout → offline
# ---------------------------------------------------------------------------


async def test_geocode_timeout_falls_back():
    import httpx

    svc = _make_service("validkey")
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with patch.object(svc, "_get_client", AsyncMock(return_value=mock_client)):
        result = await svc.geocode("Ankara")

    assert result is not None


# ---------------------------------------------------------------------------
# geocode_offline — known and unknown cities
# ---------------------------------------------------------------------------


def test_geocode_offline_known_cities():
    svc = _make_service()
    for city in ["istanbul", "ankara", "izmir", "bursa", "antalya", "gebze", "kocaeli"]:
        result = svc.geocode_offline(city)
        assert result is not None, f"{city} should be known"
        assert len(result) == 2


def test_geocode_offline_unknown_returns_none():
    svc = _make_service()
    result = svc.geocode_offline("Bilinmeyen Köy")
    assert result is None


def test_geocode_offline_case_insensitive():
    svc = _make_service()
    assert svc.geocode_offline("ISTANBUL") == svc.geocode_offline("istanbul")


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


async def test_close_clears_client():
    svc = _make_service()
    mock_client = MagicMock()
    mock_client.aclose = AsyncMock()
    svc._client = mock_client
    await svc.close()
    mock_client.aclose.assert_called_once()
    assert svc._client is None


async def test_close_noop_when_no_client():
    svc = _make_service()
    svc._client = None
    await svc.close()  # Should not raise


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_get_openroute_service_singleton():
    from app.core.services.openroute_service import get_openroute_service

    s1 = get_openroute_service()
    s2 = get_openroute_service()
    assert s1 is s2
