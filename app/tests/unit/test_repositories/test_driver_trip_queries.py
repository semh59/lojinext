"""Real-DB tests for v2/modules/driver/infrastructure/driver_trip_queries.py.

``get_by_sofor_id``/``get_with_route_analysis``/``get_driver_trips_with_
route_analysis``/``get_driver_trips_by_route_type`` used to live as
``SeferRepository`` methods (tested with mocks in
``test_sefer_repo_coverage.py``); dalga 14 moved them here as free
functions. 2026-07-22: the old mocked tests were stale (calling
``AttributeError``-raising, no-longer-existent repo methods) — replaced
with real-DB coverage per the 0-mock convention (``db_session`` fixture +
``app/tests/_helpers/seed.py``).
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor
from v2.modules.driver.infrastructure.driver_trip_queries import (
    get_by_sofor_id,
    get_driver_trips_by_route_type,
    get_driver_trips_with_route_analysis,
    get_with_route_analysis,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


class TestGetBySoforId:
    async def test_returns_trips_for_driver_ordered_by_date_desc(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ001")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor 1")
        other_sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Other")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tarih=date.today() - timedelta(days=5),
            sefer_no="DTQ-OLD",
        )
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tarih=date.today(),
            sefer_no="DTQ-NEW",
        )
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=other_sofor.id,
            tarih=date.today(),
            sefer_no="DTQ-OTHER",
        )
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_by_sofor_id(sofor.id, uow=uow)

        assert len(result) == 2
        assert result[0]["sefer_no"] == "DTQ-NEW"
        assert result[1]["sefer_no"] == "DTQ-OLD"

    async def test_filters_by_onay_durumu(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ002")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Onay")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-ONAY-BEK",
            onay_durumu="beklemede",
        )
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-ONAY-OK",
            onay_durumu="onaylandi",
        )
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_by_sofor_id(sofor.id, onay_durumu="onaylandi", uow=uow)

        assert len(result) == 1
        assert result[0]["sefer_no"] == "DTQ-ONAY-OK"

    async def test_empty_when_no_trips(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Empty")
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_by_sofor_id(sofor.id, uow=uow)

        assert result == []


class TestGetWithRouteAnalysis:
    async def test_returns_trips_with_route_analysis_and_consumption(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ003")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Route")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-ROUTE-01",
            mesafe_km=300.0,
            tuketim=35.0,
            rota_detay={"route_analysis": {"type": "highway"}},
        )
        # Missing tuketim -> must be excluded
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-ROUTE-NOTUK",
            rota_detay={"route_analysis": {"type": "city"}},
            tuketim=None,
        )
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_with_route_analysis(days=90, uow=uow)

        assert len(result) == 1
        assert result[0]["mesafe_km"] == 300.0
        assert result[0]["gercek_tuketim"] == 35.0
        assert result[0]["route_analysis"] == {"type": "highway"}

    async def test_rota_detay_fallback_to_whole_dict(self, db_session):
        """If rota_detay has no 'route_analysis' key, the whole dict is used."""
        arac = await seed_arac(db_session, plaka="34DTQ004")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Fallback")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-FALLBACK",
            tuketim=30.0,
            rota_detay={"some_other_key": "value"},
        )
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_with_route_analysis(days=90, uow=uow)

        assert result[0]["route_analysis"] == {"some_other_key": "value"}

    async def test_excludes_old_trips_outside_days_window(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ005")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Old")
        old_sefer = await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-VERY-OLD",
            tuketim=30.0,
            rota_detay={"route_analysis": {}},
        )
        # created_at defaults to now() in seed_sefer; push it outside the window.
        old_sefer.created_at = datetime.now(timezone.utc) - timedelta(days=200)
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_with_route_analysis(days=90, uow=uow)

        assert result == []


class TestGetDriverTripsWithRouteAnalysis:
    async def test_returns_trips_for_driver(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ006")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Drv1")
        other_sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Drv1Other")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-DRV1-A",
            tuketim=34.0,
            tahmini_tuketim=32.0,
            rota_detay={"type": "highway"},
        )
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=other_sofor.id,
            sefer_no="DTQ-DRV1-OTHER",
            tuketim=34.0,
            tahmini_tuketim=32.0,
            rota_detay={"type": "highway"},
        )
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_driver_trips_with_route_analysis(sofor.id, uow=uow)

        assert len(result) == 1
        assert result[0]["gercek_tuketim"] == 34.0
        assert result[0]["tahmini_tuketim"] == 32.0

    async def test_empty_result_when_no_matching_trips(self, db_session):
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Drv1Empty")
        await db_session.commit()

        async with UnitOfWork() as uow:
            result = await get_driver_trips_with_route_analysis(sofor.id, uow=uow)

        assert result == []


class TestGetDriverTripsByRouteType:
    async def test_filters_by_classify_route(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ007")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Drv2")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-DRV2-HWY",
            tuketim=33.0,
            tahmini_tuketim=31.0,
            rota_detay={"route_analysis": {"primary_type": "highway"}},
        )
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-DRV2-CITY",
            tuketim=40.0,
            tahmini_tuketim=38.0,
            rota_detay={"route_analysis": {"primary_type": "city"}},
        )
        await db_session.commit()

        with patch(
            "v2.modules.driver.public.classify_route",
            side_effect=lambda rd: rd.get("primary_type", "city"),
        ):
            async with UnitOfWork() as uow:
                result = await get_driver_trips_by_route_type(
                    sofor.id, route_type="highway", uow=uow
                )

        assert len(result) == 1
        assert result[0]["gercek_tuketim"] == 33.0

    async def test_empty_when_no_matching_type(self, db_session):
        arac = await seed_arac(db_session, plaka="34DTQ008")
        sofor = await seed_sofor(db_session, ad_soyad="DTQ Sofor Drv3")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            sefer_no="DTQ-DRV3-CITY",
            tuketim=33.0,
            tahmini_tuketim=31.0,
            rota_detay={"route_analysis": {"primary_type": "city"}},
        )
        await db_session.commit()

        with patch(
            "v2.modules.driver.public.classify_route",
            return_value="city",
        ):
            async with UnitOfWork() as uow:
                result = await get_driver_trips_by_route_type(
                    sofor.id, route_type="highway", uow=uow
                )

        assert result == []
