"""
MapboxClient coverage tests — HTTP mock, route fetch, road classification,
_classify_road_segments, _extract_speed_kmh, get_route, _fetch_segments.

Targets lines missed in: app/infrastructure/routing/mapbox_client.py
"""

from __future__ import annotations

from typing import Any

import pytest

from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient

pytestmark = pytest.mark.integration

_STUB_BASE_URL = "http://localhost:9000/directions/v5/mapbox/driving-traffic"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class FakeCache:
    def __init__(self):
        self.store: dict = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: Any, ttl_seconds: float = 3600):
        self.store[key] = value


def _make_client(api_key: str = "pk.test") -> MapboxClient:
    """Return a MapboxClient with a FakeCache, pointed at the real api_stub
    server (Faz 0) instead of the real Mapbox API."""
    client = MapboxClient.__new__(MapboxClient)
    client.api_key = api_key
    client.base_url = _STUB_BASE_URL
    client._cache = FakeCache()  # type: ignore[assignment]
    return client


def _make_client_no_key() -> MapboxClient:
    client = _make_client()
    client.api_key = None
    return client


def _minimal_route_json(
    distance_m: float = 50_000.0, duration_s: float = 1800.0
) -> dict:
    """Minimal Mapbox Directions API response."""
    return {
        "routes": [
            {
                "distance": distance_m,
                "duration": duration_s,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[28.0, 41.0], [32.0, 39.0]],
                },
                "legs": [
                    {
                        "distance": distance_m,
                        "duration": duration_s,
                        "annotation": {
                            "distance": [500.0, 500.0, 500.0],
                            "speed": [27.8, 22.2, 13.9],
                            "maxspeed": [
                                {"speed": 120, "unit": "km/h"},
                                {"speed": 90, "unit": "km/h"},
                                {"speed": 50, "unit": "km/h"},
                            ],
                            "congestion": ["low", "moderate", "heavy"],
                        },
                        "steps": [
                            {
                                "intersections": [
                                    {
                                        "geometry_index": 0,
                                        "mapbox_streets_v8": {"class": "motorway"},
                                    },
                                    {
                                        "geometry_index": 1,
                                        "mapbox_streets_v8": {"class": "primary"},
                                    },
                                    {
                                        "geometry_index": 2,
                                        "mapbox_streets_v8": {"class": "street"},
                                    },
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# _extract_speed_kmh — static method
# ---------------------------------------------------------------------------


class TestExtractSpeedKmh:
    def test_kmh_unit_returns_float(self):
        assert MapboxClient._extract_speed_kmh({"speed": 120, "unit": "km/h"}) == 120.0

    def test_mph_unit_converts(self):
        result = MapboxClient._extract_speed_kmh({"speed": 55, "unit": "mph"})
        assert result == pytest.approx(55 * 1.60934, rel=0.001)

    def test_unknown_flag_returns_none(self):
        assert MapboxClient._extract_speed_kmh({"unknown": True}) is None

    def test_none_flag_returns_none(self):
        assert MapboxClient._extract_speed_kmh({"none": True}) is None

    def test_missing_speed_key_returns_none(self):
        assert MapboxClient._extract_speed_kmh({"unit": "km/h"}) is None

    def test_non_dict_returns_none(self):
        assert MapboxClient._extract_speed_kmh(None) is None
        assert MapboxClient._extract_speed_kmh("130") is None

    def test_default_unit_is_kmh(self):
        result = MapboxClient._extract_speed_kmh({"speed": 90})
        assert result == 90.0


# ---------------------------------------------------------------------------
# _classify_road_segments
# ---------------------------------------------------------------------------


class TestClassifyRoadSegments:
    def _client(self):
        return _make_client()

    def test_no_legs_returns_full_city(self):
        route = {"distance": 10_000}
        res = self._client()._classify_road_segments(route)
        assert res["otoban_km"] == 0.0
        assert res["sehir_ici_km"] == pytest.approx(10.0, abs=0.01)

    def test_motorway_class_counted(self):
        route = {
            "legs": [
                {
                    "annotation": {
                        "distance": [1000.0, 1000.0],
                    },
                    "steps": [
                        {
                            "intersections": [
                                {
                                    "geometry_index": 0,
                                    "mapbox_streets_v8": {"class": "motorway"},
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        assert res["otoban_km"] >= 1.0

    def test_link_variant_counts_as_base(self):
        route = {
            "legs": [
                {
                    "annotation": {"distance": [500.0]},
                    "steps": [
                        {
                            "intersections": [
                                {
                                    "geometry_index": 0,
                                    "mapbox_streets_v8": {"class": "motorway_link"},
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        assert res["otoban_km"] == pytest.approx(0.5, abs=0.01)

    def test_trunk_primary_classes_in_otoban(self):
        route = {
            "legs": [
                {
                    "annotation": {"distance": [2000.0, 2000.0]},
                    "steps": [
                        {
                            "intersections": [
                                {
                                    "geometry_index": 0,
                                    "mapbox_streets_v8": {"class": "trunk"},
                                },
                                {
                                    "geometry_index": 1,
                                    "mapbox_streets_v8": {"class": "primary"},
                                },
                            ]
                        }
                    ],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        assert res["otoban_km"] == pytest.approx(4.0, abs=0.01)

    def test_street_residential_service_in_sehir(self):
        route = {
            "legs": [
                {
                    "annotation": {"distance": [300.0, 300.0, 300.0]},
                    "steps": [
                        {
                            "intersections": [
                                {
                                    "geometry_index": 0,
                                    "mapbox_streets_v8": {"class": "street"},
                                },
                                {
                                    "geometry_index": 1,
                                    "mapbox_streets_v8": {"class": "residential"},
                                },
                                {
                                    "geometry_index": 2,
                                    "mapbox_streets_v8": {"class": "service"},
                                },
                            ]
                        }
                    ],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        assert res["sehir_ici_km"] == pytest.approx(0.9, abs=0.01)

    def test_fallback_to_maxspeed_when_no_road_class(self):
        """Empty road class → maxspeed bucket fallback."""
        route = {
            "legs": [
                {
                    "annotation": {
                        "distance": [1000.0],
                        "maxspeed": [{"speed": 120, "unit": "km/h"}],
                    },
                    "steps": [],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        # 120 km/h >= 110 → motorway
        assert res["otoban_km"] == pytest.approx(1.0, abs=0.01)

    def test_fallback_maxspeed_80kmh_trunk(self):
        route = {
            "legs": [
                {
                    "annotation": {
                        "distance": [1000.0],
                        "maxspeed": [{"speed": 80, "unit": "km/h"}],
                    },
                    "steps": [],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        # 80 >= 80 → trunk → otoban_km
        assert res["otoban_km"] == pytest.approx(1.0, abs=0.01)

    def test_fallback_no_distances_uses_avg_speed(self):
        """Leg without annotation — fallback to avg speed from leg totals."""
        route = {
            "legs": [
                {
                    "distance": 10_000,
                    "duration": 100,  # 100 m/s → 360 km/h (unrealistic but tests path)
                    "annotation": {"distance": []},
                    "steps": [],
                }
            ]
        }
        res = self._client()._classify_road_segments(route)
        # avg_speed very high → motorway bucket
        assert res["otoban_km"] >= 5.0

    def test_ratios_sum_approx_one(self):
        client = self._client()
        route = _minimal_route_json()["routes"][0]
        res = client._classify_road_segments(route)
        ratios = res.get("ratios", {})
        total = sum(ratios.values())
        assert total == pytest.approx(1.0, abs=0.02)

    def test_detailed_dict_present(self):
        client = self._client()
        route = _minimal_route_json()["routes"][0]
        res = client._classify_road_segments(route)
        assert "detailed" in res
        assert "motorway" in res["detailed"]


# ---------------------------------------------------------------------------
# get_route — HTTP path
# ---------------------------------------------------------------------------


class TestGetRoute:
    """0-mock epiği: gerçek api_stub sunucusuna gider (Faz 0). Edge-case
    senaryolar sentinel koordinatlarla seçilir (gerçek istemci params'ı
    query'e ekstra alan eklemeye izin vermez, bu yüzden koordinatlar
    kendisi senaryo seçici — bkz. api_stub/main.py, aynı Stripe'ın test
    kart numaraları deseni)."""

    async def test_returns_none_when_no_api_key(self):
        client = _make_client_no_key()
        result = await client.get_route((28.0, 41.0), (32.0, 39.0))
        assert result is None

    async def test_returns_dict_on_success(self):
        client = _make_client()
        result = await client.get_route((28.0, 41.0), (32.0, 39.0))

        assert result is not None
        assert result["source"] == "mapbox"
        # api_stub'ın deterministik canned response'u: 450km.
        assert result["distance_km"] == pytest.approx(450.0, abs=0.1)

    async def test_returns_none_on_non_200_status(self):
        client = _make_client()
        result = await client.get_route((0.0, 0.0), (0.0, 401.0))
        assert result is None

    async def test_returns_none_when_no_routes_in_response(self):
        client = _make_client()
        result = await client.get_route((0.0, 0.0), (0.0, 200.0))
        assert result is None

    async def test_returns_none_on_exception(self):
        # Gerçek bağlantı hatası: kapalı bir porta işaret eder (mock değil).
        client = _make_client()
        client.base_url = "http://localhost:1/directions/v5/mapbox/driving-traffic"
        result = await client.get_route((28.0, 41.0), (32.0, 39.0))
        assert result is None

    async def test_route_analysis_included_in_result(self):
        client = _make_client()
        result = await client.get_route((28.0, 41.0), (32.0, 39.0))

        assert result is not None
        assert "geometry" in result
        assert "otoban_mesafe_km" in result
        assert "sehir_ici_mesafe_km" in result


# ---------------------------------------------------------------------------
# _fetch_segments — HTTP path (no cache)
# ---------------------------------------------------------------------------


class TestFetchSegments:
    """0-mock epiği: gerçek api_stub sunucusuna gider. 4xx yollarında
    with_async_retry gerçek retry mantığını çalıştırır ama hiç retry
    tetiklemez (kaynak kod: 4xx anında None döner, sadece 5xx/network
    hataları retry'ı tetikler) — bypass etmeye gerek yok."""

    async def test_returns_none_when_no_api_key(self):
        client = _make_client_no_key()
        result = await client._fetch_segments((28.0, 41.0), (32.0, 39.0))
        assert result is None

    async def test_returns_none_on_4xx(self):
        client = _make_client()
        result = await client._fetch_segments((0.0, 0.0), (0.0, 422.0))
        assert result is None

    async def test_returns_none_when_routes_empty(self):
        client = _make_client()
        result = await client._fetch_segments((0.0, 0.0), (0.0, 200.0))
        assert result is None

    async def test_returns_segments_and_coords_on_success(self):
        client = _make_client()
        result = await client._fetch_segments((28.0, 41.0), (32.0, 39.0))

        assert result is not None
        segs, coords = result
        # api_stub'ın canned response'u: annotation.distance 2 giriş, geometry 3 koordinat.
        assert len(segs) == 2
        assert len(coords) == 3

    async def test_returns_none_on_exception_from_retry(self):
        # Gerçek bağlantı hatası — 3 deneme gerçek backoff ile (kapalı port).
        client = _make_client()
        client.base_url = "http://localhost:1/directions/v5/mapbox/driving-traffic"
        result = await client._fetch_segments((28.0, 41.0), (32.0, 39.0))
        assert result is None
