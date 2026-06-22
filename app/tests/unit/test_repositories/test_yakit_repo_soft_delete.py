"""
T1-C: yakit_repo.get_son_km() soft-delete filtresi.
T1-D: yakit_repo.get_stats() silinmiş sefer mesafesi dahil edilmemeli.

Bug Kontrol: Soft-delete filtresi doğru uygulanıyor mu?
"""

from datetime import date

import pytest
from sqlalchemy import insert

from app.database.models import Arac, Sefer, Sofor, YakitAlimi

pytestmark = pytest.mark.integration


@pytest.mark.integration
async def test_get_son_km_excludes_inactive(db_session, yakit_repo):
    """T1-C: get_son_km() pasif yakıt kayıtlarını dışlamalı."""

    # Araç oluştur
    arac_result = await db_session.execute(
        insert(Arac).values(
            plaka="99 YAK C01",
            marka="Test",
            model="Model",
            yil=2020,
            aktif=True,
            bos_agirlik_kg=5000.0,
        )
    )
    arac_id = arac_result.inserted_primary_key[0]

    # Aktif yakıt alımı (DÖNMELİ)
    await db_session.execute(
        insert(YakitAlimi).values(
            arac_id=arac_id,
            tarih=date.today(),
            istasyon="Shell",
            fiyat_tl=10.0,
            litre=50.0,
            km_sayac=150000,
            toplam_tutar=500.0,
            aktif=True,
        )
    )

    # Pasif yakıt alımı (DIŞLANMALI)
    await db_session.execute(
        insert(YakitAlimi).values(
            arac_id=arac_id,
            tarih=date.today(),
            istasyon="Opet",
            fiyat_tl=10.0,
            litre=60.0,
            km_sayac=200000,
            toplam_tutar=600.0,
            aktif=False,
        )
    )

    await db_session.commit()

    # TEST: get_son_km en yüksek aktif km'yi döndürmeli
    result = await yakit_repo.get_son_km(arac_id=arac_id)

    assert result == 150000, (
        f"T1-C: get_son_km() pasif yakıt kaydını dahil ediyor. "
        f"Beklenen: 150000 (aktif), Aldık: {result}"
    )


@pytest.mark.integration
async def test_get_stats_excludes_deleted_seferler(db_session, yakit_repo):
    """T1-D: get_stats() silinmiş seferlerin mesafesini dahil etmemeli."""

    # Araç oluştur
    arac_result = await db_session.execute(
        insert(Arac).values(
            plaka="99 YAK D01",
            marka="Test",
            model="Model",
            yil=2020,
            aktif=True,
            bos_agirlik_kg=5000.0,
        )
    )
    arac_id = arac_result.inserted_primary_key[0]

    # Şoför oluştur
    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Test Şoför D",
            telefon="0532 000 00 04",
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

    # Aktif sefer (MESAFE SAYILMALI)
    await db_session.execute(
        insert(Sefer).values(
            arac_id=arac_id,
            sofor_id=sofor_id,
            tarih=date.today(),
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=400.0,
            durum="Completed",
            is_deleted=False,
            tuketim=30.0,
            bos_agirlik_kg=5000,
            dolu_agirlik_kg=15000,
            net_kg=10000,  # dolu - bos = 15000 - 5000 = 10000 ✓
            flat_distance_km=400.0,
        )
    )

    # Silinmiş sefer (MESAFE SAYILMAMALI)
    await db_session.execute(
        insert(Sefer).values(
            arac_id=arac_id,
            sofor_id=sofor_id,
            tarih=date.today(),
            cikis_yeri="Ankara",
            varis_yeri="Izmir",
            mesafe_km=500.0,
            durum="Completed",
            is_deleted=True,  # Silinmiş
            tuketim=32.0,
            bos_agirlik_kg=5000,
            dolu_agirlik_kg=15000,
            net_kg=10000,  # dolu - bos = 15000 - 5000 = 10000 ✓
            flat_distance_km=500.0,
        )
    )

    # Aktif yakıt alımı
    await db_session.execute(
        insert(YakitAlimi).values(
            arac_id=arac_id,
            tarih=date.today(),
            istasyon="Shell",
            fiyat_tl=10.0,
            litre=120.0,  # 400km için 30 L/100km = 120L
            km_sayac=400,
            toplam_tutar=1200.0,
            aktif=True,
        )
    )

    await db_session.commit()

    # TEST: get_stats() mesafe toplamı sadece aktif seferlerden hesaplanmalı
    stats = await yakit_repo.get_stats()

    # Beklenen: 400 km (sadece aktif sefer), silinmiş 500 km sayılmamış
    assert stats["total_distance"] == 400.0, (
        f"T1-D: get_stats() silinmiş sefer mesafesini dahil ediyor. "
        f"Beklenen: 400.0 (sadece aktif), Aldık: {stats['total_distance']}"
    )

    # L/100km kontrol: 120L / 400km * 100 = 30 L/100km
    expected_consumption = (120.0 / 400.0) * 100
    assert abs(stats["avg_consumption"] - expected_consumption) < 0.01, (
        f"L/100km hesaplaması yanlış. "
        f"Beklenen: {expected_consumption}, Aldık: {stats['avg_consumption']}"
    )
