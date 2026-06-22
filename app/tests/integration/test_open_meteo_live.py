"""Open-Meteo elevation client — gerçek API canlı smoke (integration).

Bu test ağa çıkar (Open-Meteo /v1/elevation, ücretsiz public). CI/dev
ortamında ağ erişimi yoksa veya hız limit endişesi varsa atlanır.

Phase 0.2 referans değerleri (docs/.../_tilequery_elevation.md):
  Ankara Kızılay      883m
  İstanbul Sultanahmet 36m
  Erciyes              2238m
  Antalya Konyaaltı     0m
  Konya                1025m

±50m tolerans (relief sabit + SRTM precision).
"""

from __future__ import annotations

import os

import pytest

from app.infrastructure.elevation.open_meteo_client import OpenMeteoElevationClient

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_NETWORK_TESTS") != "1",
    reason="Canlı ağ test'i: RUN_LIVE_NETWORK_TESTS=1 set edilmedi",
)
async def test_live_open_meteo_returns_known_turkish_elevations():
    """Bypass cache by injecting a no-op stub."""

    class _NoopCache:
        def get(self, *_a, **_kw):
            return None

        def set(self, *_a, **_kw):
            return None

    client = OpenMeteoElevationClient(cache=_NoopCache())
    coords = [
        (32.8597, 39.9334),  # Ankara Kızılay → ~883
        (28.9784, 41.0082),  # Sultanahmet → ~36
        (35.5050, 38.5550),  # Erciyes → ~2238
        (30.6320, 36.8550),  # Antalya → ~0
        (32.4833, 37.8667),  # Konya → ~1025
    ]
    expected = [883, 36, 2238, 0, 1025]
    tol = 50

    result = await client.get_elevations(coords)

    assert all(r is not None for r in result), result
    assert len(result) == len(coords)
    for got, want in zip(result, expected):
        assert abs(got - want) <= tol, f"{got} m beklenen {want} ±{tol} dışında"
