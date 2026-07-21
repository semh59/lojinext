import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import Anomaly, Sofor
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.trip.public import SeferORM as Sefer


@pytest.mark.asyncio
async def test_anomaly_severity_rejects_invalid_value(db_session):
    """
    2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 15): `Anomaly.severity`
    kritik bir enum-benzeri kolondu ama DB seviyesinde CHECK kısıtı yoktu —
    typo'lu bir değer (örn. "hihg") hiç engellenmiyordu. Artık
    `check_anomaly_severity_enum` CHECK kısıtı var.
    """
    bad = Anomaly(
        tarih=date.today(),
        tip="tuketim",
        kaynak_tip="arac",
        kaynak_id=1,
        deger=10.0,
        beklenen_deger=5.0,
        sapma_yuzde=100.0,
        severity="hihg",  # typo — geçersiz değer
        aciklama="test",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.flush()


async def test_anomaly_severity_accepts_valid_values(db_session):
    for sev in ("low", "medium", "high", "critical"):
        a = Anomaly(
            tarih=date.today(),
            tip="tuketim",
            kaynak_tip="arac",
            kaynak_id=1,
            deger=10.0,
            beklenen_deger=5.0,
            sapma_yuzde=100.0,
            severity=sev,
            aciklama="test",
        )
        db_session.add(a)
        await db_session.flush()


@pytest.mark.asyncio
async def test_sefer_onay_durumu_rejects_invalid_value(db_session):
    """Aynı çelişki `Sefer.onay_durumu` için de vardı — artık
    `check_sefer_onay_durumu_enum` CHECK kısıtı var."""
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="OnayCheckTest")
    sofor = Sofor(ad_soyad="Onay Check Test", ehliyet_sinifi="E")
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
        onay_durumu="approved",  # geçersiz değer (İngilizce, yanlış typo)
    )
    db_session.add(sefer)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.flush()


async def test_sefer_onay_durumu_accepts_null_and_valid_values(db_session):
    plaka = f"34TST{uuid.uuid4().hex[:6].upper()}"
    arac = Arac(plaka=plaka, marka="Test", model="OnayCheckTest2")
    sofor = Sofor(ad_soyad="Onay Check Test2", ehliyet_sinifi="E")
    db_session.add_all([arac, sofor])
    await db_session.flush()

    for durum in (None, "beklemede", "onaylandi", "reddedildi"):
        sefer = Sefer(
            arac_id=arac.id,
            sofor_id=sofor.id,
            tarih=date.today(),
            mesafe_km=100,
            cikis_yeri="A",
            varis_yeri="B",
            baslangic_km=1000,
            bitis_km=1100,
            onay_durumu=durum,
        )
        db_session.add(sefer)
        await db_session.flush()
