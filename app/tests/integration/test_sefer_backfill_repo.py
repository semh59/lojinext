"""SeferRepository.get_ids_missing_prediction integration testi."""

from datetime import date

import pytest

from app.database.models import Arac, Lokasyon, Sefer, Sofor
from app.database.repositories.sefer_repo import SeferRepository

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _seed_min(db):
    arac = Arac(
        plaka="34ABC12",
        marka="M",
        model="A",
        yil=2022,
        tank_kapasitesi=600,
        hedef_tuketim=30.0,
        aktif=True,
        bos_agirlik_kg=8000,
    )
    sofor = Sofor(ad_soyad="S1", aktif=True)
    lok = Lokasyon(cikis_yeri="Istanbul", varis_yeri="Ankara", mesafe_km=450.0)
    db.add_all([arac, sofor, lok])
    await db.commit()
    await db.refresh(arac)
    await db.refresh(sofor)
    await db.refresh(lok)
    return arac, sofor, lok


def _base(arac, sofor, lok):
    return dict(
        tarih=date(2026, 6, 1),
        arac_id=arac.id,
        sofor_id=sofor.id,
        guzergah_id=lok.id,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        bos_agirlik_kg=8000,
        dolu_agirlik_kg=23000,
        net_kg=15000,
        durum="Planned",
    )


async def test_returns_only_null_prediction_non_deleted(db_session):
    arac, sofor, lok = await _seed_min(db_session)
    base = _base(arac, sofor, lok)
    s_null = Sefer(**base)
    s_has = Sefer(**{**base, "tahmini_tuketim": 31.2})
    s_deleted = Sefer(**{**base, "is_deleted": True})
    db_session.add_all([s_null, s_has, s_deleted])
    await db_session.commit()
    await db_session.refresh(s_null)
    await db_session.refresh(s_has)
    await db_session.refresh(s_deleted)

    repo = SeferRepository(db_session)
    ids = await repo.get_ids_missing_prediction(limit=100)

    assert s_null.id in ids
    assert s_has.id not in ids
    assert s_deleted.id not in ids


async def test_respects_limit(db_session):
    arac, sofor, lok = await _seed_min(db_session)
    base = _base(arac, sofor, lok)
    db_session.add_all([Sefer(**base) for _ in range(5)])
    await db_session.commit()

    repo = SeferRepository(db_session)
    ids = await repo.get_ids_missing_prediction(limit=3)
    assert len(ids) == 3
