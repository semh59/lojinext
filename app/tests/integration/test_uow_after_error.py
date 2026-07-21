"""
T5-C: sefer_repo.add() IntegrityError sonrası UoW geçerli kalmalı.

Bug Açıklaması:
  IntegrityError'dan sonra aynı UoW'da işlem yapılamıyor.
  UoW state bozuluyor (session closed veya dirty).

Beklenen: IntegrityError sonrası başka işlem yapılabilmeli (rollback veya recover).
"""

from datetime import date

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.infrastructure.security.pii_encryption import blind_index
from v2.modules.driver.public import Sofor
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


@pytest.mark.integration
async def test_uow_usable_after_integrity_error(db_session, sefer_repo):
    """
    IntegrityError sonrası aynı UoW'da başka işlem yapılabilmeli.
    """

    # Araç ve şoför oluştur
    arac_result = await db_session.execute(
        insert(Arac).values(
            plaka="99 UOW 001",
            marka="Test",
            model="Model",
            yil=2020,
            aktif=True,
            bos_agirlik_kg=5000.0,
        )
    )
    arac_id = arac_result.inserted_primary_key[0]

    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Test Şoför UoW",
            ad_soyad_bidx=blind_index("Test Şoför UoW"),
            telefon="0532 000 00 05",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=1.0,
            manual_score=1.0,
            hiz_disiplin_skoru=1.0,
            agresif_surus_faktoru=1.0,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    # Test: UoW'da duplicate sefer oluştur (hata), sonra başka işlem yap
    async with UnitOfWork() as uow:
        # 1. İlk sefer - başarılı
        try:
            await uow.sefer_repo.add(
                arac_id=arac_id,
                sofor_id=sofor_id,
                tarih=date.today(),
                cikis_yeri="Istanbul",
                varis_yeri="Ankara",
                mesafe_km=400.0,
                durum="Completed",
                net_kg=10000,
                bos_agirlik_kg=5000,
                dolu_agirlik_kg=15000,
                flat_distance_km=400.0,
            )
            await uow.commit()
        except Exception:
            await uow.session.rollback()

        # 2. Geçersiz FK (var olmayan arac_id) → IntegrityError beklenir.
        #    (seferler'de duplicate'i engelleyen unique constraint yok; UoW'nun
        #    bir integrity hatasından sonra kullanılabilir kaldığını test ediyoruz.)
        try:
            await uow.sefer_repo.add(
                arac_id=999999,
                sofor_id=sofor_id,
                tarih=date.today(),
                cikis_yeri="Istanbul",
                varis_yeri="Ankara",
                mesafe_km=400.0,
                durum="Completed",
                net_kg=10000,
                bos_agirlik_kg=5000,
                dolu_agirlik_kg=15000,
                flat_distance_km=400.0,
            )
            await uow.commit()
            assert False, "Should have raised IntegrityError"
        except IntegrityError:
            await uow.session.rollback()

        # 3. IntegrityError'dan sonra başka işlem yapılabilmeli
        # UoW'da arac bilgisi getir
        try:
            arac = await uow.arac_repo.get_by_id(arac_id)
            assert arac is not None, (
                "T5-C: IntegrityError'dan sonra UoW kullanılmıyor. "
                "Sorun: sefer_repo.add() IntegrityError'ı session'ı corrupt ediyor."
            )
        except Exception as e:
            assert False, (
                f"T5-C: UoW işlemler sonra başarısız. Error: {type(e).__name__}: {e}"
            )
