from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.analytics_executive.infrastructure.executive_read_models import (
    DEFAULT_FILO_ORTALAMA,
    AnalizRepository,
)


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(mock_session):
    return AnalizRepository(session=mock_session)


@pytest.mark.asyncio
async def test_get_dashboard_stats_success(repo, mock_session):
    mock_row = MagicMock()
    mock_row._mapping = {
        "toplam_arac": 12,
        "toplam_sofor": 8,
        "filo_ortalama": 30.0,
        "toplam_yakit": 1500.5,
    }
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute.return_value = mock_result

    stats = await repo.get_dashboard_stats()

    assert stats == {
        "toplam_arac": 12,
        "toplam_sofor": 8,
        "filo_ortalama": 30.0,
        "toplam_yakit": 1500.5,
    }
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_dashboard_stats_empty(repo, mock_session):
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session.execute.return_value = mock_result

    stats = await repo.get_dashboard_stats()

    assert stats == {
        "toplam_arac": 0,
        "toplam_sofor": 0,
        "filo_ortalama": DEFAULT_FILO_ORTALAMA,
        "toplam_yakit": 0,
    }


@pytest.mark.asyncio
async def test_get_filo_ortalama_tuketim_default(repo, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    val = await repo.get_filo_ortalama_tuketim()

    assert val == DEFAULT_FILO_ORTALAMA


@pytest.mark.asyncio
async def test_get_filo_ortalama_tuketim_value(repo, mock_session):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 28.543
    mock_session.execute.return_value = mock_result

    val = await repo.get_filo_ortalama_tuketim()

    assert val == 28.54


@pytest.mark.asyncio
async def test_get_top_performing_vehicles(repo, mock_session):
    mock_row = MagicMock()
    mock_row.plaka = "34ABC12"
    mock_row.avg_consumption = 32.5
    mock_row.trip_count = 5

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    stats = await repo.get_top_performing_vehicles(limit=5)

    assert stats == [{"plaka": "34ABC12", "avg_consumption": 32.5, "trip_count": 5}]
