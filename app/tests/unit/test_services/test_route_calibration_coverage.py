"""Tests for app/core/services/route_calibration_service.py.

De-mocked to the real test DB for every path that does NOT write PostGIS
geometry: the service constructs a real ``UnitOfWork`` (whose session is the
conftest-monkeypatched test session), reads real seeded Sefer / Lokasyon /
GuzergahKalibrasyon rows, and we assert the real status dicts / returned records
instead of asserting on mocked inner calls.

Geometry-storage boundary (documented, not a shortcut): the ``hedef_path``
column has NO portable representation across the suite's two schema variants.
When the full suite runs (CI), root ``tests/conftest.py`` injects
``geoalchemy2.Geometry = MockGeometry`` (get_col_spec → ``TEXT``) and mocks
``geoalchemy2.shape``, so ``hedef_path`` is a TEXT column that binds **str**;
when only ``app/tests`` is collected, ``app/tests/conftest.py`` swaps the real
geometry type for ``LargeBinary`` (no PostGIS in the DB), so it binds **bytes**.
No single seed value satisfies both, so any test that needs a *stored, truthy*
``hedef_path`` cannot be portably real-DB tested. Those tests — the two
coordinate-branch checks that require an existing calibration path, plus the
four ``calibrate_route_from_trip`` write tests (which also call the mocked
``from_shape`` and a PostGIS-only ``ST_SetSRID`` UPDATE that would poison the
async transaction) — keep a controlled UoW double. Every real-DB test below
seeds only NULL / absent ``hedef_path``, so it passes in BOTH schema variants.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.route_calibration_service import RouteCalibrationService
from app.database.models import GuzergahKalibrasyon
from app.database.unit_of_work import UnitOfWork
from app.tests._helpers.seed import seed_arac, seed_lokasyon, seed_sefer, seed_sofor

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Real-DB seed helpers
# ---------------------------------------------------------------------------


async def _seed_trip(db_session, *, rota_detay, guzergah_id):
    """Seed arac + sofor + sefer (real rows) and commit. Returns the Sefer."""
    arac = await seed_arac(db_session, plaka="34RC001")
    sofor = await seed_sofor(db_session, ad_soyad="RC Sofor")
    sefer = await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        guzergah_id=guzergah_id,
        rota_detay=rota_detay,
    )
    await db_session.commit()
    return sefer


async def _seed_calibration(db_session, *, lokasyon_id, hedef_path):
    cal = GuzergahKalibrasyon(
        lokasyon_id=lokasyon_id,
        buffer_meters=250.0,
        hedef_path=hedef_path,  # LargeBinary in the non-PostGIS test DB
    )
    db_session.add(cal)
    await db_session.commit()
    return cal


# ---------------------------------------------------------------------------
# _get_value static method (pure, no DB)
# ---------------------------------------------------------------------------


def test_get_value_from_dict():
    assert RouteCalibrationService._get_value({"key": "val"}, "key") == "val"


def test_get_value_from_dict_missing():
    assert RouteCalibrationService._get_value({}, "missing_key") is None


def test_get_value_from_object():
    class Obj:
        some_field = 42

    assert RouteCalibrationService._get_value(Obj(), "some_field") == 42


def test_get_value_from_object_missing_attr():
    class Plain:
        pass

    assert RouteCalibrationService._get_value(Plain(), "nonexistent") is None


# ---------------------------------------------------------------------------
# match_sefer_to_path — real DB
# ---------------------------------------------------------------------------


class TestMatchSeferToPath:
    async def test_missing_sefer(self, db_session):
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=999
            )
        assert result["status"] == "skipped"
        assert result["matches"] is False
        assert result["error_code"] == "MISSING_TRIP_CONTEXT"

    async def test_missing_rota_detay(self, db_session):
        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        sefer = await _seed_trip(db_session, rota_detay=None, guzergah_id=lok.id)

        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=sefer.id
            )
        assert result["status"] == "skipped"
        assert result["error_code"] == "MISSING_TRIP_CONTEXT"

    async def test_missing_guzergah_id(self, db_session):
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
            guzergah_id=None,
        )
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=sefer.id
            )
        assert result["status"] == "skipped"
        assert result["error_code"] == "MISSING_TRIP_CONTEXT"

    async def test_no_calibration(self, db_session):
        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
            guzergah_id=lok.id,
        )
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=sefer.id
            )
        assert result["status"] == "not_calibrated"
        assert result["error_code"] == "CALIBRATION_MISSING"
        assert result["target_lokasyon_id"] == lok.id

    async def test_calibration_no_path(self, db_session):
        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
            guzergah_id=lok.id,
        )
        await _seed_calibration(db_session, lokasyon_id=lok.id, hedef_path=None)

        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=sefer.id
            )
        assert result["status"] == "not_calibrated"
        assert result["error_code"] == "CALIBRATION_MISSING"


# ---------------------------------------------------------------------------
# get_calibration_for_lokasyon — real DB
# ---------------------------------------------------------------------------


class TestGetCalibrationForLokasyon:
    async def test_returns_none_when_not_found(self, db_session):
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).get_calibration_for_lokasyon(
                lokasyon_id=99
            )
        assert result is None

    async def test_returns_record(self, db_session):
        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        # hedef_path left NULL — portable across both schema variants (see module
        # docstring). This test only asserts the row is fetched, not its geometry.
        await _seed_calibration(db_session, lokasyon_id=lok.id, hedef_path=None)

        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).get_calibration_for_lokasyon(
                lokasyon_id=lok.id
            )
        assert result is not None
        assert result.lokasyon_id == lok.id
        assert result.buffer_meters == 250.0


# ---------------------------------------------------------------------------
# calibrate_route_from_trip — early returns (real DB) + missing dependency
# ---------------------------------------------------------------------------


class TestCalibrateRouteEarlyReturns:
    async def test_raises_without_shapely(self, db_session):
        """Missing optional dependency → RuntimeError (no DB write reached)."""
        from app.core.services import route_calibration_service as mod

        orig_line, orig_from = mod.LineString, mod.from_shape
        try:
            mod.LineString = None
            mod.from_shape = None
            async with UnitOfWork() as uow:
                with pytest.raises(RuntimeError, match="shapely"):
                    await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                        sefer_id=1
                    )
        finally:
            mod.LineString, mod.from_shape = orig_line, orig_from

    async def test_returns_false_missing_sefer(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")
        async with UnitOfWork() as uow:
            result = await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=999
            )
        assert result is False

    async def test_returns_false_insufficient_coords(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0]]},  # only 1 point
            guzergah_id=None,
        )
        async with UnitOfWork() as uow:
            result = await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=sefer.id
            )
        assert result is False


# ---------------------------------------------------------------------------
# _get_sefer dispatch — real DB
# ---------------------------------------------------------------------------


class TestGetSefer:
    async def test_returns_seeded_sefer(self, db_session):
        sefer = await _seed_trip(db_session, rota_detay=None, guzergah_id=None)
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow)._get_sefer(sefer.id)
        assert result is not None
        assert RouteCalibrationService._get_value(result, "id") == sefer.id


# ===========================================================================
# calibrate_route_from_trip — geometry WRITE path.
#
# PostGIS boundary: see module docstring. The dev/CI DB has no PostGIS, so the
# ST_SetSRID(:geom::geometry) UPDATE would poison the async transaction and
# break commit(). These four write-path tests keep a controlled UoW double to
# exercise the new-vs-existing / match_count / add-vs-update branch logic; the
# shapely geometry encoding (from_shape) is patched because it produces a
# WKBElement that only a PostGIS column can store.
# ===========================================================================


def _make_uow(sefer=None, lokasyon=None):
    """UnitOfWork-like double for the PostGIS-bound write path only."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()

    mock_uow.sefer_repo = AsyncMock()
    mock_uow.sefer_repo.get_by_id = AsyncMock(return_value=sefer)
    mock_uow.lokasyon_repo = AsyncMock()
    mock_uow.lokasyon_repo.get_by_id = AsyncMock(return_value=lokasyon)

    mock_uow.session = AsyncMock()
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


