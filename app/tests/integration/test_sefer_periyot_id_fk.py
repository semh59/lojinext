import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import Arac, Sefer, Sofor, YakitAlimi, YakitPeriyot


@pytest.mark.asyncio
async def test_sefer_periyot_id_rejects_orphan_reference(db_session):
    """
    2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 14): `Sefer.periyot_id`
    hiçbir DB-seviyeli FK kısıtı olmayan bir "soft link" idi — orphan
    referanslar engellenmiyordu. Artık `yakit_periyotlari(id)` için gerçek
    bir FK (`ON DELETE SET NULL`) var; var olmayan bir periyot_id ile
    sefer eklemek/güncellemek artık DB'de IntegrityError ile reddedilir.
    """
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="PeriyotFkTest")
    sofor = Sofor(ad_soyad="Periyot Fk Test", ehliyet_sinifi="E")
    db_session.add_all([arac, sofor])
    await db_session.flush()

    sefer = Sefer(
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=date.today(),
        mesafe_km=100,
        cikis_yeri="A",
        varis_yeri="B",
        baslangic_km=1000,
        bitis_km=1100,
        periyot_id=999999999,  # does not exist
    )
    db_session.add(sefer)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.flush()


@pytest.mark.asyncio
async def test_sefer_periyot_id_deleting_periyot_sets_null(db_session):
    """Periyot silindiğinde bağlı sefer'in periyot_id'si ON DELETE SET NULL
    ile otomatik NULL'a düşer, sefer kaydının kendisi etkilenmez."""
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="PeriyotFkTest2")
    sofor = Sofor(ad_soyad="Periyot Fk Test2", ehliyet_sinifi="E")
    db_session.add_all([arac, sofor])
    await db_session.flush()

    alim1 = YakitAlimi(
        arac_id=arac.id,
        tarih=date(2026, 1, 1),
        litre=100,
        fiyat_tl=40,
        toplam_tutar=4000,
        km_sayac=1000,
    )
    alim2 = YakitAlimi(
        arac_id=arac.id,
        tarih=date(2026, 1, 15),
        litre=100,
        fiyat_tl=40,
        toplam_tutar=4000,
        km_sayac=1500,
    )
    db_session.add_all([alim1, alim2])
    await db_session.flush()

    periyot = YakitPeriyot(arac_id=arac.id, alim1_id=alim1.id, alim2_id=alim2.id)
    db_session.add(periyot)
    await db_session.flush()

    sefer = Sefer(
        arac_id=arac.id,
        sofor_id=sofor.id,
        tarih=date.today(),
        mesafe_km=100,
        cikis_yeri="A",
        varis_yeri="B",
        baslangic_km=1000,
        bitis_km=1100,
        periyot_id=periyot.id,
    )
    db_session.add(sefer)
    await db_session.flush()
    sefer_id = sefer.id

    from sqlalchemy import delete

    await db_session.execute(delete(YakitPeriyot).where(YakitPeriyot.id == periyot.id))
    await db_session.flush()

    # `sefer` zaten identity map'te — DB'nin ON DELETE SET NULL sonucu
    # yansısın diye açıkça refresh ediyoruz (aksi halde SQLAlchemy hâlâ
    # önceden yüklenmiş, artık stale olan Python-side değeri döner).
    await db_session.refresh(sefer)
    assert sefer.id == sefer_id
    assert sefer.periyot_id is None
