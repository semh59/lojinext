"""Unit tests for v2/modules/driver/api/internal_routes.py.

New file added 2026-08-04 for the prediction_ml_service extraction (Task 5
Step 2b Option B). No dedicated test existed for it yet (caught via the
hard-gates unit-lane coverage gate, 2026-08-05).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from v2.modules.driver.api import internal_routes


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


@pytest.mark.asyncio
class TestDriverStats:
    async def test_returns_stats_list(self):
        mock_get_driver_stats = AsyncMock(return_value=[{"sofor_id": 1}])
        with patch.object(internal_routes, "get_driver_stats", mock_get_driver_stats):
            result = await internal_routes.driver_stats(
                sofor_id=1, include_elite_score=False
            )

        assert result == [{"sofor_id": 1}]
        mock_get_driver_stats.assert_awaited_once_with(
            sofor_id=1, include_elite_score=False
        )


@pytest.mark.asyncio
class TestDriverById:
    async def test_found(self):
        mock_get_by_id = AsyncMock(return_value={"id": 3, "ad_soyad": "Test"})
        with patch.object(internal_routes, "get_by_id", mock_get_by_id):
            result = await internal_routes.driver_by_id(sofor_id=3)

        assert result == {"id": 3, "ad_soyad": "Test"}

    async def test_not_found_raises_404(self):
        mock_get_by_id = AsyncMock(return_value=None)
        with patch.object(internal_routes, "get_by_id", mock_get_by_id):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes.driver_by_id(sofor_id=999)

        assert exc_info.value.status_code == 404