class TestMatchSeferToPathStoredCalibration:
    """Coordinate-branch checks that require an EXISTING calibration whose
    hedef_path is truthy. A stored truthy geometry is not portable across the
    two schema variants (TEXT vs bytea), so these use an in-memory UoW double
    (no DB binding). See module docstring."""

    async def test_missing_coordinates(self, db_session):
        sefer = _make_sefer(rota_detay={"coordinates": []}, guzergah_id=5)
        uow = _make_uow(sefer=sefer)
        calibration = MagicMock()
        calibration.hedef_path = b"stored_geom"  # in-memory only, never bound to DB
        cal_result = MagicMock()
        cal_result.scalar_one_or_none.return_value = calibration
        uow.session.execute = AsyncMock(return_value=cal_result)

        result = await RouteCalibrationService(uow).match_sefer_to_path(sefer_id=1)
        assert result["status"] == "verification_unavailable"
        assert result["error_code"] == "TRIP_COORDINATES_MISSING"

    async def test_with_coordinates(self, db_session):
        sefer = _make_sefer(
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1], [30.0, 42.0]]},
            guzergah_id=5,
        )
        uow = _make_uow(sefer=sefer)
        calibration = MagicMock()
        calibration.hedef_path = b"stored_geom"
        cal_result = MagicMock()
        cal_result.scalar_one_or_none.return_value = calibration
        uow.session.execute = AsyncMock(return_value=cal_result)

        result = await RouteCalibrationService(uow).match_sefer_to_path(sefer_id=1)
        assert result["status"] == "verification_unavailable"
        assert result["error_code"] == "SPATIAL_VERIFICATION_NOT_IMPLEMENTED"
        assert result["sefer_id"] == 1


