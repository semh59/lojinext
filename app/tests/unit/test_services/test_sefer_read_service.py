from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.sefer_read_service import SeferReadService

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_id_with_details = AsyncMock(return_value=None)
    repo.get_all = AsyncMock(return_value=[])
    repo.count_all = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def service(mock_repo):
    return SeferReadService(mock_repo)


class TestSeferReadService:
    async def test_get_by_id_found(self, service, mock_repo):
        mock_sefer_obj = MagicMock()
        mock_sefer_obj.sefer_id = 1

        with patch("app.core.services.sefer_read_service.Sefer") as MockSefer:
            MockSefer.model_validate.return_value = mock_sefer_obj
            mock_repo.get_by_id_with_details = AsyncMock(return_value={"sefer_id": 1})

            result = await service.get_by_id(sefer_id=1)
            assert result is not None
            assert result.sefer_id == 1

    async def test_get_by_id_not_found(self, service, mock_repo):
        mock_repo.get_by_id_with_details = AsyncMock(return_value=None)
        result = await service.get_by_id(sefer_id=999)
        assert result is None

    async def test_get_by_vehicle(self, service, mock_repo):
        mock_sefer1 = MagicMock()
        mock_sefer1.sefer_id = 1
        mock_sefer2 = MagicMock()
        mock_sefer2.sefer_id = 2

        with patch("app.core.services.sefer_read_service.Sefer") as MockSefer:
            MockSefer.model_validate.side_effect = [mock_sefer1, mock_sefer2]
            mock_repo.get_all = AsyncMock(
                return_value=[{"sefer_id": 1}, {"sefer_id": 2}]
            )

            result = await service.get_by_vehicle(arac_id=10)
            assert isinstance(result, list)
            assert len(result) == 2

    async def test_get_all_paged(self, service, mock_repo):
        with patch(
            "app.core.services.sefer_read_service.SeferResponse"
        ) as MockSeferResponse:
            mock_response = MagicMock()
            MockSeferResponse.model_validate.return_value = mock_response
            mock_repo.count_all = AsyncMock(return_value=100)
            mock_repo.get_all = AsyncMock(return_value=[{"sefer_id": 1}])

            result = await service.get_all_paged(skip=0, limit=10)
            assert isinstance(result, dict)
            assert "items" in result or "meta" in result

    async def test_get_sefer_by_id_legacy(self, service, mock_repo):
        mock_sefer_obj = MagicMock()
        mock_sefer_obj.model_dump.return_value = {"sefer_id": 1, "arac_id": 10}

        with patch("app.core.services.sefer_read_service.Sefer") as MockSefer:
            MockSefer.model_validate.return_value = mock_sefer_obj
            mock_repo.get_by_id_with_details = AsyncMock(return_value={"sefer_id": 1})

            result = await service.get_sefer_by_id(sefer_id=1)
            assert result is not None
            assert isinstance(result, dict)

    async def test_get_by_vehicle_empty(self, service, mock_repo):
        mock_repo.get_all = AsyncMock(return_value=[])
        result = await service.get_by_vehicle(arac_id=999)
        assert result == []

    async def test_get_all_paged_simple(self, service, mock_repo):
        with patch("app.core.services.sefer_read_service.SeferResponse"):
            mock_repo.count_all = AsyncMock(return_value=50)
            mock_repo.get_all = AsyncMock(return_value=[])

            result = await service.get_all_paged(skip=0, limit=20)
            assert isinstance(result, dict)

    async def test_service_initialization(self, mock_repo):
        service = SeferReadService(mock_repo)
        assert service is not None
        assert hasattr(service, "get_by_id")
        assert hasattr(service, "get_all_paged")
