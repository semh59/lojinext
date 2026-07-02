"""
Real-object integration tests for cashflow_projector.project_cashflow.

BUG-002 regression guard: cashflow_projector queries seferler with
durum = 'Planned' (English canonical). Before the fix it used 'Planlandı'
(Turkish) which never matched — projected fuel was always 0.

These tests use a real DB session and no mocks.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import insert

from app.database.models import Arac, Sefer, Sofor
from app.infrastructure.security.pii_encryption import blind_index

pytestmark = pytest.mark.integration


async def _insert_arac(db_session) -> int:
    r = await db_session.execute(
        insert(Arac).values(
            plaka="99 CASH 01",
            marka="Cash",
            model="Test",
            yil=2022,
            aktif=True,
            bos_agirlik_kg=8000.0,
        )
    )
    await db_session.commit()
    return r.inserted_primary_key[0]


async def _insert_sofor(db_session) -> int:
    r = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Cash Driver",
            ad_soyad_bidx=blind_index("Cash Driver"),
            telefon="0532 999 00 00",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
        )
    )
    await db_session.commit()
    return r.inserted_primary_key[0]


async def _insert_sefer(
    db_session, arac_id, sofor_id, durum, tahmini_tuketim=None, days_ahead=1
):
    tarih = date.today() + timedelta(days=days_ahead)
    r = await db_session.execute(
        insert(Sefer).values(
            arac_id=arac_id,
            sofor_id=sofor_id,
            cikis_yeri="Ankara",
            varis_yeri="Istanbul",
            mesafe_km=450.0,
            net_kg=18000,
            dolu_agirlik_kg=26000,
            bos_agirlik_kg=8000,
            tarih=tarih,
            durum=durum,
            tahmini_tuketim=tahmini_tuketim,
        )
    )
    await db_session.commit()
    return r.inserted_primary_key[0]


async def test_project_cashflow_counts_planned_trips(db_session):
    """
    BUG-002 regression: project_cashflow must find 'Planned' trips.
    If the SQL uses Turkish 'Planlandı', fuel_rows is empty → weeks all 0.
    """
    from app.core.services.cashflow_projector import project_cashflow
    from app.database.unit_of_work import UnitOfWork

    arac_id = await _insert_arac(db_session)
    sofor_id = await _insert_sofor(db_session)

    # 3 Planned trips with known tahmini_tuketim
    for i in range(1, 4):
        await _insert_sefer(
            db_session, arac_id, sofor_id, "Planned", tahmini_tuketim=30.0, days_ahead=i
        )

    async with UnitOfWork() as uow:
        result = await project_cashflow(uow, horizon_days=30, diesel_price_tl=50.0)

    total_fuel = sum(w.fuel_tl for w in result.weeks)
    assert total_fuel > 0, (
        "BUG-002: project_cashflow returned 0 total fuel for 3 Planned trips — "
        "SQL may still use 'Planlandı' instead of 'Planned'"
    )


async def test_project_cashflow_excludes_completed_trips(db_session):
    """
    Completed and Cancelled trips must NOT contribute to the fuel projection
    (they're in the past or abandoned).
    """
    from app.core.services.cashflow_projector import project_cashflow
    from app.database.unit_of_work import UnitOfWork

    arac_id = await _insert_arac(db_session)
    sofor_id = await _insert_sofor(db_session)

    # Completed trips in the future (edge case) — should not be projected
    for i in range(1, 4):
        await _insert_sefer(
            db_session,
            arac_id,
            sofor_id,
            "Completed",
            tahmini_tuketim=999.0,
            days_ahead=i,
        )

    async with UnitOfWork() as uow:
        result_completed_only = await project_cashflow(
            uow, horizon_days=30, diesel_price_tl=50.0
        )

    total_fuel_completed = sum(w.fuel_tl for w in result_completed_only.weeks)

    # Now add a Planned trip with a distinct value
    await _insert_sefer(
        db_session, arac_id, sofor_id, "Planned", tahmini_tuketim=50.0, days_ahead=1
    )

    async with UnitOfWork() as uow:
        result_with_planned = await project_cashflow(
            uow, horizon_days=30, diesel_price_tl=50.0
        )

    total_with_planned = sum(w.fuel_tl for w in result_with_planned.weeks)

    assert total_with_planned > total_fuel_completed, (
        "Adding a Planned trip must increase projected fuel (Completed trips must be excluded)"
    )


async def test_project_cashflow_returns_cashflow_projection(db_session):
    """
    project_cashflow must return a CashflowProjection dataclass with
    .weeks, .horizon_days, and .assumptions attributes.
    """
    from app.core.services.cashflow_projector import (
        CashflowProjection,
        project_cashflow,
    )
    from app.database.unit_of_work import UnitOfWork

    async with UnitOfWork() as uow:
        result = await project_cashflow(uow, horizon_days=14, diesel_price_tl=48.0)

    assert isinstance(result, CashflowProjection)
    assert result.horizon_days == 14
    assert isinstance(result.weeks, list)
    assert len(result.weeks) > 0
    assert hasattr(result, "assumptions")
