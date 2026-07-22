"""Real-object integration tests for OpenRouteClient.

0-mock epigi (Faz1 dilim4): `httpx.AsyncClient.post` in-process mock'u
api_stub'a (gercek FastAPI sunucusu, Docker `--profile test`) gercek HTTP
round-trip ile degistirildi. Everything internal runs for real:
  - PolylineDecoder + RouteAnalyzer (a real Google-encoded polyline decoded
    from the stub's canned response and analysed for real -- stub'in
    extras'i gercek ORS "values" formatinda, "summary" degil),
    (conftest monkeypatches v2.modules.platform_infra.database.connection.AsyncSessionLocal to the
    shared test session).
"""

import pytest

from app.config import settings
from v2.modules.route_simulation.infrastructure.openroute_client import OpenRouteClient


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
