"""Real-object integration tests for OpenRouteClient.

0-mock epigi (Faz1 dilim4): `httpx.AsyncClient.post` in-process mock'u
api_stub'a (gercek FastAPI sunucusu, Docker `--profile test`) gercek HTTP
round-trip ile degistirildi. Everything internal runs for real:
  - PolylineDecoder + RouteAnalyzer (a real Google-encoded polyline decoded
    from the stub's canned response and analysed for real -- stub'in
    extras'i gercek ORS "values" formatinda, "summary" degil),
  - the DB read/update in update_route_distance hits the real test DB
    (conftest monkeypatches app.database.connection.AsyncSessionLocal to the
    shared test session).
"""

import pytest
from sqlalchemy import insert, select

from app.config import settings
from app.database.models import Lokasyon
from app.infrastructure.routing.openroute_client import OpenRouteClient


@pytest.mark.asyncio
async def test_openroute_client_structure(db_session, monkeypatch):
    """get_distance runs the REAL PolylineDecoder + REAL RouteAnalyzer against
    api_stub's canned OpenRoute directions response (450km/motorway/flat)."""
    monkeypatch.setattr(settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2")
    client = OpenRouteClient(api_key="test_key")
    result = await client.get_distance(
        (40.0, 30.0), (41.0, 31.0), use_cache=False, include_details=True
    )

    assert result is not None
    assert result["distance_km"] == 450.0
    # Real RouteAnalyzer produced a details breakdown (a real dict, not a mocked value).
    assert isinstance(result.get("details"), dict)
    assert result["details"]["highway"]["flat"] > 0


@pytest.mark.asyncio
async def test_update_route_distance_log(db_session, monkeypatch):
    """update_route_distance reads the route's coordinates and writes the API
    breakdown back to the REAL DB, via a real get_distance->api_stub round-trip."""
    monkeypatch.setattr(settings, "OPENROUTE_API_BASE_URL", "http://localhost:9000/v2")
    res = await db_session.execute(
        insert(Lokasyon).values(
            cikis_yeri="TestCikis",
            varis_yeri="TestVaris",
            mesafe_km=0.0,
            cikis_lat=40.0,
            cikis_lon=29.0,
            varis_lat=41.0,
            varis_lon=29.0,
        )
    )
    await db_session.commit()
    lok_id = res.inserted_primary_key[0]

    client = OpenRouteClient(api_key="test")
    await client.update_route_distance(lok_id)

    # Real DB round-trip: the row's API metrics were persisted by the UPDATE.
    row = (
        await db_session.execute(select(Lokasyon).where(Lokasyon.id == lok_id))
    ).scalar_one()
    assert row.api_mesafe_km == 450.0
    assert row.otoban_mesafe_km > 0