class TestCalibrateRouteWritePath:
    async def test_creates_new_calibration(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")

        sefer = _make_sefer(
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1], [30.0, 42.0]]},
            guzergah_id=5,
        )
        uow = _make_uow(sefer=sefer)
        with (
            patch.object(mod, "LineString", return_value=MagicMock()),
            patch.object(mod, "from_shape", return_value=b"wkb_bytes"),
        ):
            result = await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=1
            )
        assert result is True
        uow.commit.assert_awaited_once()
        uow.session.add.assert_called_once()

    async def test_updates_existing_calibration(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")

        sefer = _make_sefer(
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]}, guzergah_id=3
        )
        uow = _make_uow(sefer=sefer)
        existing = MagicMock()
        existing.match_count = 5
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing
        uow.session.execute = AsyncMock(return_value=existing_result)

        with (
            patch.object(mod, "LineString", return_value=MagicMock()),
            patch.object(mod, "from_shape", return_value=b"updated_wkb"),
        ):
            result = await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=2
            )
        assert result is True
        assert existing.match_count == 1  # reset to 1
        uow.commit.assert_awaited_once()
        uow.session.add.assert_not_called()

    async def test_updates_lokasyon_object(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")

        sefer = _make_sefer(
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]}, guzergah_id=3
        )
        uow = _make_uow(sefer=sefer, lokasyon=MagicMock())
        existing = MagicMock()
        existing.match_count = 0
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing
        uow.session.execute = AsyncMock(return_value=existing_result)

        with (
            patch.object(mod, "LineString", return_value=MagicMock()),
            patch.object(mod, "from_shape", return_value=b"wkb"),
        ):
            result = await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=2
            )
        assert result is True

    async def test_updates_lokasyon_dict_attempts_geom_update(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")

        sefer = _make_sefer(
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]}, guzergah_id=3
        )
        uow = _make_uow(sefer=sefer, lokasyon={"id": 3, "rota_geom": None})
        existing = MagicMock()
        existing.match_count = 0
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing
        uow.session.execute = AsyncMock(return_value=existing_result)

        with (
            patch.object(mod, "LineString", return_value=MagicMock()),
            patch.object(mod, "from_shape", return_value=b"wkb"),
        ):
            result = await mod.RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=2
            )
        assert result is True
        # AUDIT-068: rota_geom persists via SQL UPDATE (not silent dict mutation).
        geom_updates = [
            call
            for call in uow.session.execute.call_args_list
            if "rota_geom" in str(call.args[0])
        ]
        assert geom_updates, "rota_geom için SQL UPDATE bekleniyordu"
