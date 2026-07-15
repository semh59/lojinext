from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from v2.modules.import_excel.application.execute_import import execute_import
from v2.modules.import_excel.application.preview_import import parse_and_preview
from v2.modules.import_excel.application.rollback_import import rollback_import


@pytest.mark.asyncio
async def test_import_preview():
    """Verify CSV parsing and mapping logic."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.read = AsyncMock(return_value=b"plaka,kapasite\n34ABC123,25.5")

    result = await parse_and_preview(mock_file, "arac")
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_import_execution_and_rollback():
    """Verify bulk import and subsequent rollback."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.read = AsyncMock(return_value=b"plaka,kapasite\n34ABC123,25.5")

    mock_job = MagicMock()
    mock_job.id = 1

    with (
        patch(
            "v2.modules.import_excel.application.execute_import.UnitOfWork"
        ) as mock_uow_cls,
        patch(
            "v2.modules.import_excel.application.rollback_import.UnitOfWork"
        ) as mock_rollback_uow_cls,
    ):
        mock_uow = MagicMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow

        mock_uow.session.execute = AsyncMock()
        mock_uow.session.flush = AsyncMock()
        mock_uow.commit = AsyncMock()

        # execute_import wraps each row in a SAVEPOINT (begin_nested) so a
        # failed row rolls back alone; the mocked session must support it.
        mock_savepoint = MagicMock()
        mock_savepoint.commit = AsyncMock()
        mock_savepoint.rollback = AsyncMock()
        mock_uow.session.begin_nested = AsyncMock(return_value=mock_savepoint)

        # Use AsyncMock for all awaited methods
        mock_uow.import_repo.create_import_job = AsyncMock(return_value=mock_job)
        mock_uow.import_repo.update_job_status = AsyncMock()

        # 1. Execute
        result = await execute_import(
            mock_file, "arac", 1, {"plaka": "plaka", "kapasite": "kapasite"}
        )
        assert result["job_id"] == 1

        # 2. Rollback (separate UnitOfWork instance, rollback_import.py's own)
        mock_rollback_uow = MagicMock()
        mock_rollback_uow.__aenter__.return_value = mock_rollback_uow
        mock_rollback_uow_cls.return_value = mock_rollback_uow
        mock_rollback_uow.session.execute = AsyncMock()
        mock_rollback_uow.commit = AsyncMock()
        mock_rollback_uow.import_repo.get_by_id = AsyncMock(
            return_value=MagicMock(
                id=1,
                durum="COMPLETED",
                aktarim_tipi="arac",
                islem_haritasi={"inserted_ids": [100]},
            )
        )
        mock_rollback_uow.import_repo.update_job_status = AsyncMock()

        success = await rollback_import(1, 1)
        assert success is True
