"""Dilim 2: arac_repo.get_all 'acik_ariza' (açık ARIZA/ACIL) sayısını döndürür.

Gerçek DB sorgusunu (correlated subquery) doğrudan test eder — sadece açık
(tamamlanmamış) ARIZA/ACIL sayılır; kapatılanlar ve PERIYODIK sayılmaz.
"""

from datetime import datetime, timezone

import pytest

from app.tests._helpers.seed import seed_arac
from v2.modules.fleet.public import AracBakim, BakimTipi
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


def _bakim(arac_id, tip, *, tamamlandi):
    return AracBakim(
        arac_id=arac_id,
        bakim_tipi=tip,
        km_bilgisi=1000,
        bakim_tarihi=datetime.now(timezone.utc),
        tamamlandi=tamamlandi,
    )


async def test_get_all_counts_only_open_breakdowns(db_session):
    arac = await seed_arac(db_session, plaka="34 OA 001")
    db_session.add_all(
        [
            _bakim(arac.id, BakimTipi.ARIZA, tamamlandi=False),  # sayılır
            _bakim(arac.id, BakimTipi.ACIL, tamamlandi=False),  # sayılır
            _bakim(arac.id, BakimTipi.ARIZA, tamamlandi=True),  # kapalı → sayılmaz
            _bakim(arac.id, BakimTipi.PERIYODIK, tamamlandi=False),  # arıza değil
        ]
    )
    await db_session.commit()

    async with UnitOfWork() as uow:
        rows = await uow.arac_repo.get_all(sadece_aktif=False, limit=500)

    row = next(r for r in rows if r["id"] == arac.id)
    assert row["acik_ariza"] == 2


async def test_get_all_zero_when_no_breakdowns(db_session):
    arac = await seed_arac(db_session, plaka="34 OA 002")
    await db_session.commit()

    async with UnitOfWork() as uow:
        rows = await uow.arac_repo.get_all(sadece_aktif=False, limit=500)

    row = next(r for r in rows if r["id"] == arac.id)
    assert row["acik_ariza"] == 0
