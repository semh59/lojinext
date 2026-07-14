"""Verify write endpoints return {success: True, ...} not {status: 'success', ...}"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


async def test_vehicle_delete_returns_success_true():
    """DELETE vehicle: {success: True, message: ...} olmalı."""
    from v2.modules.fleet.api import vehicle_routes as v_mod

    mock_user = MagicMock()

    with patch.object(v_mod, "delete_vehicle", AsyncMock(return_value=True)):
        result = await v_mod.delete_arac(
            arac_id=1,
            current_admin=mock_user,
        )

    assert isinstance(result, dict), f"Dict beklendi, geldi: {type(result)}"
    assert "success" in result, f"'success' key beklendi, geldi: {result}"
    assert result.get("success") is True, f"success=True beklendi, geldi: {result}"
    assert "status" not in result, f"Eski format 'status' key hâlâ var: {result}"


async def test_vehicle_clear_all_returns_success_true():
    """DELETE /clear-all: {success: True, message: ...} olmalı."""
    from v2.modules.fleet.api import vehicle_routes as v_mod

    mock_user = MagicMock()

    with patch.object(v_mod, "delete_all_vehicles", AsyncMock(return_value=5)):
        result = await v_mod.clear_all_vehicles(
            current_admin=mock_user,
        )

    assert isinstance(result, dict), f"Dict beklendi, geldi: {type(result)}"
    assert "success" in result, f"'success' key beklendi, geldi: {result}"
    assert result.get("success") is True, f"success=True beklendi, geldi: {result}"
    assert "status" not in result, f"Eski format 'status' key hâlâ var: {result}"


async def test_vehicle_upload_returns_success_true():
    """POST /upload: {success: True, message: ..., errors: [...]} olmalı."""
    from unittest.mock import patch as stdlib_patch

    from v2.modules.fleet.api import vehicle_routes as v_mod

    mock_import_service = AsyncMock()
    mock_import_service.process_vehicle_import = AsyncMock(return_value=(3, []))
    mock_user = MagicMock()

    mock_file = MagicMock()
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    mock_file.filename = "test.xlsx"
    mock_file.size = 100
    # Simulate chunked read: first call returns data, second returns empty bytes
    mock_file.read = AsyncMock(side_effect=[b"fakecontent", b""])

    with stdlib_patch(
        "app.core.services.import_service.get_import_service",
        return_value=mock_import_service,
    ):
        result = await v_mod.upload_vehicles(
            current_admin=mock_user,
            file=mock_file,
        )

    assert isinstance(result, dict), f"Dict beklendi, geldi: {type(result)}"
    assert "success" in result, f"'success' key beklendi, geldi: {result}"
    assert result.get("success") is True, f"success=True beklendi, geldi: {result}"
    assert "status" not in result, f"Eski format 'status' key hâlâ var: {result}"


async def test_driver_upload_returns_success_true():
    """POST /excel/upload: {success: True, message: ..., errors: [...]} olmalı."""
    from unittest.mock import patch as stdlib_patch

    from v2.modules.driver.api import driver_routes as d_mod

    mock_import_service = AsyncMock()
    mock_import_service.process_driver_import = AsyncMock(return_value=(2, []))
    mock_user = MagicMock()

    mock_file = MagicMock()
    mock_file.content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    mock_file.read = AsyncMock(return_value=b"fakecontent")

    with stdlib_patch(
        "app.core.services.import_service.get_import_service",
        return_value=mock_import_service,
    ):
        result = await d_mod.upload_drivers(
            current_admin=mock_user,
            file=mock_file,
        )

    assert isinstance(result, dict), f"Dict beklendi, geldi: {type(result)}"
    assert "success" in result, f"'success' key beklendi, geldi: {result}"
    assert result.get("success") is True, f"success=True beklendi, geldi: {result}"
    assert "status" not in result, f"Eski format 'status' key hâlâ var: {result}"


async def test_driver_delete_returns_success_true():
    """DELETE /{sofor_id}: {success: True, message: ...} olmalı."""
    from v2.modules.driver.api import driver_routes as d_mod

    mock_user = MagicMock()

    mock_sofor = MagicMock()
    mock_sofor.aktif = True
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_sofor)

    # NOT: eski DI-injected `service=` kwarg'ı kaldırıldı — SoforService
    # sınıfı silindi (dalga 5, B.1 free-function refactor); route artık
    # module-level import edilen delete_sofor_usecase'i doğrudan çağırıyor.
    with patch.object(d_mod, "delete_sofor_usecase", AsyncMock(return_value=True)):
        result = await d_mod.delete_sofor(
            sofor_id=1,
            db=mock_db,
            current_admin=mock_user,
        )

    assert isinstance(result, dict), f"Dict beklendi, geldi: {type(result)}"
    assert "success" in result, f"'success' key beklendi, geldi: {result}"
    assert result.get("success") is True, f"success=True beklendi, geldi: {result}"
    assert "status" not in result, f"Eski format 'status' key hâlâ var: {result}"


async def test_calibration_returns_success_true(db_session):
    """POST calibrate/{sefer_id}: {success: True, message: ...} olmalı (real DB)."""
    from unittest.mock import AsyncMock as AM
    from unittest.mock import patch as stdlib_patch

    from app.api.v1.endpoints import admin_calibration as cal_mod

    mock_service_instance = AM()
    mock_service_instance.calibrate_route_from_trip = AM(return_value=True)

    with stdlib_patch.object(
        cal_mod, "RouteCalibrationService", return_value=mock_service_instance
    ):
        result = await cal_mod.calibrate_route_from_trip(sefer_id=1, db=db_session)

    assert isinstance(result, dict), f"Dict beklendi, geldi: {type(result)}"
    assert "success" in result, f"'success' key beklendi, geldi: {result}"
    assert result.get("success") is True, f"success=True beklendi, geldi: {result}"
    assert "status" not in result, f"Eski format 'status' key hâlâ var: {result}"
