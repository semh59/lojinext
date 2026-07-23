"""MobilizAVLProvider against the real api_stub server (0-mock epiği —
gerçek HTTP, in-process mock değil). Requires
`docker compose --profile test up -d api-stub` (localhost:9000).

Bu adapter'ın request/response şekli gerçek Mobiliz sözleşmesiyle
DOĞRULANMAMIŞ — bkz. mobiliz.py'nin modül docstring'i. Bu testler
adapter'ın kendi (stub'a karşı) davranışını kanıtlar, gerçek Mobiliz
uyumunu değil."""

from datetime import datetime, timezone

import httpx
import pytest

from v2.modules.admin_platform.infrastructure.integrations.avl.mobiliz import (
    MobilizAVLProvider,
)

pytestmark = pytest.mark.unit

STUB_URL = "http://localhost:9000"


def _reachable() -> bool:
    try:
        httpx.get(f"{STUB_URL}/health", timeout=2.0)
        return True
    except httpx.RequestError:
        return False


skip_if_unreachable = pytest.mark.skipif(
    not _reachable(), reason="api-stub (localhost:9000) erişilemez"
)


@pytest.fixture
def provider():
    return MobilizAVLProvider(base_url=STUB_URL, api_key="test-key", account_id="acc-1")


def test_constructor_requires_all_fields():
    with pytest.raises(ValueError):
        MobilizAVLProvider(base_url="", api_key="k", account_id="a")
    with pytest.raises(ValueError):
        MobilizAVLProvider(base_url=STUB_URL, api_key="", account_id="a")
    with pytest.raises(ValueError):
        MobilizAVLProvider(base_url=STUB_URL, api_key="k", account_id="")


@skip_if_unreachable
@pytest.mark.asyncio
async def test_fetch_trips_maps_stub_response(provider):
    trips = await provider.fetch_trips(since=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert len(trips) == 2

    t1 = next(t for t in trips if t.external_id == "T-1001")
    assert t1.plaka == "34ABC123"
    assert t1.distance_km == 450.0
    assert t1.driver_external_id == "DRV-42"
    assert t1.end_time is not None
    assert t1.raw_payload["trip_id"] == "T-1001"

    # T-1002 has a null end_time in the stub — must map to None, not crash.
    t2 = next(t for t in trips if t.external_id == "T-1002")
    assert t2.end_time is None
    assert t2.start_lat == 40.2


@skip_if_unreachable
@pytest.mark.asyncio
async def test_fetch_positions_maps_stub_response(provider):
    positions = await provider.fetch_positions(["34ABC123", "06XYZ456"])
    assert len(positions) == 2
    assert positions[0].plaka == "34ABC123"
    assert positions[0].speed_kmh == 85.0


@skip_if_unreachable
@pytest.mark.asyncio
async def test_fetch_positions_empty_list_still_calls_endpoint(provider):
    """Empty plakalar list means 'all active vehicles' per the base
    Protocol's docstring — must not short-circuit locally."""
    positions = await provider.fetch_positions([])
    assert len(positions) >= 1


@skip_if_unreachable
@pytest.mark.asyncio
async def test_healthcheck_true_when_stub_up(provider):
    assert await provider.healthcheck() is True


@pytest.mark.asyncio
async def test_healthcheck_false_when_unreachable():
    provider = MobilizAVLProvider(
        base_url="http://localhost:1", api_key="k", account_id="a"
    )
    assert await provider.healthcheck() is False
