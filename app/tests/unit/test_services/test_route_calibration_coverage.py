"""Coverage tests for app/core/services/route_calibration_service.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_uow(sefer=None, lokasyon=None, session_result=None):
    """Build a UnitOfWork-like async context manager mock."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()

    mock_sefer_repo = AsyncMock()
    mock_sefer_repo.get_by_id = AsyncMock(return_value=sefer)
    mock_sefer_repo.get = AsyncMock(return_value=sefer)
    mock_uow.sefer_repo = mock_sefer_repo

    mock_lok_repo = AsyncMock()
    mock_lok_repo.get_by_id = AsyncMock(return_value=lokasyon)
    mock_lok_repo.get = AsyncMock(return_value=lokasyon)
    mock_uow.lokasyon_repo = mock_lok_repo

    if session_result is not None:
        mock_uow.session = AsyncMock()
        mock_uow.session.execute = AsyncMock(return_value=session_result)
        mock_uow.session.add = MagicMock()
    else:
        mock_uow.session = AsyncMock()
        # Default: returns None from scalar_one_or_none
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_uow.session.execute = AsyncMock(return_value=mock_result)
        mock_uow.session.add = MagicMock()

    return mock_uow


def _make_sefer(rota_detay=None, guzergah_id=None):
    sefer = MagicMock()
    sefer.rota_detay = rota_detay
    sefer.guzergah_id = guzergah_id
    return sefer


# ---------------------------------------------------------------------------
# _get_value static method
# ---------------------------------------------------------------------------


def test_get_value_from_dict():
    from app.core.services.route_calibration_service import RouteCalibrationService

    result = RouteCalibrationService._get_value({"key": "val"}, "key")
    assert result == "val"


def test_get_value_from_dict_missing():
    from app.core.services.route_calibration_service import RouteCalibrationService

    result = RouteCalibrationService._get_value({}, "missing_key")
    assert result is None


def test_get_value_from_object():
    from app.core.services.route_calibration_service import RouteCalibrationService

    obj = MagicMock()
    obj.some_field = 42
    result = RouteCalibrationService._get_value(obj, "some_field")
    assert result == 42


def test_get_value_from_object_missing_attr():
    from app.core.services.route_calibration_service import RouteCalibrationService

    class Plain:
        pass

    result = RouteCalibrationService._get_value(Plain(), "nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# match_sefer_to_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_sefer_to_path_missing_sefer():
    from app.core.services.route_calibration_service import RouteCalibrationService

    uow = _make_uow(sefer=None)
    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=999)

    assert result["status"] == "skipped"
    assert result["matches"] is False
    assert result["error_code"] == "MISSING_TRIP_CONTEXT"


@pytest.mark.asyncio
async def test_match_sefer_to_path_missing_rota_detay():
    from app.core.services.route_calibration_service import RouteCalibrationService

    sefer = _make_sefer(rota_detay=None, guzergah_id=10)
    uow = _make_uow(sefer=sefer)
    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=1)

    assert result["status"] == "skipped"
    assert result["error_code"] == "MISSING_TRIP_CONTEXT"


@pytest.mark.asyncio
async def test_match_sefer_to_path_missing_guzergah_id():
    from app.core.services.route_calibration_service import RouteCalibrationService

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]}, guzergah_id=None
    )
    uow = _make_uow(sefer=sefer)
    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=1)

    assert result["status"] == "skipped"
    assert result["error_code"] == "MISSING_TRIP_CONTEXT"


@pytest.mark.asyncio
async def test_match_sefer_to_path_no_calibration():
    from app.core.services.route_calibration_service import RouteCalibrationService

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
        guzergah_id=5,
    )
    uow = _make_uow(sefer=sefer)
    # session.execute returns None calibration
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    uow.session.execute = AsyncMock(return_value=mock_result)

    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=1)

    assert result["status"] == "not_calibrated"
    assert result["error_code"] == "CALIBRATION_MISSING"
    assert result["target_lokasyon_id"] == 5


@pytest.mark.asyncio
async def test_match_sefer_to_path_calibration_no_path():
    from app.core.services.route_calibration_service import RouteCalibrationService

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
        guzergah_id=5,
    )
    uow = _make_uow(sefer=sefer)

    # Calibration exists but hedef_path is None
    calibration = MagicMock()
    calibration.hedef_path = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = calibration
    uow.session.execute = AsyncMock(return_value=mock_result)

    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=1)

    assert result["status"] == "not_calibrated"
    assert result["error_code"] == "CALIBRATION_MISSING"


