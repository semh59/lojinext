"""OpetFuelProvider against the real api_stub server (0-mock epiği —
gerçek HTTP, in-process mock değil). Requires
`docker compose --profile test up -d api-stub` (localhost:9000).

Bu adapter'ın request/response şekli gerçek OPET sözleşmesiyle
DOĞRULANMAMIŞ — bkz. opet.py'nin modül docstring'i. Bu testler adapter'ın
kendi (stub'a karşı) davranışını kanıtlar, gerçek OPET uyumunu değil."""

from datetime import datetime, timezone

import httpx
import pytest

from app.core.integrations.fuel.opet import OpetFuelProvider

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
    return OpetFuelProvider(base_url=STUB_URL, api_key="test-key", account_id="acc-1")


def test_constructor_requires_all_fields():
    with pytest.raises(ValueError):
        OpetFuelProvider(base_url="", api_key="k", account_id="a")
    with pytest.raises(ValueError):
        OpetFuelProvider(base_url=STUB_URL, api_key="", account_id="a")
    with pytest.raises(ValueError):
        OpetFuelProvider(base_url=STUB_URL, api_key="k", account_id="")


@skip_if_unreachable
@pytest.mark.asyncio
async def test_fetch_transactions_maps_stub_response(provider):
    transactions = await provider.fetch_transactions(
        since=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert len(transactions) == 1

    tx = transactions[0]
    assert tx.external_transaction_id == "TX-9001"
    assert tx.plaka == "34ABC123"
    assert tx.station_name == "OPET Bolu"
    assert tx.station_city == "Bolu"
    assert tx.liters == 180.5
    assert tx.price_per_liter == 42.3
    assert tx.total_amount_tl == 7636.65
    assert tx.odometer_km == 125430
    assert tx.driver_card_id == "CARD-1"
    assert tx.receipt_no == "R-556677"
    assert tx.fuel_type == "MOTORIN"
    assert tx.raw_payload["transactionId"] == "TX-9001"


@skip_if_unreachable
@pytest.mark.asyncio
async def test_healthcheck_true_when_stub_up(provider):
    assert await provider.healthcheck() is True


@pytest.mark.asyncio
async def test_healthcheck_false_when_unreachable():
    provider = OpetFuelProvider(
        base_url="http://localhost:1", api_key="k", account_id="a"
    )
    assert await provider.healthcheck() is False
