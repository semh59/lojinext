"""Fuel (yakit) soft-delete guard tests — real DB, no mocked UoW.

2026-07-01 prod-grade denetiminde bulunan bug: `update_yakit`, hedef kaydı
`yakit_repo.get_by_id(yakit_id, for_update=True)` ile çekip sadece `if not
current: return False` kontrolü yapıyordu; get_by_id soft-delete filtresiz
olduğu için soft-deleted (aktif=False) bir yakıt alım kaydı `aktif`
kontrolsüz düzenlenebiliyordu (fiyat/litre/toplam_tutar). Kök neden
düzeltmesiyle (BaseRepository.get_by_id varsayılan soft-delete filtresi) bu
dosya doğrulanır — ek servis-seviyesi kod değişikliği gerekmedi.

`delete_yakit` (hard-delete) ise tam tersi yönde: soft-deleted bir kaydın da
kalıcı olarak silinebilmesi GEREKİR — bu yüzden orada `include_inactive=True`
eklendi (bkz. v2/modules/fuel/application/delete_yakit.py). Bu dosya o
davranışı da doğrular.

Dalga 4 (B.1 free-function refactor): YakitService class deleted — use-cases
are free functions in v2/modules/fuel/application/.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import insert, select

from app.core.entities.models import YakitUpdate
from app.database.models import Arac, YakitAlimi
from v2.modules.fuel.application.delete_yakit import delete_yakit
from v2.modules.fuel.application.update_yakit import update_yakit

pytestmark = pytest.mark.integration


async def _seed_arac(db_session, plaka: str) -> int:
    res = await db_session.execute(
        insert(Arac).values(plaka=plaka, marka="Mercedes", model="Actros", aktif=True)
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _seed_yakit(db_session, arac_id: int, *, aktif: bool = True) -> int:
    res = await db_session.execute(
        insert(YakitAlimi).values(
            arac_id=arac_id,
            tarih=date(2026, 6, 1),
            fiyat_tl=Decimal("45.50"),
            litre=Decimal("200.00"),
            toplam_tutar=Decimal("9100.00"),
            km_sayac=150000,
            aktif=aktif,
        )
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _get_yakit(db_session, yakit_id: int):
    return (
        await db_session.execute(select(YakitAlimi).where(YakitAlimi.id == yakit_id))
    ).scalar_one_or_none()


class TestYakitServiceSoftDeleteGuard:
    async def test_update_yakit_rejects_passive_record(self, db_session):
        arac_id = await _seed_arac(db_session, "34 YKT 001")
        yakit_id = await _seed_yakit(db_session, arac_id, aktif=False)

        success = await update_yakit(yakit_id, YakitUpdate(fiyat_tl=Decimal("99.99")))

        assert success is False
        row = await _get_yakit(db_session, yakit_id)
        assert row.fiyat_tl == Decimal("45.50")  # untouched

    async def test_update_yakit_active_record_succeeds(self, db_session):
        arac_id = await _seed_arac(db_session, "34 YKT 002")
        yakit_id = await _seed_yakit(db_session, arac_id, aktif=True)

        success = await update_yakit(
            yakit_id, YakitUpdate(fiyat_tl=Decimal("50.00"), litre=200.0)
        )

        assert success is True
        row = await _get_yakit(db_session, yakit_id)
        assert row.fiyat_tl == Decimal("50.00")

    async def test_delete_yakit_hard_deletes_already_passive_record(self, db_session):
        """Hard-delete, soft-deleted (aktif=False) bir kaydı da silebilmeli
        (aksi halde kayıt sonsuza dek "limbo" durumda kalır)."""
        arac_id = await _seed_arac(db_session, "34 YKT 003")
        yakit_id = await _seed_yakit(db_session, arac_id, aktif=False)

        success = await delete_yakit(yakit_id)

        assert success is True
        assert await _get_yakit(db_session, yakit_id) is None
