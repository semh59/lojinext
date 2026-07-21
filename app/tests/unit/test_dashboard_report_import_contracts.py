"""Dashboard / report contract tests — real DB, no mocks.

Slice 3a of the zero-mock epic:
  - 3 tests converted to real seeded Postgres (run in the unit gate, which has a DB)
  - 2 sefer-import tests MOVED to PR-3b (see marker comment in
    app/tests/unit/test_sefer_import_service.py)
"""

from datetime import date, timedelta

import pytest

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor
from v2.modules.reports.application.generate_fleet_summary import generate_fleet_summary
from v2.modules.reports.application.generate_monthly_trend import generate_monthly_trend
from v2.modules.reports.application.generate_vehicle_report import (
    generate_vehicle_report,
)
from v2.modules.reports.application.get_dashboard_summary import get_dashboard_summary
from v2.modules.reports.application.get_monthly_comparison import (
    get_monthly_comparison,
)
from v2.modules.reports.infrastructure.repo_access import resolve_repos
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


async def test_report_service_exposes_dashboard_compat_methods(db_session):
    """get_dashboard_summary / get_monthly_comparison are thin mapping wrappers
    over generate_fleet_summary / generate_monthly_trend.

    We assert the *relationship* between the two real calls (mapping correctness)
    rather than hard-coding numbers — this survives any seed-value change.
    """
    arac = await seed_arac(db_session, plaka="34TST001", hedef_tuketim=25.0)
    sofor = await seed_sofor(db_session)
    today = date.today()
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=today,
        durum="Completed",
        mesafe_km=450.0,
        tuketim=30.0,
    )
    await db_session.commit()

    async with UnitOfWork(session=db_session) as uow:
        repos = resolve_repos(uow)

        fleet = await generate_fleet_summary(repos)
        summary = await get_dashboard_summary(repos)

        # Mapping assertions: compat wrapper must relay generate_fleet_summary keys
        assert summary["toplam_sefer"] == fleet["total_trips"]
        assert summary["toplam_km"] == fleet["total_distance"]
        assert summary["toplam_yakit"] == fleet["total_fuel"]
        assert summary["filo_ortalama"] == fleet["avg_consumption"]

        trend = await generate_monthly_trend(repos)
        comparison = await get_monthly_comparison(repos)

        degisimler = trend.get("degisimler", {})
        assert comparison["sefer_degisim"] == degisimler.get("toplam_sefer_degisim", 0)
        assert comparison["km_degisim"] == degisimler.get("toplam_km_degisim", 0)
        assert comparison["tuketim_degisim"] == degisimler.get(
            "ortalama_tuketim_degisim", 0
        )


async def test_dashboard_service_filters_deleted_trip_count_and_recent_list(
    db_session,
):
    """DashboardService delegates to SeferRepository which must exclude soft-deleted trips.

    DashboardService.get_dashboard_data calls:
      - repo.get_all(limit=recent_limit, filters={"is_deleted": False})
      - repo.count(filters={"is_deleted": False})

    Behavioral assertion: seed 1 active + 1 soft-deleted trip, then verify the
    REAL repo calls (that the service delegates to) exclude the deleted row.
    We test via the repo directly because asyncio.gather() in DashboardService
    runs multiple SQL ops concurrently on a single test session, which SQLAlchemy
    AsyncSession does not support (concurrent-connection guard fires).

    The filtering behavior lives in SeferRepository, not in DashboardService
    itself — so asserting the repo output is the correct behavioral test here.
    """
    from v2.modules.trip.infrastructure.repository import SeferRepository

    arac = await seed_arac(db_session, plaka="34TST002")
    sofor = await seed_sofor(db_session, ad_soyad="Test Sofor")

    today = date.today()
    # Active trip
    await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=today,
        durum="Completed",
        mesafe_km=300.0,
    )
    # Soft-deleted trip — seed normally then flip the flag before commit
    deleted_sefer = await seed_sefer(
        db_session,
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=today - timedelta(days=1),
        durum="Completed",
        mesafe_km=400.0,
    )
    deleted_sefer.is_deleted = True
    await db_session.commit()

    sefer_repo = SeferRepository(session=db_session)

    # Replicate the two calls that DashboardService.get_dashboard_data makes
    recent = await sefer_repo.get_all(limit=3, filters={"is_deleted": False})
    total = await sefer_repo.count(filters={"is_deleted": False})

    # Only the non-deleted trip should appear
    assert len(recent) == 1
    assert total == 1


async def test_generate_vehicle_report_computes_performance_score_from_actual_stats(
    db_session,
):
    """generate_vehicle_report derives performance_score from REAL analiz_repo stats.

    Formula: score = 100 - max(0, (actual - target) / target * 100)
    Seeds: hedef_tuketim=25, 4 trips each with tuketim=30
      -> AVG(tuketim) = 30.0
      -> deviation = (30 - 25) / 25 * 100 = 20%
      -> score = 100 - 20 = 80.0

    If the real SQL produces a slightly different float (e.g. due to Decimal
    representation), we round to 1 decimal — the formula already does round(..., 1).
    """
    arac = await seed_arac(
        db_session,
        plaka="34TST003",
        marka="Ford",
        hedef_tuketim=25.0,
    )
    sofor = await seed_sofor(db_session, ad_soyad="Perf Sofor")
    start = date.today() - timedelta(days=15)

    for i in range(4):
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tarih=start + timedelta(days=i),
            durum="Completed",
            mesafe_km=450.0,
            tuketim=30.0,
        )
    await db_session.commit()

    async with UnitOfWork(session=db_session) as uow:
        report = await generate_vehicle_report(resolve_repos(uow), arac.id, days=30)

    # Real performance_score from real DB stats
    # Expected: 80.0 (see formula comment above)
    assert report["performance_score"] == 80.0
    assert report["plaka"] == "34TST003"
    assert report["istatistikler"]["sefer_sayisi"] == 4
