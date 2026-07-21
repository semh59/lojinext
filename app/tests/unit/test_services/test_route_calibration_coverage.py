"""Tests for app/core/services/route_calibration_service.py — fully real DB.

Every test runs the service against a real ``UnitOfWork`` (whose session is the
conftest-monkeypatched test session) over real seeded Sefer / Lokasyon /
GuzergahKalibrasyon rows, and asserts the real status dicts / persisted records.

``hedef_path`` is now a plain BYTEA column (``_LINESTRING_TYPE = LargeBinary``):
the previous geoalchemy2 Geometry type bound writes through PostGIS functions
(ST_GeomFromEWKB) that crash without the extension — a real production bug, now
fixed so calibrate_route_from_trip stores raw WKB bytes. Because the column is
bytea in every schema variant, the calibration write path round-trips for real
here, so there is no mocked-UoW boundary left.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.services.route_calibration_service import RouteCalibrationService
from app.tests._helpers.seed import seed_arac, seed_lokasyon, seed_sefer, seed_sofor
from v2.modules.route_simulation.public import GuzergahKalibrasyon
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration
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


# ---------------------------------------------------------------------------
# match_sefer_to_path — with an EXISTING stored calibration (real DB)
#
# hedef_path is now a plain BYTEA column everywhere (the prod fix dropped the
# PostGIS-bound geoalchemy2 type), so a stored calibration round-trips for real.
# ---------------------------------------------------------------------------


class TestMatchSeferToPathStoredCalibration:
    async def test_missing_coordinates(self, db_session):
        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        sefer = await _seed_trip(
            db_session, rota_detay={"coordinates": []}, guzergah_id=lok.id
        )
        await _seed_calibration(db_session, lokasyon_id=lok.id, hedef_path=b"wkb")
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=sefer.id
            )
        assert result["status"] == "verification_unavailable"
        assert result["error_code"] == "TRIP_COORDINATES_MISSING"

    async def test_with_coordinates(self, db_session):
        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1], [30.0, 42.0]]},
            guzergah_id=lok.id,
        )
        await _seed_calibration(db_session, lokasyon_id=lok.id, hedef_path=b"wkb")
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).match_sefer_to_path(
                sefer_id=sefer.id
            )
        assert result["status"] == "verification_unavailable"
        assert result["error_code"] == "SPATIAL_VERIFICATION_NOT_IMPLEMENTED"
        assert result["sefer_id"] == sefer.id


# ---------------------------------------------------------------------------
# calibrate_route_from_trip — real WKB-bytes write (no PostGIS required)
# ---------------------------------------------------------------------------


class TestCalibrateRouteWritePath:
    async def test_creates_new_calibration(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")

        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1], [30.0, 42.0]]},
            guzergah_id=lok.id,
        )
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=sefer.id
            )
        assert result is True
        row = (
            await db_session.execute(
                select(GuzergahKalibrasyon).where(
                    GuzergahKalibrasyon.lokasyon_id == lok.id
                )
            )
        ).scalar_one()
        # Real WKB bytes persisted to the BYTEA column — no PostGIS, no crash.
        assert row.hedef_path is not None
        assert len(bytes(row.hedef_path)) > 0

    async def test_updates_existing_calibration_resets_match_count(self, db_session):
        from app.core.services import route_calibration_service as mod

        if mod.LineString is None:
            pytest.skip("shapely not installed")

        lok = await seed_lokasyon(db_session)
        await db_session.commit()
        db_session.add(
            GuzergahKalibrasyon(
                lokasyon_id=lok.id,
                buffer_meters=250.0,
                match_count=5,
                hedef_path=b"old",
            )
        )
        await db_session.commit()
        sefer = await _seed_trip(
            db_session,
            rota_detay={"coordinates": [[28.9, 41.0], [29.0, 41.1]]},
            guzergah_id=lok.id,
        )
        async with UnitOfWork() as uow:
            result = await RouteCalibrationService(uow).calibrate_route_from_trip(
                sefer_id=sefer.id
            )
        assert result is True
        row = (
            await db_session.execute(
                select(GuzergahKalibrasyon).where(
                    GuzergahKalibrasyon.lokasyon_id == lok.id
                )
            )
        ).scalar_one()
        await db_session.refresh(row)
        assert row.match_count == 1  # reset on recalibration
        assert bytes(row.hedef_path) != b"old"  # path updated
