"""
Coverage tests for app/core/services/openroute_service.py
Targets: offline fallback, geocode paths.

2026-07-22 dead-code denetimi: rota-profili hesaplama tarafının (RouteProfile,
get_route_profile/get_route_profile_offline, _haversine_distance, sync
is_configured(), close()) testleri buradan kaldırıldı — test ettikleri kod
silindi (sıfır prod çağıranı vardı, v2/modules/route_simulation'ın kendi
RouteSimulator/get_route_details pipeline'ı tarafından zaten ikame edilmişti).

0-mock epiği (Faz1 dilim5) notu: `geocode()`'un ağ yolu DAHA ÖNCE bilerek
mock'lu bırakılmadı — grep ile doğrulandı ki bu metod, `openroute_service.py`
dışında hiçbir gerçek prod kod yolundan çağrılmıyor (sadece bu test dosyası
ve `get_openroute_service()` singleton'ı kullanıyor; `lokasyon_service.py`
kendi `_geocode_with_openroute`'unu yazıp `openroute_service._get_client()`/
`base_url`'i ödünç alıyor, `.geocode()`'u DEĞİL). Gerçek prod'da kullanılan
yüzey (`is_configured_async`, `_get_client`, `base_url`, `geocode_url`,
`geocode_offline`) zaten mock'suz test ediliyor.
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
# Singleton
# ---------------------------------------------------------------------------


def test_get_openroute_service_singleton():
    from app.core.services.openroute_service import get_openroute_service

    s1 = get_openroute_service()
    s2 = get_openroute_service()
    assert s1 is s2
