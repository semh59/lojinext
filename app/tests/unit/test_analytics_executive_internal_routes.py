"""Unit tests for v2/modules/analytics_executive/api/internal_routes.py.

New file added 2026-08-04 for the prediction_ml_service extraction (Task 5
Step 2b Option B): ensemble_service.py/kalman_estimator.py's
save_model_params/get_daily_summary_for_ml calls reach analytics_executive
over HTTP instead of an in-process UnitOfWork. No dedicated test existed
for it yet (caught via the hard-gates unit-lane coverage gate, 2026-08-05).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from v2.modules.analytics_executive.api import internal_routes


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


def _mock_uow():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    return uow


@pytest.mark.asyncio
class TestSaveModelParams:
    async def test_saves_and_commits(self):
        uow = _mock_uow()
        uow.analiz_repo.save_model_params = AsyncMock()
        uow.commit = AsyncMock()
        body = internal_routes.ModelParamsBody(arac_id=5, result={"r2": 0.9})

        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.save_model_params(body)

        assert result == {"ok": True}
        uow.analiz_repo.save_model_params.assert_awaited_once_with(5, {"r2": 0.9})
        uow.commit.assert_awaited_once()


@pytest.mark.asyncio
class TestDailySummary:
    async def test_returns_repo_result(self):
        uow = _mock_uow()
        uow.analiz_repo.get_daily_summary_for_ml = AsyncMock(
            return_value=[{"gun": "2026-08-01"}]
        )

        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.daily_summary(days=30, arac_id=7)

        assert result == [{"gun": "2026-08-01"}]
        uow.analiz_repo.get_daily_summary_for_ml.assert_awaited_once_with(
            days=30, arac_id=7
        )
