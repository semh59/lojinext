"""
Unit tests for OpenRouteClient — targeting ≥75% coverage.

0-mock epiği: HTTP çağrıları gerçek api_stub sunucusuna gider (Faz 0/1).
Belirli hata senaryoları (403/404/429/500/empty) sentinel koordinatlarla
seçilir — client'ın kendi params/body'si testin ekstra bir query param
eklemesine izin vermediği için (bkz. api_stub/main.py). DB-mocking
testleri (_get_from_cache/_save_to_cache) gerçek DB'ye (db_session) çevrildi.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import RouteProcessingError
from v2.modules.route_simulation.infrastructure.openroute_client import (
    OpenRouteClient,
    get_route_client,
)

pytestmark = pytest.mark.integration

_STUB_BASE_URL = "http://localhost:9000/v2"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(api_key: str = "test-key") -> OpenRouteClient:
    client = OpenRouteClient(api_key=api_key)
    client.base_url = _STUB_BASE_URL
    return client


def _make_breaker(delegate: bool = True):
    """Returns a MagicMock circuit breaker that delegates .call to the real fn."""
    breaker = MagicMock()
    if delegate:

        async def _delegate(func, *args, **kwargs):
            return await func(*args, **kwargs)

        breaker.call = AsyncMock(side_effect=_delegate)
    return breaker


def _make_api_response(status: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    if body is not None:
        resp.json.return_value = body
    resp.text = "error"
    return resp


# ---------------------------------------------------------------------------
# _validate_coordinates
# ---------------------------------------------------------------------------


def test_validate_coordinates_valid_turkey():
    client = _make_client()
    assert client._validate_coordinates((40.0, 29.0), (39.9, 32.8)) is True


def test_validate_coordinates_lat_out_of_range():
    client = _make_client()
    # lat < 35 (outside Turkey bounding box)
    assert client._validate_coordinates((10.0, 29.0), (39.9, 32.8)) is False


def test_validate_coordinates_lon_out_of_range():
    client = _make_client()
    # lon > 46 (outside Turkey bounding box)
    assert client._validate_coordinates((40.0, 50.0), (39.9, 32.8)) is False


def test_validate_coordinates_wrong_length():
    client = _make_client()
    assert client._validate_coordinates((40.0,), (39.9, 32.8)) is False  # type: ignore


def test_validate_coordinates_not_tuple():
    client = _make_client()
    assert client._validate_coordinates("bad", (39.9, 32.8)) is False  # type: ignore


# ---------------------------------------------------------------------------
# get_distance — validation failures
# ---------------------------------------------------------------------------


async def test_get_distance_invalid_coords_returns_none():
    client = _make_client()
    result = await client.get_distance((0.0, 0.0), (39.9, 32.8))
    assert result is None


async def test_get_distance_no_api_key_no_cache_returns_none():
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction

    with patch.object(
        client, "_get_from_cache", new_callable=AsyncMock, return_value=None
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=True)
    assert result is None


# ---------------------------------------------------------------------------
# get_distance — happy path via _call_api mock
# ---------------------------------------------------------------------------


async def test_get_distance_api_success_returns_source_api():
    client = _make_client()
    breaker = _make_breaker()

    api_result = {
        "distance_km": 452.3,
        "duration_hours": 5.5,
        "ascent_m": 1200,
        "descent_m": 1100,
    }

    # RouteValidator is imported lazily inside the method → patch at source module
    with (
        patch(
            "v2.modules.route_simulation.infrastructure.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=None
        ),
        patch.object(client, "_save_to_cache", new_callable=AsyncMock),
        patch.object(
            client, "_call_api", new_callable=AsyncMock, return_value=api_result
        ),
        patch(
            "app.core.services.route_validator.RouteValidator.validate_and_correct",
            side_effect=lambda x: x,
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=False)

    assert result is not None
    assert result["source"] == "api"
    assert result["distance_km"] == 452.3


async def test_get_distance_cache_hit_returns_source_cache():
    client = _make_client()
    cached = {
        "distance_km": 100.0,
        "duration_hours": 1.5,
        "ascent_m": 0,
        "descent_m": 0,
    }

    with (
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=cached
        ),
        patch(
            "app.core.services.route_validator.RouteValidator.validate_and_correct",
            side_effect=lambda x: x,
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=True)

    assert result is not None
    assert result["source"] == "cache"
    assert result["distance_km"] == 100.0


# ---------------------------------------------------------------------------
# get_distance — circuit breaker open
# ---------------------------------------------------------------------------


async def test_get_distance_circuit_breaker_open_returns_none():
    from app.infrastructure.resilience.circuit_breaker import CircuitBreakerError

    client = _make_client()
    breaker = MagicMock()
    breaker.call = AsyncMock(side_effect=CircuitBreakerError("open"))

    with (
        patch(
            "v2.modules.route_simulation.infrastructure.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(
            client, "_get_from_cache", new_callable=AsyncMock, return_value=None
        ),
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=False)

    assert result is None


# ---------------------------------------------------------------------------
# _call_api — HTTP status error codes
# ---------------------------------------------------------------------------


async def test_call_api_403_raises_route_processing_error():
    client = _make_client()
    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((0.0, 0.0), (0.0, 403.0))
    assert exc_info.value.provider_status == 403


async def test_call_api_404_raises_route_processing_error():
    client = _make_client()
    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((0.0, 0.0), (0.0, 404.0))
    assert exc_info.value.provider_status == 404


async def test_call_api_429_raises_route_processing_error():
    client = _make_client()
    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((0.0, 0.0), (0.0, 429.0))
    assert exc_info.value.provider_status == 429


async def test_call_api_500_raises_route_processing_error():
    client = _make_client()
    with pytest.raises(RouteProcessingError) as exc_info:
        await client._call_api((0.0, 0.0), (0.0, 500.0))
    assert exc_info.value.provider_status == 500


async def test_call_api_200_success_parses_result():
    client = _make_client()
    result = await client._call_api((40.0, 29.0), (39.9, 32.8), include_details=False)

    assert result is not None
    # api_stub'ın deterministik canned response'u.
    assert result["distance_km"] == pytest.approx(450.0, abs=0.1)
    assert result["duration_hours"] == pytest.approx(5.5, abs=0.1)
    assert result["ascent_m"] == 620.0
    assert result["descent_m"] == 580.0


async def test_call_api_200_with_geometry_polyline_string():
    """api_stub geometry'yi gerçek bir encoded polyline string olarak döner
    → gerçek PolylineDecoder çalışır (mock değil)."""
    client = _make_client()
    result = await client._call_api((40.0, 29.0), (39.9, 32.8), include_details=True)

    assert result is not None
    assert "details" in result


async def test_call_api_network_error_raises_route_processing_error():
    """Gerçek bağlantı hatası: kapalı bir porta işaret eder (mock değil)."""
    client = _make_client()
    client.base_url = "http://localhost:1/v2"
    with pytest.raises(RouteProcessingError):
        await client._call_api((40.0, 29.0), (39.9, 32.8))


async def test_call_api_timeout_raises_route_processing_error():
    """Gerçek timeout: sentinel senaryo (408) api_stub'ta 30s uyur —
    istemcinin kendi HTTP timeout'u (1s, burada override edilir) bundan
    önce tetiklenir, gerçek bir ReadTimeout üretir (mock değil)."""
    client = _make_client()
    client._client = httpx.AsyncClient(timeout=1.0)
    with pytest.raises(RouteProcessingError):
        await client._call_api((0.0, 0.0), (0.0, 408.0))


# ---------------------------------------------------------------------------
# get_route_client — singleton
# ---------------------------------------------------------------------------


async def test_get_route_client_returns_singleton():
    import v2.modules.route_simulation.infrastructure.openroute_client as mod

    # Reset singleton for clean test
    mod._client_instance = None

    with patch(
        "v2.modules.route_simulation.infrastructure.openroute_client.OpenRouteClient"
    ) as MockCls:
        instance = MagicMock()
        MockCls.return_value = instance

        c1 = await get_route_client()
        c2 = await get_route_client()

    assert c1 is c2
    MockCls.assert_called_once()

    # cleanup
    mod._client_instance = None


# ---------------------------------------------------------------------------
# db property (deprecated)
# ---------------------------------------------------------------------------


def test_db_property_returns_none():
    client = _make_client()
    assert client.db is None


# ---------------------------------------------------------------------------
# _call_api — lazy client creation
# ---------------------------------------------------------------------------


async def test_call_api_creates_httpx_client_if_none():
    """When _client is None, _call_api creates a REAL httpx.AsyncClient
    (0-mock epiği: gerçek stub'a bağlanır, mock class değil)."""
    client = _make_client()
    assert client._client is None

    result = await client._call_api((40.0, 29.0), (39.9, 32.8), include_details=False)

    assert result is not None
    assert isinstance(client._client, httpx.AsyncClient)


# ---------------------------------------------------------------------------
# get_distance — no api_key after cache miss (lines 117-118)
# ---------------------------------------------------------------------------


async def test_get_distance_no_api_key_after_cache_miss_returns_none():
    """api_key=None but use_cache=True and cache misses → None (line 117-118)."""
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction

    with patch.object(
        client, "_get_from_cache", new_callable=AsyncMock, return_value=None
    ):
        result = await client.get_distance((40.0, 29.0), (39.9, 32.8), use_cache=True)

    assert result is None


# ---------------------------------------------------------------------------
# _call_api — no api_key returns None early
# ---------------------------------------------------------------------------


async def test_call_api_no_api_key_returns_none():
    client = _make_client(api_key="dummy")
    client.api_key = None  # Force None after construction bypasses settings fallback
    result = await client._call_api((40.0, 29.0), (39.9, 32.8))
    assert result is None


# ---------------------------------------------------------------------------
# _call_api — geometry list path (already-decoded GeoJSON)
# ---------------------------------------------------------------------------


async def test_call_api_geometry_as_list():
    """geometry as a list (already decoded) should be used directly —
    api_stub'ın 777 sentinel senaryosu bu şekli döner (gerçek istemci
    kodu değişmeden çalışır)."""
    client = _make_client()
    result = await client._call_api((0.0, 0.0), (0.0, 777.0), include_details=True)

    assert result is not None
    assert "details" in result


# ---------------------------------------------------------------------------
# _call_api — polyline decode error (line 280-284)
# ---------------------------------------------------------------------------


async def test_call_api_polyline_decode_error_no_details():
    """If polyline decode raises, result still returns without details.

    DOKÜMANTE İSTİSNA (0-mock epiği): gerçek PolylineDecoder.decode() hiçbir
    girdi için exception fırlatmıyor (garbage string bile sessizce yanlış
    ama geçerli koordinatlara decode oluyor — doğrulandı) — bu yüzden bu
    savunmacı except-branch gerçek bir API yanıtıyla asla tetiklenemez.
    HTTP çağrısının kendisi gerçek stub'a gider; sadece decode() burada
    zorla raise ettirilir (gerçek istemci davranışı, yalnız erişilemez
    dal için hedefli patch)."""
    client = _make_client()

    with patch(
        "v2.modules.route_simulation.infrastructure.openroute_client.PolylineDecoder.decode",
        side_effect=Exception("bad polyline"),
    ):
        result = await client._call_api(
            (40.0, 29.0), (39.9, 32.8), include_details=True
        )

    assert result is not None
    assert "details" not in result  # no details when decode fails


# ---------------------------------------------------------------------------
# _get_from_cache (lines 341-391)
# ---------------------------------------------------------------------------


async def test_get_from_cache_returns_none_when_no_row(db_session):
    """0-mock epiği: gerçek DB'ye karşı, hiç satır yokken None döner."""
    client = _make_client()
    result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))
    assert result is None


