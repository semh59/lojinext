import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from v2.modules.fleet.public import AracORM as Arac
from v2.modules.fuel.public import YakitAlimiORM as YakitAlimi
from v2.modules.fuel.public import YakitFormul, YakitPeriyot


@pytest.mark.asyncio
async def test_deleting_arac_orm_instance_does_not_silently_cascade_fuel_purchases(
    db_session,
):
    """
    2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 13): `Arac.yakit_alimlari`
    ilişkisi ORM'de `cascade="all, delete-orphan"` taşıyordu, ama DB seviyesinde
    `yakit_alimlari.arac_id` FK'si `ondelete="RESTRICT"`. Şu anki aktif silme
    yolları (`AracService`, `hard_delete` Core-level bulk DELETE) bu çelişkiye
    hiç dokunmuyor — ama biri ileride ORM-seviyeli `session.delete(arac)`
    çağırırsa, ORM cascade DB'nin RESTRICT'ini hiç göremeden finansal kaydı
    (yakıt alımı) sessizce, hiçbir hata vermeden siler.

    Fix: cascade kaldırıldı, `passive_deletes=True` eklendi — ORM artık
    çocuk satırları kendi yönetmiyor, DB'nin RESTRICT'ine bırakıyor. Bu test
    doğrudan ORM-seviyeli `session.delete(arac)` çağırıp finansal kaydın
    KORUNDUĞUNU (IntegrityError ile reddedildiğini) kanıtlıyor.
    """
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="CascadeTest")
    db_session.add(arac)
    await db_session.flush()

    yakit = YakitAlimi(
        arac_id=arac.id,
        tarih=date(2026, 1, 1),
        litre=100,
        fiyat_tl=40,
        toplam_tutar=4000,
        km_sayac=1000,
    )
    db_session.add(yakit)
    await db_session.flush()
    yakit_id = yakit.id

    # SAVEPOINT kullanılıyor: başarısız delete'in rollback'i yalnızca bu
    # savepoint'i geri alsın, testin setup insert'lerini taşıyan dış
    # transaction'ı değil. IntegrityError savepoint'ten dışarı taşınca
    # SQLAlchemy savepoint'i otomatik rollback eder.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(arac)
            await db_session.flush()

    # Financial record must still exist — the DB rejected the parent delete.
    result = await db_session.execute(
        select(YakitAlimi).where(YakitAlimi.id == yakit_id)
    )
    assert result.scalar_one_or_none() is not None, (
        "Yakıt alımı (finansal kayıt) ORM cascade tarafından sessizce "
        "silinmiş — RESTRICT çelişkisi hâlâ mevcut."
    )


@pytest.mark.asyncio
async def test_deleting_arac_orm_instance_does_not_silently_cascade_yakit_periyodu(
    db_session,
):
    """Aynı çelişki `YakitPeriyot.arac_id` için de vardı (RESTRICT + ORM
    delete-orphan). Not: bir periyot her zaman 2 `YakitAlimi` satırına bağımlı
    olduğundan, bu senaryoda IntegrityError zaten `yakit_alimlari`
    korumasından da gelebilir — asıl kesin kanıt aşağıdaki mapper-seviyeli
    `test_yakit_periyotlari_relationship_uses_passive_deletes` testinde."""
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="CascadeTest2")
    db_session.add(arac)
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
    periyot_id = periyot.id

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(arac)
            await db_session.flush()

    result = await db_session.execute(
        select(YakitPeriyot).where(YakitPeriyot.id == periyot_id)
    )
    assert result.scalar_one_or_none() is not None, (
        "Yakıt periyodu ORM cascade tarafından sessizce silinmiş — "
        "RESTRICT çelişkisi hâlâ mevcut."
    )


@pytest.mark.asyncio
async def test_deleting_arac_orm_instance_does_not_silently_cascade_yakit_formul(
    db_session,
):
    """Aynı çelişki `YakitFormul.arac_id` için de vardı (RESTRICT + ORM
    delete-orphan)."""
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="CascadeTest3")
    db_session.add(arac)
    await db_session.flush()

    formul = YakitFormul(arac_id=arac.id, katsayilar={"a": 1.0})
    db_session.add(formul)
    await db_session.flush()
    formul_id = formul.id

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.delete(arac)
            await db_session.flush()

    result = await db_session.execute(
        select(YakitFormul).where(YakitFormul.id == formul_id)
    )
    assert result.scalar_one_or_none() is not None, (
        "Yakıt formülü ORM cascade tarafından sessizce silinmiş — "
        "RESTRICT çelişkisi hâlâ mevcut."
    )


@pytest.mark.parametrize(
    "model,fk_column", [(YakitAlimi, "arac_id"), (YakitPeriyot, "arac_id"), (YakitFormul, "arac_id")]
)
def test_arac_financial_fk_columns_use_db_level_restrict(model, fk_column):
    """Mapper-seviyeli kesin doğrulama (dalga 16 task #58 sonrası güncellendi):
    `Arac.yakit_alimlari`/`.yakit_periyotlari`/`.formul` ORM ``relationship()``'leri
    models.py bölünmesinde KALDIRILDI (Arac fleet'e taşındı, fuel'in
    tablolarına cross-module relationship() ile sızamaz — B.1). Eski test
    ORM mapper cascade config'ini kontrol ediyordu; artık kontrol edilecek
    hiçbir relationship() yok — bu aslında RESTRICT/cascade çelişkisinin en
    kesin çözümü (relationship() hiç olmayınca ORM-seviyeli cascade delete
    riski de yapısal olarak imkânsız). Bu test artık doğrudan FK kolonunun
    DB-seviyeli ``ondelete="RESTRICT"`` taşıdığını doğruluyor — asıl
    korumanın kaynağı budur (yukarıdaki 3 entegrasyon testi bunu ampirik
    olarak zaten kanıtlıyor)."""
    col = model.__table__.columns[fk_column]
    fk = next(iter(col.foreign_keys))
    assert fk.ondelete == "RESTRICT"
