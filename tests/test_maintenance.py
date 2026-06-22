from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.maintenance_service import MaintenanceService
from app.database.models import AracBakim, BakimTipi


@pytest.mark.asyncio
async def test_create_maintenance_record():
    """Verify maintenance record creation logic."""
    service = MaintenanceService()

    with patch("app.core.services.maintenance_service.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.commit = AsyncMock()
        mock_uow.arac_repo.get_by_id = AsyncMock(
            return_value=MagicMock(id=1, plaka="34ABC123")
        )

        mock_bakim = AracBakim(id=10, arac_id=1, bakim_tipi=BakimTipi.PERIYODIK)
        mock_uow.maintenance_repo.add = AsyncMock(return_value=mock_bakim)

        result = await service.create_maintenance_record(
            arac_id=1,
            bakim_tipi=BakimTipi.PERIYODIK,
            km_bilgisi=50000,
            bakim_tarihi=datetime.now(),
        )

        assert result.id == 10
        mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_upcoming_alerts():
    """Verify enrichment of maintenance alerts with vehicle plates."""
    service = MaintenanceService()

    with patch("app.core.services.maintenance_service.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.maintenance_repo.get_upcoming_maintenance = AsyncMock(
            return_value=[
                MagicMock(
                    id=1,
                    arac_id=101,
                    bakim_tipi="PERIYODIK",
                    bakim_tarihi=datetime.now(),
                )
            ]
        )
        # Service batch-fetches vehicles via get_by_ids (N+1 fix) → returns a
        # {arac_id: Arac} map, not a single record.
        mock_uow.arac_repo.get_by_ids = AsyncMock(
            return_value={101: MagicMock(plaka="PLK-99")}
        )

        alerts = await service.get_upcoming_alerts()

        assert len(alerts) == 1
        assert alerts[0]["plaka"] == "PLK-99"


@pytest.mark.asyncio
async def test_mark_as_completed():
    """Verify that maintenance can be marked as completed."""
    service = MaintenanceService()

    with patch("app.core.services.maintenance_service.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.commit = AsyncMock()
        mock_uow.maintenance_repo.update = AsyncMock(return_value=True)

        success = await service.mark_as_completed(10)
        assert success is True
        mock_uow.maintenance_repo.update.assert_called_with(10, tamamlandi=True)
        mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_vehicle_maintenance_history():
    """Verify history retrieval for a specific vehicle."""
    service = MaintenanceService()

    with patch("app.core.services.maintenance_service.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_record = MagicMock(id=1, arac_id=1, bakim_tipi=BakimTipi.PERIYODIK)
        mock_uow.maintenance_repo.get_by_arac_id = AsyncMock(return_value=[mock_record])

        history = await service.get_vehicle_maintenance_history(1)
        assert len(history) == 1
        assert history[0].id == 1
        mock_uow.maintenance_repo.get_by_arac_id.assert_called_with(1)
