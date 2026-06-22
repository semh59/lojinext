"""OpenMeteoElevationClient — Phase 1.1 unit tests.

Mock cache + mock HTTP. Gerçek API'ye canlı smoke test ayrı (integration,
env-gated).

Invariant'lar:
- Boş input → boş output
- Full cache hit → HTTP çağrısı YOK
- Full cache miss → tek HTTP request, sonuçlar cache'e yazılır
- Karışık (yarı cache, yarı miss) → sadece miss'ler fetch
- Aynı koord birden fazla → tek API request, sonuçlar tekrar dağıtılır
- Coordinate precision: 4 decimal round
- API hatası → graceful, mevcut cache verisi korunur, miss'ler None
- Batch > 100 → chunk'lara böl
"""

from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.elevation.open_meteo_client import (
    OpenMeteoElevationClient,
)


class FakeCache:
    """In-memory cache stub uyumlu CacheManager interface'i (set/get)."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.get_calls = 0
        self.set_calls = 0

    def get(self, key: str) -> Any:
        self.get_calls += 1
        return self.store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: float = 3600) -> None:
        self.set_calls += 1
        self.store[key] = value


class FakeHttpResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class FakeAsyncClient:
    """httpx.AsyncClient stub. Bir veya birden fazla cevap kuyrukta."""

    def __init__(self, responses: list[FakeHttpResponse]):
        self._responses = list(responses)
        self.requests: list[dict] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def get(self, url: str, params: dict | None = None) -> FakeHttpResponse:
        self.requests.append({"url": url, "params": params})
        if not self._responses:
            raise RuntimeError("FakeAsyncClient: no more responses queued")
        return self._responses.pop(0)


@pytest.fixture
def fake_cache() -> FakeCache:
    return FakeCache()


@pytest.fixture
def client(fake_cache: FakeCache) -> OpenMeteoElevationClient:
    return OpenMeteoElevationClient(cache=fake_cache)


async def test_empty_input_returns_empty(client: OpenMeteoElevationClient):
    result = await client.get_elevations([])
    assert result == []


async def test_full_cache_hit_skips_http(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    fake_cache.store["elev:28.9784:41.0082"] = 36.0
    fake_cache.store["elev:32.8597:39.9334"] = 850.0

    # AsyncClient çağrılırsa test fail eder
    def _boom(*_a, **_kw):
        raise AssertionError("HTTP çağrılmamalıydı — full cache hit")

    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient", _boom
    )

    result = await client.get_elevations([(28.9784, 41.0082), (32.8597, 39.9334)])
    assert result == [36.0, 850.0]
    assert fake_cache.get_calls == 2
    assert fake_cache.set_calls == 0


async def test_full_cache_miss_fetches_and_caches(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    fake_http = FakeAsyncClient([FakeHttpResponse(200, {"elevation": [36.0, 850.0]})])
    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: fake_http,
    )

    result = await client.get_elevations([(28.9784, 41.0082), (32.8597, 39.9334)])
    assert result == [36.0, 850.0]
    assert len(fake_http.requests) == 1
    assert fake_cache.set_calls == 2
    assert fake_cache.store == {
        "elev:28.9784:41.0082": 36.0,
        "elev:32.8597:39.9334": 850.0,
    }


async def test_partial_cache_only_fetches_misses(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    # 3 koordinattan ilki cache'te
    fake_cache.store["elev:28.9784:41.0082"] = 36.0

    fake_http = FakeAsyncClient([FakeHttpResponse(200, {"elevation": [850.0, 5.0]})])
    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: fake_http,
    )

    result = await client.get_elevations(
        [(28.9784, 41.0082), (32.8597, 39.9334), (30.6320, 36.8550)]
    )
    assert result == [36.0, 850.0, 5.0]
    # Sadece 2 miss → 1 HTTP request, payload 2 koord
    assert len(fake_http.requests) == 1
    params = fake_http.requests[0]["params"]
    assert "32.8597" in params["longitude"]
    assert "30.632" in params["longitude"]
    assert "28.9784" not in params["longitude"]
    # Cache'e 2 set
    assert fake_cache.set_calls == 2


async def test_duplicate_coords_deduplicated_in_fetch(
    client: OpenMeteoElevationClient, monkeypatch
):
    fake_http = FakeAsyncClient([FakeHttpResponse(200, {"elevation": [36.0]})])
    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: fake_http,
    )

    # Aynı koord 3 kez
    result = await client.get_elevations(
        [(28.9784, 41.0082), (28.9784, 41.0082), (28.9784, 41.0082)]
    )
    # Tek HTTP request, tek koord payload
    assert len(fake_http.requests) == 1
    params = fake_http.requests[0]["params"]
    assert params["longitude"] == "28.9784"
    # Sonuç 3 slot dolu
    assert result == [36.0, 36.0, 36.0]


async def test_coordinate_precision_rounds_to_4_decimal(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    # (28.97843, 41.00821) → round 4 → (28.9784, 41.0082)
    fake_cache.store["elev:28.9784:41.0082"] = 36.0

    def _boom(*_a, **_kw):
        raise AssertionError("4 decimal round başarısız — cache miss")

    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient", _boom
    )

    result = await client.get_elevations([(28.97843, 41.00821)])
    assert result == [36.0]


async def test_api_error_returns_cached_only(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    fake_cache.store["elev:28.9784:41.0082"] = 36.0

    fake_http = FakeAsyncClient(
        [FakeHttpResponse(500, payload=None, text="server boom")]
    )
    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: fake_http,
    )

    result = await client.get_elevations([(28.9784, 41.0082), (32.8597, 39.9334)])
    # Cached olan korunur, miss olan None
    assert result == [36.0, None]
    # Hatalı fetch cache'e yazılmaz
    assert fake_cache.set_calls == 0


async def test_http_exception_returns_cached_only(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    fake_cache.store["elev:28.9784:41.0082"] = 36.0

    class ExplodingClient:
        async def __aenter__(self):
            raise RuntimeError("network down")

        async def __aexit__(self, *_):
            return None

    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: ExplodingClient(),
    )

    result = await client.get_elevations([(28.9784, 41.0082), (32.8597, 39.9334)])
    # Outer try/except: hepsi cache, miss'ler None
    assert result == [36.0, None]


async def test_large_batch_splits_into_chunks(
    client: OpenMeteoElevationClient, monkeypatch
):
    # 150 farklı koord — 100 + 50 chunk
    coords = [(28.0 + i * 0.001, 41.0) for i in range(150)]
    fake_http = FakeAsyncClient(
        [
            FakeHttpResponse(200, {"elevation": [float(i) for i in range(100)]}),
            FakeHttpResponse(200, {"elevation": [float(i + 100) for i in range(50)]}),
        ]
    )
    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: fake_http,
    )

    result = await client.get_elevations(coords)
    assert len(fake_http.requests) == 2
    assert len(result) == 150
    assert result[0] == 0.0
    assert result[99] == 99.0
    assert result[100] == 100.0
    assert result[149] == 149.0


async def test_null_elevations_in_response_are_preserved(
    client: OpenMeteoElevationClient, fake_cache: FakeCache, monkeypatch
):
    fake_http = FakeAsyncClient(
        [FakeHttpResponse(200, {"elevation": [36.0, None, 850.0]})]
    )
    monkeypatch.setattr(
        "app.infrastructure.elevation.open_meteo_client.httpx.AsyncClient",
        lambda *_a, **_kw: fake_http,
    )

    result = await client.get_elevations([(28.0, 41.0), (29.0, 40.0), (32.0, 39.0)])
    assert result == [36.0, None, 850.0]
    # None değerler cache'e yazılmaz
    assert fake_cache.set_calls == 2
