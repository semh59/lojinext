"""WeatherService.get_route_weather_samples — Phase 4.1 unit tests.

Mock cache + mock ExternalService. Network'e çıkmadan batch + cache +
dedup + error fallback path'lerini doğrular.
"""

from __future__ import annotations

from typing import Any

from app.core.services.weather_service import WeatherSample, WeatherService


class FakeCache:
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


class FakeExternal:
    def __init__(self, response: dict):
        self._response = response
        self.calls: list = []

    async def get_weather_current_batch(self, coords):
        self.calls.append(list(coords))
        return self._response


def _patch_cache(monkeypatch, fake_cache: FakeCache):
    monkeypatch.setattr(
        "v2.modules.platform_infra.cache.cache_manager.get_cache_manager",
        lambda: fake_cache,
    )


def _sample_response(*temps_winds) -> dict:
    """Build Open-Meteo-shaped batch response from (temp, wind_speed) tuples."""
    items = []
    for temp, wind in temps_winds:
        items.append(
            {
                "current": {
                    "temperature_2m": temp,
                    "wind_speed_10m": wind,
                    "wind_direction_10m": 180.0,
                    "precipitation": 0.0,
                    "snowfall": 0.0,
                }
            }
        )
    return {"data": items}


async def test_empty_input_returns_empty():
    ws = WeatherService(external_service=FakeExternal({}))
    result = await ws.get_route_weather_samples([])
    assert result == []


async def test_full_cache_hit_skips_http(monkeypatch):
    fake_cache = FakeCache()
    fake_cache.store["weather:current:28.98:41.01"] = WeatherSample(
        temperature_2m=22.0, wind_speed_10m=10.0
    )
    _patch_cache(monkeypatch, fake_cache)

    class BoomExternal:
        async def get_weather_current_batch(self, coords):
            raise AssertionError("Cache hit'te HTTP çağrılmamalıydı")

    ws = WeatherService(external_service=BoomExternal())
    result = await ws.get_route_weather_samples([(28.978, 41.008)])
    assert len(result) == 1
    assert result[0].temperature_2m == 22.0
    assert fake_cache.set_calls == 0


async def test_full_cache_miss_fetches_and_caches(monkeypatch):
    fake_cache = FakeCache()
    _patch_cache(monkeypatch, fake_cache)

    fake_ext = FakeExternal(_sample_response((22.0, 10.0), (16.0, 15.0)))
    ws = WeatherService(external_service=fake_ext)

    result = await ws.get_route_weather_samples(
        [
            (28.978, 41.008),
            (32.86, 39.93),
        ]
    )

    assert len(result) == 2
    assert result[0].temperature_2m == 22.0
    assert result[1].temperature_2m == 16.0
    assert len(fake_ext.calls) == 1  # tek HTTP
    assert fake_cache.set_calls == 2


async def test_dedup_same_coord_yields_one_api_call(monkeypatch):
    fake_cache = FakeCache()
    _patch_cache(monkeypatch, fake_cache)

    fake_ext = FakeExternal(_sample_response((22.0, 10.0)))
    ws = WeatherService(external_service=fake_ext)

    # 3 aynı koord
    result = await ws.get_route_weather_samples(
        [
            (28.978, 41.008),
            (28.978, 41.008),
            (28.978, 41.008),
        ]
    )
    assert len(fake_ext.calls) == 1
    # Tek koord payload
    assert len(fake_ext.calls[0]) == 1
    # 3 slot da dolu
    assert all(s is not None for s in result)
    assert all(s.temperature_2m == 22.0 for s in result)


async def test_coord_precision_2_decimal(monkeypatch):
    """28.9789 → 28.98, cache hit beklenir."""
    fake_cache = FakeCache()
    fake_cache.store["weather:current:28.98:41.01"] = WeatherSample(temperature_2m=22.0)
    _patch_cache(monkeypatch, fake_cache)

    class BoomExternal:
        async def get_weather_current_batch(self, coords):
            raise AssertionError("precision 2 decimal cache hit failed")

    ws = WeatherService(external_service=BoomExternal())
    result = await ws.get_route_weather_samples([(28.9789, 41.0084)])
    assert result[0].temperature_2m == 22.0


async def test_provider_error_returns_cached_only(monkeypatch):
    fake_cache = FakeCache()
    fake_cache.store["weather:current:28.98:41.01"] = WeatherSample(temperature_2m=22.0)
    _patch_cache(monkeypatch, fake_cache)

    fake_ext = FakeExternal({"error": "down", "error_code": "SERVICE_UNAVAILABLE"})
    ws = WeatherService(external_service=fake_ext)

    result = await ws.get_route_weather_samples(
        [
            (28.978, 41.008),
            (32.86, 39.93),  # 1. cache hit, 2. miss
        ]
    )
    assert result[0].temperature_2m == 22.0  # cache
    assert result[1] is None  # provider fail
    assert fake_cache.set_calls == 0


async def test_partial_cache_only_fetches_misses(monkeypatch):
    fake_cache = FakeCache()
    fake_cache.store["weather:current:28.98:41.01"] = WeatherSample(temperature_2m=22.0)
    _patch_cache(monkeypatch, fake_cache)

    fake_ext = FakeExternal(_sample_response((16.0, 15.0), (5.0, 20.0)))
    ws = WeatherService(external_service=fake_ext)

    result = await ws.get_route_weather_samples(
        [
            (28.978, 41.008),  # cache hit
            (32.86, 39.93),  # miss
            (29.18, 40.08),  # miss
        ]
    )
    assert result[0].temperature_2m == 22.0
    assert result[1].temperature_2m == 16.0
    assert result[2].temperature_2m == 5.0
    # Tek API call, 2 koord payload (cache miss'ler için)
    assert len(fake_ext.calls) == 1
    assert len(fake_ext.calls[0]) == 2


async def test_cache_exception_falls_through_to_fetch(monkeypatch):
    """Redis down: cache.get() raise → fetch yine çalışır."""

    class BrokenCache:
        def get(self, key):
            raise RuntimeError("redis down")

        def set(self, *a, **k):
            pass

    monkeypatch.setattr(
        "v2.modules.platform_infra.cache.cache_manager.get_cache_manager",
        lambda: BrokenCache(),
    )

    fake_ext = FakeExternal(_sample_response((22.0, 10.0)))
    ws = WeatherService(external_service=fake_ext)
    result = await ws.get_route_weather_samples([(28.978, 41.008)])
    assert result[0].temperature_2m == 22.0


async def test_weather_sample_includes_wind_direction(monkeypatch):
    fake_cache = FakeCache()
    _patch_cache(monkeypatch, fake_cache)

    response = {
        "data": [
            {
                "current": {
                    "temperature_2m": 18.0,
                    "wind_speed_10m": 15.0,
                    "wind_direction_10m": 270.0,  # batıdan
                    "precipitation": 0.5,
                    "snowfall": 0.0,
                }
            }
        ]
    }
    fake_ext = FakeExternal(response)
    ws = WeatherService(external_service=fake_ext)

    result = await ws.get_route_weather_samples([(28.978, 41.008)])
    s = result[0]
    assert s.temperature_2m == 18.0
    assert s.wind_direction_10m == 270.0
    assert s.precipitation == 0.5
    assert s.snowfall == 0.0
