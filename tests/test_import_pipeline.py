from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from app.core.services.import_service import ImportService


@pytest.mark.asyncio
async def test_import_preview():
    """Verify CSV parsing and mapping logic."""
    service = ImportService()
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.read = AsyncMock(return_value=b"plaka,kapasite\n34ABC123,25.5")

    result = await service.parse_and_preview(mock_file, "arac")
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_import_execution_and_rollback():
    """Verify bulk import and subsequent rollback."""
    service = ImportService()
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.read = AsyncMock(return_value=b"plaka,kapasite\n34ABC123,25.5")

    mock_job = MagicMock()
    mock_job.id = 1

    with patch("app.core.services.import_service.UnitOfWork") as mock_uow_cls:
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.session.execute = AsyncMock()
        mock_uow.session.flush = AsyncMock()
        mock_uow.commit = AsyncMock()

        # Use AsyncMock for all awaited methods
        mock_uow.import_repo.create_import_job = AsyncMock(return_value=mock_job)
        mock_uow.import_repo.update_job_status = AsyncMock()
        mock_uow.import_repo.get_by_id = AsyncMock(
            return_value=MagicMock(
                id=1,
                durum="COMPLETED",
                aktarim_tipi="arac",
                islem_haritasi={"inserted_ids": [100]},
            )
        )

        # 1. Execute
        result = await service.execute_import(
            mock_file, "arac", 1, {"plaka": "plaka", "kapasite": "kapasite"}
        )
        assert result["job_id"] == 1

        # 2. Rollback
        success = await service.rollback_import(1, 1)
        assert success is True
