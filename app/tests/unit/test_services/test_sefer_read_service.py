from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.trip.application import list_trips

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_id_with_details = AsyncMock(return_value=None)
    repo.get_all = AsyncMock(return_value=[])
    repo.count_all = AsyncMock(return_value=0)
    return repo


class TestListTrips:
    async def test_get_by_id_found(self, mock_repo):
        mock_sefer_obj = MagicMock()
        mock_sefer_obj.sefer_id = 1

        with patch("v2.modules.trip.application.list_trips.Sefer") as MockSefer:
            MockSefer.model_validate.return_value = mock_sefer_obj
            mock_repo.get_by_id_with_details = AsyncMock(return_value={"sefer_id": 1})

            result = await list_trips.get_by_id(sefer_id=1, repo=mock_repo)
            assert result is not None
            assert result.sefer_id == 1

    async def test_get_by_id_not_found(self, mock_repo):
        mock_repo.get_by_id_with_details = AsyncMock(return_value=None)
        result = await list_trips.get_by_id(sefer_id=999, repo=mock_repo)
        assert result is None

    async def test_get_by_vehicle(self, mock_repo):
        mock_sefer1 = MagicMock()
        mock_sefer1.sefer_id = 1
        mock_sefer2 = MagicMock()
        mock_sefer2.sefer_id = 2

        with patch("v2.modules.trip.application.list_trips.Sefer") as MockSefer:
            MockSefer.model_validate.side_effect = [mock_sefer1, mock_sefer2]
            mock_repo.get_all = AsyncMock(
                return_value=[{"sefer_id": 1}, {"sefer_id": 2}]
            )

            result = await list_trips.get_by_vehicle(arac_id=10, repo=mock_repo)
            assert isinstance(result, list)
            assert len(result) == 2

    async def test_get_all_paged(self, mock_repo):
        with patch(
            "v2.modules.trip.application.list_trips.SeferResponse"
        ) as MockSeferResponse:
            mock_response = MagicMock()
            MockSeferResponse.model_validate.return_value = mock_response
            mock_repo.count_all = AsyncMock(return_value=100)
            mock_repo.get_all = AsyncMock(return_value=[{"sefer_id": 1}])

            result = await list_trips.get_all_paged(skip=0, limit=10, repo=mock_repo)
            assert isinstance(result, dict)
            assert "items" in result or "meta" in result

    async def test_get_sefer_by_id_legacy(self, mock_repo):
        mock_sefer_obj = MagicMock()
        mock_sefer_obj.model_dump.return_value = {"sefer_id": 1, "arac_id": 10}

        with patch("v2.modules.trip.application.list_trips.Sefer") as MockSefer:
            MockSefer.model_validate.return_value = mock_sefer_obj
            mock_repo.get_by_id_with_details = AsyncMock(return_value={"sefer_id": 1})

            result = await list_trips.get_sefer_by_id(sefer_id=1, repo=mock_repo)
            assert result is not None
            assert isinstance(result, dict)

    async def test_get_by_vehicle_empty(self, mock_repo):
        mock_repo.get_all = AsyncMock(return_value=[])
        result = await list_trips.get_by_vehicle(arac_id=999, repo=mock_repo)
        assert result == []

    async def test_get_all_paged_simple(self, mock_repo):
        with patch("v2.modules.trip.application.list_trips.SeferResponse"):
            mock_repo.count_all = AsyncMock(return_value=50)
            mock_repo.get_all = AsyncMock(return_value=[])

            result = await list_trips.get_all_paged(skip=0, limit=20, repo=mock_repo)
            assert isinstance(result, dict)
