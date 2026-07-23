from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.route_simulation.application.route_calibration_service import (
    RouteCalibrationService,
)


@pytest.mark.asyncio
async def test_calibrate_route_from_trip_logic():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    uow.commit = AsyncMock()
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 1,
            "guzergah_id": 10,
            "rota_detay": {"coordinates": [[29.0, 41.0], [29.1, 41.1]]},
        }
    )
    uow.lokasyon_repo.get_by_id = AsyncMock(return_value=SimpleNamespace(id=10))
    uow.session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: None)
    )
    uow.session.add = MagicMock()

    with (
        patch("v2.modules.route_simulation.application.route_calibration_service.LineString") as mock_line,
        patch("v2.modules.route_simulation.application.route_calibration_service.from_shape") as mock_shape,
    ):
        mock_line.return_value = MagicMock()
        # calibrate now stores bytes(from_shape(...).data) — a plain BYTEA column,
        # no PostGIS. Return a WKBElement-like object exposing .data.
        mock_shape.return_value = SimpleNamespace(data=b"WKB")

        service = RouteCalibrationService(uow)
        success = await service.calibrate_route_from_trip(1)

    assert success is True
    uow.session.add.assert_called_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_match_sefer_to_path_logic():
    uow = AsyncMock()
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = None
    uow.sefer_repo.get_by_id = AsyncMock(
        return_value={
            "id": 1,
            "guzergah_id": 10,
            "rota_detay": {"coordinates": [[29.0, 41.0], [29.1, 41.1]]},
        }
    )

    service = RouteCalibrationService(uow)
    service.get_calibration_for_lokasyon = AsyncMock(
        return_value=SimpleNamespace(hedef_path="WKB")
    )

    result = await service.match_sefer_to_path(1)
    assert result["status"] == "verification_unavailable"
    assert result["matches"] is False
    assert result["error_code"] == "SPATIAL_VERIFICATION_NOT_IMPLEMENTED"
