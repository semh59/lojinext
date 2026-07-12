"""MapboxClient.get_segments Redis cache — Phase 2.3 unit tests.

Fake cache + monkey-patched _fetch_segments. Network'e çıkmadan cache
hit/miss/error path'lerini doğrular.

Plan §9 Phase 2: "Directions response cache (1-gün TTL — traffic değişir)".
"""

from __future__ import annotations

from typing import Any

from v2.modules.route_simulation.domain.segment_simulator import SegmentInput
from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient


class FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.get_calls = 0
        self.set_calls = 0
        self.last_ttl: float | None = None

    def get(self, key: str) -> Any:
        self.get_calls += 1
        return self.store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: float = 3600) -> None:
        self.set_calls += 1
        self.last_ttl = ttl_seconds
        self.store[key] = value


def _make_payload() -> tuple[list, list]:
    segs = [
        SegmentInput(
            length_km=0.5,
            grade_pct=0.0,
            road_class="motorway",
            maxspeed_kmh=130.0,
            traffic_speed_kmh=90.0,
            congestion="low",
        )
    ]
    coords = [(28.0, 41.0), (28.005, 41.0)]
    return segs, coords


def test_cache_key_uses_4_decimal_precision():
    key = MapboxClient._segments_cache_key(
        (28.978412, 41.008234), (32.859693, 39.933399)
    )
    assert key == "mb:dir:28.9784,41.0082:32.8597,39.9334"


def test_cache_key_differs_for_different_coords():
    a = MapboxClient._segments_cache_key((28.0, 41.0), (29.0, 40.0))
    b = MapboxClient._segments_cache_key((29.0, 40.0), (28.0, 41.0))  # ters
    c = MapboxClient._segments_cache_key((28.0, 41.0), (29.0, 41.0))
    assert a != b
    assert a != c
    assert b != c


async def test_cache_hit_skips_fetch(monkeypatch):
    cache = FakeCache()
    payload = _make_payload()
    cache.store["mb:dir:28.0000,41.0000:29.0000,40.0000"] = payload

    client = MapboxClient(cache=cache)

    async def _boom(*_a, **_kw):
        raise AssertionError("Cache hit'te _fetch_segments çağrılmamalı")

    monkeypatch.setattr(client, "_fetch_segments", _boom)

    result = await client.get_segments((28.0, 41.0), (29.0, 40.0))
    assert result == payload
    assert cache.get_calls == 1
    assert cache.set_calls == 0


async def test_cache_miss_calls_fetch_and_writes(monkeypatch):
    cache = FakeCache()
    payload = _make_payload()
    client = MapboxClient(cache=cache)

    fetch_calls = []

    async def _stub_fetch(start, end):
        fetch_calls.append((start, end))
        return payload

    monkeypatch.setattr(client, "_fetch_segments", _stub_fetch)

    result = await client.get_segments((28.0, 41.0), (29.0, 40.0))
    assert result == payload
    assert len(fetch_calls) == 1
    assert cache.set_calls == 1
    # 24h TTL
    assert cache.last_ttl == 24 * 3600
    assert cache.store["mb:dir:28.0000,41.0000:29.0000,40.0000"] == payload


async def test_fetch_returning_none_does_not_cache(monkeypatch):
    cache = FakeCache()
    client = MapboxClient(cache=cache)

    async def _stub_fetch(start, end):
        return None

    monkeypatch.setattr(client, "_fetch_segments", _stub_fetch)

    result = await client.get_segments((28.0, 41.0), (29.0, 40.0))
    assert result is None
    assert cache.set_calls == 0


async def test_cache_get_exception_falls_through_to_fetch(monkeypatch):
    """Redis get() patladığında fetch yine de çağrılmalı."""
    payload = _make_payload()
    client = MapboxClient(cache=FakeCache())

    class _BrokenGetCache:
        def get(self, key):
            raise RuntimeError("redis down")

        def set(self, *a, **k):
            pass

    client._cache = _BrokenGetCache()

    async def _stub_fetch(start, end):
        return payload

    monkeypatch.setattr(client, "_fetch_segments", _stub_fetch)

    result = await client.get_segments((28.0, 41.0), (29.0, 40.0))
    assert result == payload


async def test_cache_set_exception_does_not_break_response(monkeypatch):
    payload = _make_payload()

    class _BrokenSetCache:
        def get(self, key):
            return None

        def set(self, *a, **k):
            raise RuntimeError("redis down")

    client = MapboxClient(cache=_BrokenSetCache())

    async def _stub_fetch(start, end):
        return payload

    monkeypatch.setattr(client, "_fetch_segments", _stub_fetch)

    result = await client.get_segments((28.0, 41.0), (29.0, 40.0))
    assert result == payload  # Cache write fail eden case'de bile sonuç döner
