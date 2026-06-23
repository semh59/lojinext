"""Real-object integration tests for OpenRouteClient.

Only the external ORS HTTP call (httpx) is stubbed — calling ORS for real means a
live API key, cost and rate limits. Everything internal runs for real:
  - PolylineDecoder + RouteAnalyzer (no longer mocked; a real Google-encoded
    polyline is decoded and analysed),
  - the DB read/update in update_route_distance hits the real test DB
    (conftest monkeypatches app.database.connection.AsyncSessionLocal to the
    shared test session).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import insert, select

from app.database.models import Lokasyon
from app.infrastructure.routing.openroute_client import OpenRouteClient

# Google's canonical encoded-polyline example → 3 real points. Decoded for real by
# PolylineDecoder (dependency-free). ORS `extras` index ranges reference those nodes.
_REAL_POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


@pytest.fixture
def ors_response_real_geometry():
    return {
        "routes": [
            {
                "summary": {
                    "distance": 100000.0,  # 100 km
                    "duration": 3600.0,  # 1 h
                    "ascent": 500.0,
                    "descent": 400.0,
                },
                "geometry": _REAL_POLYLINE,
                "extras": {
                    "steepness": {"values": [[0, 2, 0]]},
                    "waycategory": {"values": [[0, 2, 1]]},
                    "waytype": {"values": [[0, 2, 1]]},
                },
            }
        ]
    }


@pytest.mark.asyncio
async def test_openroute_client_structure(db_session, ors_response_real_geometry):
    """get_distance runs the REAL PolylineDecoder + REAL RouteAnalyzer; only the
    external ORS HTTP call is stubbed."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = ors_response_real_geometry

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response
    ):
        client = OpenRouteClient(api_key="test_key")
        result = await client.get_distance(
            (40.0, 30.0), (41.0, 31.0), use_cache=False, include_details=True
        )

    assert result is not None
    assert result["distance_km"] == 100.0
    # Real RouteAnalyzer produced a details breakdown (a real dict, not a mocked value).
    assert isinstance(result.get("details"), dict)


@pytest.mark.asyncio
async def test_update_route_distance_log(db_session):
    """update_route_distance reads the route's coordinates and writes the API
    breakdown back to the REAL DB. Only the external get_distance (ORS) is stubbed."""
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

    with patch(
        "app.infrastructure.routing.openroute_client.OpenRouteClient.get_distance",
        new_callable=AsyncMock,
        return_value={
            "distance_km": 100,
            "duration_hours": 1,
            "ascent_m": 10,
            "descent_m": 10,
            "details": {"highway": {"flat": 100.0}},
        },
    ) as mock_get_dist:
        client = OpenRouteClient(api_key="test")
        await client.update_route_distance(lok_id)

    mock_get_dist.assert_called_with(
        (40.0, 29.0), (41.0, 29.0), use_cache=False, include_details=True
    )

    # Real DB round-trip: the row's API metrics were persisted by the UPDATE.
    row = (
        await db_session.execute(select(Lokasyon).where(Lokasyon.id == lok_id))
    ).scalar_one()
    assert row.api_mesafe_km == 100
    assert row.otoban_mesafe_km == 100.0  # sum(details["highway"].values())
