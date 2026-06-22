"""
T6-A: analiz_repo.get_dashboard_stats() — silinmiş/pasif yakıt dahil edilmemeli.

Bug Açıklaması:
  Dashboard stats'ta is_deleted=True veya aktif=FALSE yakıt sayılıyor.
  Soft-delete filtering eksik.

Beklenen: Sadece aktif yakıt kayıtları toplama dahil edilmeli.
"""

from datetime import date

import pytest
from sqlalchemy import insert


@pytest.mark.integration
async def test_dashboard_stats_excludes_inactive_fuel(db_session, analiz_repo):
    """
    T6-A: Dashboard stats sadece aktif yakıt kayıtlarını saymali.

    Senaryo:
    1. Aktif yakıt kaydı: 50L
    2. Pasif yakıt kaydı (aktif=FALSE): 100L
    3. Silinmiş yakıt kaydı (is_deleted=TRUE): 75L
    4. get_dashboard_stats() → toplam_yakit == 50L (pasif/silinmiş hariç)
    """

    from app.database.models import Arac, YakitAlimi

    # Create a vehicle
    arac_result = await db_session.execute(
        insert(Arac).values(
            plaka="34 DASH 001",
            marka="Test",
            model="Model",
            yil=2020,
            aktif=True,
            bos_agirlik_kg=5000.0,
        )
    )
    arac_id = arac_result.inserted_primary_key[0]
    await db_session.commit()

    # YakitAlimi soft-delete is the single `aktif` flag (no separate is_deleted);
    # both the "inactive" and "deleted" rows map to aktif=False. Only the active
    # row (50 L) must be counted by dashboard stats.
    fuel_data = [
        {"litre": 50.0, "aktif": True, "label": "active"},
        {"litre": 100.0, "aktif": False, "label": "inactive"},
        {"litre": 75.0, "aktif": False, "label": "deleted"},
    ]

    for fuel in fuel_data:
        await db_session.execute(
            insert(YakitAlimi).values(
                arac_id=arac_id,
                tarih=date(2026, 5, 30),
                litre=fuel["litre"],
                fiyat_tl=30,  # > 0 (check constraint)
                toplam_tutar=fuel["litre"] * 30,
                km_sayac=100000,
                aktif=fuel["aktif"],
            )
        )

    await db_session.commit()

    # Get dashboard stats
    try:
        stats = await analiz_repo.get_dashboard_stats()

        # Verify only active fuel is counted
        toplam_yakit = stats.get("toplam_yakit", 0)

        assert toplam_yakit <= 50.5, (
            f"T6-A: Dashboard stats included inactive/deleted fuel. "
            f"Got toplam_yakit={toplam_yakit}, expected <= 50.0. "
            f"Sorun: soft-delete filtering eksik."
        )

        assert toplam_yakit >= 49.5, (
            f"T6-A: Dashboard stats didn't count active fuel correctly. "
            f"Got toplam_yakit={toplam_yakit}, expected ~50.0."
        )

    except Exception as e:
        assert False, (
            f"T6-A: get_dashboard_stats() raised exception: {e}. "
            f"Stats calculation failed."
        )
