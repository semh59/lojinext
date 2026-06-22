from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.routing.openroute_client import OpenRouteClient


class _FakeAsyncSession:
    """openroute_client `AsyncSessionLocal()` async context manager'ını taklit
    eder (kod sync get_sync_session değil, async session kullanıyor)."""

    def __init__(self, fetchone_row=None):
        self._fetchone_row = fetchone_row
        self.execute = AsyncMock(side_effect=self._execute)
        self.commit = AsyncMock()

    async def _execute(self, *args, **kwargs):
        res = MagicMock()
        res.fetchone = MagicMock(return_value=self._fetchone_row)
        res.scalar = MagicMock(return_value=None)
        res.scalar_one_or_none = MagicMock(return_value=None)
        return res

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


@pytest.fixture
def mock_ors_response():
    return {
        "routes": [
            {
                "summary": {
                    "distance": 100000.0,  # 100km
                    "duration": 3600.0,  # 1h
                    "ascent": 500.0,
                    "descent": 400.0,
                },
                "geometry": "encoded_polyline_string",  # We'll mock decode anyway
                "extras": {
                    "steepness": {"values": [[0, 10, 0]]},
                    "waycategory": {"values": [[0, 10, 1]]},
                },
            }
        ]
    }


@pytest.mark.asyncio
async def test_openroute_client_structure(mock_ors_response):
    # Test that the client can be instantiated and methods called

    # Mock dependencies — _save_to_cache async `AsyncSessionLocal()` kullanır;
    # gerçek DB'ye gitmesin diye onu mock'la (no-op cache yazımı).
    with patch(
        "app.database.connection.AsyncSessionLocal",
        return_value=_FakeAsyncSession(),
    ):
        # Mock API call — _call_api `httpx.AsyncClient.post` kullanır (requests değil)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_ors_response
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            # Mock Polyline Decoder to return dummy points
            with patch("app.core.utils.polyline.PolylineDecoder.decode") as mock_decode:
                mock_decode.return_value = [(0, 0), (1, 1)]

                # Mock Route Analyzer
                with patch(
                    "app.domain.services.route_analyzer.RouteAnalyzer.analyze_segments"
                ) as mock_analyze:
                    mock_analyze.return_value = {"highway": {"flat": 100.0}}

                    client = OpenRouteClient(api_key="test_key")
                    # Use valid coordinates (Turkey)
                    result = await client.get_distance(
                        (40.0, 30.0),
                        (41.0, 31.0),
                        use_cache=False,
                        include_details=True,
                    )

                    assert result is not None
                    assert result["distance_km"] == 100.0
                    assert result["details"]["highway"]["flat"] == 100.0


@pytest.mark.asyncio
async def test_update_route_distance_log(mock_ors_response):
    # Verify that update_route_distance attempts to update the database

    # We need to mock the session interaction heavily since we are not using a real DB in this unit/integration hybrid
    # For true integration we'd need a real DB, but let's stick to checking the logic flow first.

    # Mock SELECT response for getting coordinates
    mock_row = MagicMock()
    mock_row.cikis_lat = 40.0
    mock_row.cikis_lon = 29.0
    mock_row.varis_lat = 41.0
    mock_row.varis_lon = 29.0

    # update_route_distance async `AsyncSessionLocal()` kullanır (sync
    # get_sync_session değil) — doğru hedefi mock'la.
    fake_session = _FakeAsyncSession(fetchone_row=mock_row)
    with patch("app.database.connection.AsyncSessionLocal", return_value=fake_session):
        # Mock API (get_distance async → patch otomatik AsyncMock)
        with patch(
            "app.infrastructure.routing.openroute_client.OpenRouteClient.get_distance",
            new_callable=AsyncMock,
        ) as mock_get_dist:
            mock_get_dist.return_value = {
                "distance_km": 100,
                "duration_hours": 1,
                "ascent_m": 10,
                "descent_m": 10,
                "details": {"test": "data"},
            }

            client = OpenRouteClient(api_key="test")
            await client.update_route_distance(123)

            # Verify get_distance was called with include_details=True
            mock_get_dist.assert_called_with(
                (40.0, 29.0), (41.0, 29.0), use_cache=False, include_details=True
            )

            # Verify UPDATE was called
            # We check if session.execute was called with an UPDATE statement
            calls = fake_session.execute.call_args_list
            # First call is SELECT, second (or third depending on logic) should be UPDATE

            update_called = False
            for call in calls:
                args, _ = call
                if "UPDATE lokasyonlar" in str(args[0]):
                    update_called = True
                    break

            assert update_called, "UPDATE statement was not executed"
