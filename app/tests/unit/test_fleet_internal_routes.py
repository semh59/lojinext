"""Unit tests for v2/modules/fleet/api/internal_routes.py.

New file added 2026-08-04 for the prediction_ml_service extraction (Task 5
Step 2b Option B): prediction_ml_service reaches vehicle/trailer data over
HTTP instead of importing v2.modules.fleet.public directly. No dedicated
test existed for it yet (caught via the hard-gates unit-lane coverage gate,
2026-08-05).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from v2.modules.fleet.api import internal_routes


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
class TestGetVehicle:
    async def test_found(self):
        uow = _mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value={"id": 1, "plaka": "34AB1"})
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.get_vehicle(arac_id=1)

        assert result == {"id": 1, "plaka": "34AB1"}

    async def test_not_found_raises_404(self):
        uow = _mock_uow()
        uow.arac_repo.get_by_id = AsyncMock(return_value=None)
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes.get_vehicle(arac_id=999)

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
class TestGetTrailer:
    async def test_found(self):
        uow = _mock_uow()
        uow.dorse_repo.get_by_id = AsyncMock(return_value={"id": 2})
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            result = await internal_routes.get_trailer(dorse_id=2)

        assert result == {"id": 2}

    async def test_not_found_raises_404(self):
        uow = _mock_uow()
        uow.dorse_repo.get_by_id = AsyncMock(return_value=None)
        with patch.object(internal_routes, "UnitOfWork", return_value=uow):
            with pytest.raises(HTTPException) as exc_info:
                await internal_routes.get_trailer(dorse_id=999)

        assert exc_info.value.status_code == 404