@pytest.mark.asyncio
async def test_match_sefer_to_path_missing_coordinates():
    from app.core.services.route_calibration_service import RouteCalibrationService

    sefer = _make_sefer(
        rota_detay={"coordinates": []},  # empty coordinates
        guzergah_id=5,
    )
    uow = _make_uow(sefer=sefer)

    calibration = MagicMock()
    calibration.hedef_path = b"some_wkb_data"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = calibration
    uow.session.execute = AsyncMock(return_value=mock_result)

    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=1)

    assert result["status"] == "verification_unavailable"
    assert result["error_code"] == "TRIP_COORDINATES_MISSING"


@pytest.mark.asyncio
async def test_match_sefer_to_path_with_coordinates():
    from app.core.services.route_calibration_service import RouteCalibrationService

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1], [30.0, 42.0]]},
        guzergah_id=5,
    )
    uow = _make_uow(sefer=sefer)

    calibration = MagicMock()
    calibration.hedef_path = b"some_wkb_data"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = calibration
    uow.session.execute = AsyncMock(return_value=mock_result)

    svc = RouteCalibrationService(uow)
    result = await svc.match_sefer_to_path(sefer_id=1)

    assert result["status"] == "verification_unavailable"
    assert result["error_code"] == "SPATIAL_VERIFICATION_NOT_IMPLEMENTED"
    assert result["sefer_id"] == 1


# ---------------------------------------------------------------------------
# get_calibration_for_lokasyon
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_calibration_for_lokasyon_returns_none_when_not_found():
    from app.core.services.route_calibration_service import RouteCalibrationService

    uow = _make_uow()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    uow.session.execute = AsyncMock(return_value=mock_result)

    svc = RouteCalibrationService(uow)
    result = await svc.get_calibration_for_lokasyon(lokasyon_id=99)
    assert result is None


@pytest.mark.asyncio
async def test_get_calibration_for_lokasyon_returns_record():
    from app.core.services.route_calibration_service import RouteCalibrationService

    uow = _make_uow()
    fake_cal = MagicMock()
    fake_cal.lokasyon_id = 7
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_cal
    uow.session.execute = AsyncMock(return_value=mock_result)

    svc = RouteCalibrationService(uow)
    result = await svc.get_calibration_for_lokasyon(lokasyon_id=7)
    assert result is fake_cal


# ---------------------------------------------------------------------------
# calibrate_route_from_trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calibrate_route_raises_without_shapely():
    from app.core.services import route_calibration_service as mod

    orig_line = mod.LineString
    orig_from = mod.from_shape
    try:
        mod.LineString = None
        mod.from_shape = None
        uow = _make_uow()
        svc = mod.RouteCalibrationService(uow)
        with pytest.raises(RuntimeError, match="shapely"):
            await svc.calibrate_route_from_trip(sefer_id=1)
    finally:
        mod.LineString = orig_line
        mod.from_shape = orig_from


@pytest.mark.asyncio
async def test_calibrate_route_returns_false_missing_sefer():
    from app.core.services import route_calibration_service as mod

    if mod.LineString is None:
        pytest.skip("shapely not installed")

    uow = _make_uow(sefer=None)
    svc = mod.RouteCalibrationService(uow)
    result = await svc.calibrate_route_from_trip(sefer_id=999)
    assert result is False


@pytest.mark.asyncio
async def test_calibrate_route_returns_false_insufficient_coords():
    from app.core.services import route_calibration_service as mod

    if mod.LineString is None:
        pytest.skip("shapely not installed")

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0]]},  # only 1 point
        guzergah_id=5,
    )
    uow = _make_uow(sefer=sefer)
    svc = mod.RouteCalibrationService(uow)
    result = await svc.calibrate_route_from_trip(sefer_id=1)
    assert result is False


