from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.routing.openroute_client import OpenRouteClient

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    return OpenRouteClient(api_key="mock_key")


async def test_update_route_distance_parses_details(db_session):
    """0-mock epiği: gerçek DB'ye seed edilen bir Lokasyon satırı üzerinden
    gerçek UPDATE çalıştırılır (AsyncSessionLocal conftest'te bu test
    session'ına monkeypatch'li). get_distance (dış API çağrısı) burada
    KASITLI mock'lu kalır — bu test HTTP davranışını değil, gerçek API
    sonucu verildiğinde DB güncelleme/parse mantığının doğruluğunu test
    ediyor; HTTP round-trip'in kendisi test_get_distance_requests_details_
    by_default ve diğer client-level testlerde gerçek stub'a karşı ayrıca
    kanıtlanıyor."""
    from app.tests._helpers.seed import seed_lokasyon

    lokasyon = await seed_lokasyon(
        db_session,
        cikis_lat=40.0,
        cikis_lon=29.0,
        varis_lat=39.0,
        varis_lon=32.0,
    )
    await db_session.commit()

    client = OpenRouteClient(api_key="mock_key")

    mock_api_result = {
        "distance_km": 100.0,
        "duration_hours": 1.5,
        "ascent_m": 500,
        "descent_m": 500,
        "details": {
            "highway": {"flat": 40.0, "up": 10.0, "down": 10.0},  # Total 60
            "other": {"flat": 20.0, "up": 10.0, "down": 10.0},  # Total 40
        },
    }

    with patch.object(
        client, "get_distance", new_callable=AsyncMock, return_value=mock_api_result
    ):
        result = await client.update_route_distance(lokasyon.id)

    assert result == mock_api_result

    from sqlalchemy import text

    row = (
        await db_session.execute(
            text(
                "SELECT otoban_mesafe_km, sehir_ici_mesafe_km FROM lokasyonlar WHERE id = :id"
            ),
            {"id": lokasyon.id},
        )
    ).fetchone()
    assert row.otoban_mesafe_km == 60.0
    assert row.sehir_ici_mesafe_km == 40.0


def test_openroute_client_prefers_canonical_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTESERVICE_API_KEY", "canonical-key")
    monkeypatch.setenv("OPENROUTE_API_KEY", "legacy-key")

    client = OpenRouteClient(api_key=None)

    assert client.api_key == "canonical-key"


async def test_get_distance_requests_details_by_default(monkeypatch):
    client = OpenRouteClient(api_key="mock-key")
    breaker = MagicMock()

    # CircuitBreaker.call is async; AsyncMock delegates to the real fn.
    async def mock_call(func, *args, **kwargs):
        return await func(*args, **kwargs)

    breaker.call = AsyncMock(side_effect=mock_call)

    with (
        patch(
            "app.infrastructure.routing.openroute_client.CircuitBreakerRegistry.get_sync",
            return_value=breaker,
        ),
        patch.object(client, "_save_to_cache"),
        patch.object(
            client,
            "_call_api",
            new_callable=AsyncMock,
            return_value={
                "distance_km": 100.0,
                "duration_hours": 1.5,
                "ascent_m": 500.0,
                "descent_m": 450.0,
            },
        ) as mock_call_api,
    ):
        result = await client.get_distance((40.0, 29.0), (39.0, 32.0), use_cache=False)

    assert result["source"] == "api"
    assert mock_call_api.call_args.kwargs["include_details"] is True
