"""SoforService.update_sofor soft-delete guard tests — real DB, no mocked UoW.

2026-07-01 prod-grade denetiminde bulunan bug: `update_sofor`'un manual_score
dalında sadece `get_by_id`'nin truthy sonucu skor yeniden hesabını
tetikliyordu, ama `uow.sofor_repo.update(sofor_id, **kwargs)` çağrısı bu
kontrolden bağımsız her koşulda çalışıyordu — soft-deleted (aktif=False) bir
şoförün manual_score'u sessizce güncellenebiliyordu. Fix: metodun başına
reaktivasyon-farkında bir varlık/aktiflik guard'ı eklendi (bkz.
arac_service._update_arac_impl için aynı desen).
"""

import pytest
from sqlalchemy import insert, select

from app.core.services.sofor_service import SoforService
from app.database.models import Sofor

pytestmark = pytest.mark.unit


async def _seed_sofor(db_session, ad_soyad: str, *, aktif: bool = True) -> int:
    res = await db_session.execute(
        insert(Sofor).values(
            ad_soyad=ad_soyad, aktif=aktif, manual_score=1.0, score=1.0
        )
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _get_sofor(db_session, sofor_id: int):
    return (
        await db_session.execute(select(Sofor).where(Sofor.id == sofor_id))
    ).scalar_one_or_none()


def _service() -> SoforService:
    return SoforService()


class TestSoforServiceSoftDeleteGuard:
    async def test_update_sofor_rejects_manual_score_change_on_passive_driver(
        self, db_session
    ):
        sofor_id = await _seed_sofor(db_session, "Pasif Soför Test", aktif=False)

        success = await _service().update_sofor(sofor_id, manual_score=1.8)

        assert success is False
        row = await _get_sofor(db_session, sofor_id)
        assert float(row.manual_score) == 1.0  # untouched

    async def test_update_sofor_allows_explicit_reactivation(self, db_session):
        sofor_id = await _seed_sofor(db_session, "Reaktive Soför Test", aktif=False)

        success = await _service().update_sofor(sofor_id, aktif=True, manual_score=1.5)

        assert success is True
        row = await _get_sofor(db_session, sofor_id)
        assert row.aktif is True
        assert float(row.manual_score) == 1.5

    async def test_update_sofor_active_driver_unaffected(self, db_session):
        sofor_id = await _seed_sofor(db_session, "Aktif Soför Test", aktif=True)

        success = await _service().update_sofor(sofor_id, manual_score=1.3)

        assert success is True
        row = await _get_sofor(db_session, sofor_id)
        assert float(row.manual_score) == 1.3

    async def test_update_score_rejects_passive_driver(self, db_session):
        sofor_id = await _seed_sofor(db_session, "Pasif Skor Test", aktif=False)

        with pytest.raises(ValueError, match="not found"):
            await _service().update_score(sofor_id, 1.7)