@pytest.mark.asyncio
async def test_calibrate_route_creates_new_calibration():
    from app.core.services import route_calibration_service as mod

    if mod.LineString is None:
        pytest.skip("shapely not installed")

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1], [30.0, 42.0]]},
        guzergah_id=5,
    )
    uow = _make_uow(sefer=sefer)

    # No existing calibration
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    uow.session.execute = AsyncMock(return_value=mock_result)
    uow.session.add = MagicMock()

    fake_line = MagicMock()
    fake_geom = b"wkb_bytes"

    # Mock shapely LineString and from_shape
    with (
        patch.object(mod, "LineString", return_value=fake_line),
        patch.object(mod, "from_shape", return_value=fake_geom),
    ):
        svc = mod.RouteCalibrationService(uow)
        result = await svc.calibrate_route_from_trip(sefer_id=1)

    assert result is True
    uow.commit.assert_awaited_once()
    uow.session.add.assert_called_once()


@pytest.mark.asyncio
async def test_calibrate_route_updates_existing_calibration():
    from app.core.services import route_calibration_service as mod

    if mod.LineString is None:
        pytest.skip("shapely not installed")

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
        guzergah_id=3,
    )
    uow = _make_uow(sefer=sefer)

    existing_calibration = MagicMock()
    existing_calibration.match_count = 5

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_calibration
    uow.session.execute = AsyncMock(return_value=mock_result)
    uow.session.add = MagicMock()

    fake_geom = b"updated_wkb"

    with (
        patch.object(mod, "LineString", return_value=MagicMock()),
        patch.object(mod, "from_shape", return_value=fake_geom),
    ):
        svc = mod.RouteCalibrationService(uow)
        result = await svc.calibrate_route_from_trip(sefer_id=2)

    assert result is True
    assert existing_calibration.match_count == 1  # reset to 1
    uow.commit.assert_awaited_once()
    # No add — existing record was updated
    uow.session.add.assert_not_called()


@pytest.mark.asyncio
async def test_calibrate_route_updates_lokasyon_object():
    from app.core.services import route_calibration_service as mod

    if mod.LineString is None:
        pytest.skip("shapely not installed")

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
        guzergah_id=3,
    )

    # Lokasyon as object (not dict)
    fake_lokasyon = MagicMock()

    uow = _make_uow(sefer=sefer, lokasyon=fake_lokasyon)

    existing_calibration = MagicMock()
    existing_calibration.match_count = 0

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_calibration
    uow.session.execute = AsyncMock(return_value=mock_result)

    fake_geom = b"wkb"

    with (
        patch.object(mod, "LineString", return_value=MagicMock()),
        patch.object(mod, "from_shape", return_value=fake_geom),
    ):
        svc = mod.RouteCalibrationService(uow)
        result = await svc.calibrate_route_from_trip(sefer_id=2)

    assert result is True


@pytest.mark.asyncio
async def test_calibrate_route_updates_lokasyon_dict():
    from app.core.services import route_calibration_service as mod

    if mod.LineString is None:
        pytest.skip("shapely not installed")

    sefer = _make_sefer(
        rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
        guzergah_id=3,
    )
    # Lokasyon as dict
    fake_lokasyon = {"id": 3, "rota_geom": None}

    uow = _make_uow(sefer=sefer, lokasyon=fake_lokasyon)

    existing_calibration = MagicMock()
    existing_calibration.match_count = 0

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_calibration
    uow.session.execute = AsyncMock(return_value=mock_result)

    fake_geom = b"wkb"

    with (
        patch.object(mod, "LineString", return_value=MagicMock()),
        patch.object(mod, "from_shape", return_value=fake_geom),
    ):
        svc = mod.RouteCalibrationService(uow)
        result = await svc.calibrate_route_from_trip(sefer_id=2)

    assert result is True
    # AUDIT-068: rota_geom artık dict mutasyonu ile DEĞİL, SQL UPDATE ile kalıcılaşır
    # (dict mutasyonu sessizce kayboluyordu — no-op). UPDATE çağrısı doğrulanır.
    geom_updates = [
        call
        for call in uow.session.execute.call_args_list
        if "rota_geom" in str(call.args[0])
    ]
    assert geom_updates, "rota_geom için SQL UPDATE bekleniyordu"


# ---------------------------------------------------------------------------
# _get_sefer — get vs get_by_id dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_sefer_uses_get_by_id_when_available():
    from app.core.services.route_calibration_service import RouteCalibrationService

    uow = _make_uow()
    fake_sefer = MagicMock()
    uow.sefer_repo.get_by_id = AsyncMock(return_value=fake_sefer)

    svc = RouteCalibrationService(uow)
    result = await svc._get_sefer(1)
    assert result is fake_sefer
