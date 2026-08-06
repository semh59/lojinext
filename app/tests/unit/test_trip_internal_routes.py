"""Unit tests for v2/modules/trip/api/internal_routes.py.

New file added 2026-08-04 for the prediction_ml_service extraction (Task 5
Step 2b Option B) -- prediction_ml_service's ensemble_service.py reaches
sefer training data over HTTP instead of an in-process UnitOfWork. No
dedicated test existed for it yet (caught via the hard-gates unit-lane
coverage gate dropping below its 83% floor once v2/services/* was excluded
from the coverage source, 2026-08-05).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from v2.modules.trip.api import internal_routes


@pytest.mark.asyncio
class TestRequireInternalToken:
    async def test_no_secret_configured_non_prod_passes(self):
        with (
            patch.object(internal_routes.settings, "INTERNAL_API_SECRET", ""),
            patch.object(internal_routes.settings, "ENVIRONMENT", "test"),
        ):
            await internal_routes._require_internal_token(x_internal_token=None)

    async def test_no_secret_configured_prod_raises_503(self):
        with (
            patch.object(internal_routes.settings, "INTERNAL_API_SECRET", ""),
            patch.object(internal_routes.settings, "ENVIRONMENT", "prod"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes._require_internal_token(x_internal_token=None)
        assert exc_info.value.status_code == 503

    async def test_wrong_token_raises_401(self):
        with patch.object(internal_routes.settings, "INTERNAL_API_SECRET", "s3cr3t"):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes._require_internal_token(x_internal_token="wrong")
        assert exc_info.value.status_code == 401

    async def test_correct_token_passes(self):
        with patch.object(internal_routes.settings, "INTERNAL_API_SECRET", "s3cr3t"):
            await internal_routes._require_internal_token(x_internal_token="s3cr3t")


def _mock_uow():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    return uow


@pytest.mark.asyncio
class TestTrainingDataEndpoints:
    async def test_training_data_returns_repo_result(self):
        uow = _mock_uow()
        uow.sefer_repo.get_for_training = AsyncMock(return_value=[{"id": 1}])
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.training_data(arac_id=10, limit=50)

        assert result == [{"id": 1}]
        uow.sefer_repo.get_for_training.assert_awaited_once_with(10, limit=50)

    async def test_training_data_all_returns_repo_result(self):
        uow = _mock_uow()
        uow.sefer_repo.get_all_for_training = AsyncMock(return_value=[{"id": 2}])
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.training_data_all(limit=100)

        assert result == [{"id": 2}]
        uow.sefer_repo.get_all_for_training.assert_awaited_once_with(limit=100)


@pytest.mark.asyncio
class TestGetSefer:
    async def test_get_sefer_found(self):
        uow = _mock_uow()
        uow.sefer_repo.get_by_id = AsyncMock(return_value={"id": 5, "arac_id": 1})
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.get_sefer(sefer_id=5)

        assert result == {"id": 5, "arac_id": 1}

    async def test_get_sefer_not_found_raises_404(self):
        uow = _mock_uow()
        uow.sefer_repo.get_by_id = AsyncMock(return_value=None)
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes.get_sefer(sefer_id=999)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestUpdateTahminiTuketim:
    async def test_update_tahmini_tuketim_commits(self):
        uow = _mock_uow()
        uow.sefer_repo.update = AsyncMock()
        uow.commit = AsyncMock()
        body = internal_routes.TahminiTuketimBody(tahmini_tuketim=42.5)

        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.update_tahmini_tuketim(sefer_id=7, body=body)

        assert result == {"ok": True}
        uow.sefer_repo.update.assert_awaited_once_with(7, tahmini_tuketim=42.5)
        uow.commit.assert_awaited_once()