async def test_get_from_cache_returns_dict_when_row_exists(db_session):
    """0-mock epiği: gerçek seed'li Lokasyon satırı bulunur → gerçek dict."""
    from app.tests._helpers.seed import seed_lokasyon

    await seed_lokasyon(
        db_session,
        cikis_lat=40.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
        api_mesafe_km=250.0,
        api_sure_saat=3.5,
        ascent_m=800,
        descent_m=750,
    )
    await db_session.commit()

    client = _make_client()
    result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is not None
    assert result["distance_km"] == 250.0
    assert result["duration_hours"] == 3.5


async def test_get_from_cache_includes_details_when_route_analysis_present(db_session):
    """0-mock epiği: route_analysis dolu bir satır → sonuçta details anahtarı."""
    from app.tests._helpers.seed import seed_lokasyon

    await seed_lokasyon(
        db_session,
        cikis_lat=40.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
        api_mesafe_km=200.0,
        api_sure_saat=2.0,
        route_analysis={"highway": {"flat": 100.0}},
    )
    await db_session.commit()

    client = _make_client()
    result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is not None
    assert "details" in result


async def test_get_from_cache_exception_returns_none():
    """DB execute raises → returns None gracefully.

    DOKÜMANTE İSTİSNA: gerçek bir DB hatasını (bağlantı kesintisi vb.)
    paylaşılan test session'ını bozmadan güvenle üretmek pratik değil —
    bu savunmacı except-branch (unexpected DB error → sessizce Redis
    fallback'e düş) hedefli bir mock ile test ediliyor."""
    client = _make_client()

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with (
        patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=AsyncCtx,
        ),
        patch(
            "app.infrastructure.cache.redis_pubsub.get_redis_val",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await client._get_from_cache((40.0, 29.0), (39.9, 32.8))

    assert result is None


# ---------------------------------------------------------------------------
# _save_to_cache (lines 400-453)
# ---------------------------------------------------------------------------


async def test_save_to_cache_updates_existing_row(db_session):
    """0-mock epiği: gerçek seed'li satır varken gerçek UPDATE çalışır."""
    from sqlalchemy import text

    from app.tests._helpers.seed import seed_lokasyon

    lokasyon = await seed_lokasyon(
        db_session,
        cikis_lat=40.0,
        cikis_lon=29.0,
        varis_lat=39.9,
        varis_lon=32.8,
    )
    await db_session.commit()

    client = _make_client()
    result_data = {
        "distance_km": 300.0,
        "duration_hours": 4.0,
        "ascent_m": 500,
        "descent_m": 450,
    }
    await client._save_to_cache((40.0, 29.0), (39.9, 32.8), result_data)

    row = (
        await db_session.execute(
            text("SELECT api_mesafe_km, api_sure_saat FROM lokasyonlar WHERE id = :id"),
            {"id": lokasyon.id},
        )
    ).fetchone()
    assert row.api_mesafe_km == 300.0
    assert row.api_sure_saat == 4.0


async def test_save_to_cache_no_existing_row_logs_debug(db_session):
    """0-mock epiği: eşleşen satır yokken gerçek DB'ye karşı sessizce no-op."""
    client = _make_client()
    result_data = {"distance_km": 300.0, "duration_hours": 4.0}
    # Should not raise, no matching row to update.
    await client._save_to_cache((40.0, 29.0), (39.9, 32.8), result_data)


async def test_save_to_cache_exception_does_not_raise():
    """Exception in DB → silently logged, no re-raise.

    DOKÜMANTE İSTİSNA: bkz. test_get_from_cache_exception_returns_none —
    gerçek bir DB hatasını paylaşılan test session'ını bozmadan üretmek
    pratik değil, hedefli mock ile test ediliyor."""
    client = _make_client()

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB error"))

    class AsyncCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *a):
            pass

    with patch(
        "app.database.connection.AsyncSessionLocal",
        side_effect=AsyncCtx,
    ):
        # Should not raise
        await client._save_to_cache((40.0, 29.0), (39.9, 32.8), {"distance_km": 100.0})
