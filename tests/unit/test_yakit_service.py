from unittest.mock import AsyncMock, patch

import pytest

from app.core.services.yakit_service import YakitService


class TestYakitService:
    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_event_bus(self):
        from unittest.mock import MagicMock

        return MagicMock()

    @pytest.fixture
    def service(self, mock_repo, mock_event_bus):
        return YakitService(repo=mock_repo, event_bus=mock_event_bus)

    @pytest.fixture
    def mock_uow(self):
        uow = AsyncMock()
        uow.__aenter__.return_value = uow
        uow.__aexit__.return_value = None
        uow.session = AsyncMock()
        return uow

    @pytest.mark.asyncio
    async def test_check_rolling_outlier_normal(self, service, mock_uow):
        """Normal consumption (e.g. 30L/100km) should not be flagged"""
        # Current: 1000km, 60L. Last sync point: 800km.
        # total_dist = 1000 - 800 = 200. valid_fuel = (60+60) - 60 = 60.
        # rolling_avg = (60 / 200) * 100 = 30.
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(
            return_value=[{"litre": 60.0, "km_sayac": 800}]
        )

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            is_outlier = await service._check_rolling_outlier(
                arac_id=1, current_litre=60, current_km=1000
            )
            assert is_outlier is False

    @pytest.mark.asyncio
    async def test_check_rolling_outlier_high(self, service, mock_uow):
        """High consumption should be flagged"""
        # Current: 1000km, 150L. Last sync point: 800km.
        # total_dist = 200. valid_fuel = (150+10) - 10 = 150.
        # rolling_avg = (150 / 200) * 100 = 75.
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(
            return_value=[{"litre": 10.0, "km_sayac": 800}]
        )

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            is_outlier = await service._check_rolling_outlier(
                arac_id=1, current_litre=150, current_km=1000
            )
            assert is_outlier is True

    @pytest.mark.asyncio
    async def test_check_rolling_outlier_empty_db(self, service, mock_uow):
        """Should return False if no historical data"""
        mock_uow.yakit_repo.get_last_n_by_arac = AsyncMock(return_value=[])

        with patch("app.core.services.yakit_service.get_uow", return_value=mock_uow):
            assert await service._check_rolling_outlier(1, 30, 1000) is False
