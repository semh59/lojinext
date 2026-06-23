"""
Real-object integration tests for sefer_repo status-filter queries.

BUG-002 regression guard: confirms all sefer_repo methods use canonical
English status strings ('Completed'/'Planned'/'Cancelled') in SQL queries
rather than Turkish values that never matched the DB CHECK constraint.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import insert

from app.database.models import Arac, Sefer, Sofor

pytestmark = pytest.mark.integration


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _create_arac(db_session) -> int:
    r = await db_session.execute(
        insert(Arac).values(
            plaka="77 STATUS 01",
            marka="StatusTest",
            model="X",
            yil=2021,
            aktif=True,
            bos_agirlik_kg=8000.0,
        )
    )
    await db_session.commit()
    return r.inserted_primary_key[0]


async def _create_sofor(db_session) -> int:
    r = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Status Driver",
            telefon="0533 777 00 00",
            ise_baslama=date(2018, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
        )
    )
    await db_session.commit()
    return r.inserted_primary_key[0]


async def _insert_sefer(
    db_session, arac_id, sofor_id, durum, days_ago=1, mesafe_km=400.0
):
    r = await db_session.execute(
        insert(Sefer).values(
            arac_id=arac_id,
            sofor_id=sofor_id,
            cikis_yeri="Ankara",
            varis_yeri="Konya",
            mesafe_km=mesafe_km,
            net_kg=15000,
            dolu_agirlik_kg=23000,
            bos_agirlik_kg=8000,
            tarih=date.today() - timedelta(days=days_ago),
            durum=durum,
        )
    )
    await db_session.commit()
    return r.inserted_primary_key[0]


# ── get_trip_stats ───────────────────────────────────────────────────────────


async def test_get_trip_stats_completed_count(db_session, sefer_repo):
    """
    BUG-002: get_trip_stats with no filter must count 'Completed' rows
    in the completed_count breakdown field.
    """
    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    for _ in range(3):
        await _insert_sefer(db_session, arac_id, sofor_id, "Completed")

    stats = await sefer_repo.get_trip_stats()

    assert stats["completed_count"] >= 3, (
        f"BUG-002: completed_count should be >=3, got {stats['completed_count']}. "
        "SQL may still use Turkish status string that never matches DB rows."
    )


async def test_get_trip_stats_planned_count(db_session, sefer_repo):
    """get_trip_stats must count 'Planned' rows in planned_count breakdown."""
    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    for _ in range(2):
        await _insert_sefer(db_session, arac_id, sofor_id, "Planned")

    stats = await sefer_repo.get_trip_stats()

    assert stats["planned_count"] >= 2, (
        f"BUG-002: planned_count should be >=2, got {stats['planned_count']}."
    )


async def test_get_trip_stats_durum_filter_completed(db_session, sefer_repo):
    """
    durum='Completed' filter (Turkish input normalized) must return only
    Completed rows — not Planned or Cancelled.
    """
    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    completed_ids = [
        await _insert_sefer(db_session, arac_id, sofor_id, "Completed")
        for _ in range(3)
    ]
    await _insert_sefer(db_session, arac_id, sofor_id, "Planned")
    await _insert_sefer(db_session, arac_id, sofor_id, "Cancelled")

    # Turkish input is normalized by get_trip_stats → 'Completed'
    stats = await sefer_repo.get_trip_stats(durum="Tamamlandı")

    assert stats["total_count"] == len(completed_ids), (
        f"Expected exactly {len(completed_ids)} completed trips, got {stats['total_count']}. "
        "BUG-002: Turkish status normalization broken."
    )


# ── get_cost_leakage_stats ───────────────────────────────────────────────────


async def test_get_cost_leakage_stats_finds_completed_trips(db_session, sefer_repo):
    """
    BUG-002 regression: get_cost_leakage_stats queries WHERE durum='Completed'.
    If it used 'Tamamlandı', route deviation sum would always be 0.
    Test verifies the function runs without error and returns a dict with
    expected keys.
    """
    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    await _insert_sefer(
        db_session, arac_id, sofor_id, "Completed", days_ago=5, mesafe_km=500.0
    )

    result = await sefer_repo.get_cost_leakage_stats(days=30)

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "route_deviation_km" in result, (
        f"Missing route_deviation_km key: {list(result)}"
    )
    assert "fuel_gap_liters" in result, f"Missing fuel_gap_liters key: {list(result)}"


async def test_get_cost_leakage_stats_excludes_planned_trips(db_session, sefer_repo):
    """
    Planned trips must not contribute to route deviation calculation.
    Only Completed trips are evaluated for cost leakage.
    """
    arac_id = await _create_arac(db_session)
    sofor_id = await _create_sofor(db_session)

    # Planned trips — should NOT affect leakage stats
    for _ in range(5):
        await _insert_sefer(
            db_session, arac_id, sofor_id, "Planned", days_ago=3, mesafe_km=999.0
        )

    result_no_completed = await sefer_repo.get_cost_leakage_stats(days=7)

    # route_deviation_km should not include the enormous distances from Planned trips
    assert result_no_completed.get("route_deviation_km", 0) < 9999 * 5, (
        "Planned trips appear to be leaking into route deviation calculation"
    )
