"""
T1-A regression guard: sefer_repo.get_trip_stats() durum filtresi.

Veri canonical İngilizce ('Planned'/'Completed'/'Cancelled') saklanır.
get_trip_stats() legacy Türkçe girişi normalize_sefer_status ile canonical'a
çevirir; bu test hem filtrenin uygulandığını hem de normalizasyonu doğrular
(Türkçe input → İngilizce stored eşleşmesi).
"""

import pytest
from sqlalchemy import text

from v2.modules.platform_infra.security.pii_encryption import blind_index, encrypt_pii


@pytest.mark.integration
async def test_get_trip_stats_respects_durum_filter(db_session, sefer_repo):
    """
    get_trip_stats() durum filtresi uygulanmıyor.
    3 Tamamlandı + 2 Planlandı sefer olduğunda:
    - durum="Tamamlandı" → 3 dönmeli, şu anda 5 dönüyor (BUG)
    """

    # Test data insert (raw SQL, conftest hazırlanmış db_session kulllanıyor)
    # Vehicle oluştur
    vehicle = await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, model, yil, aktif) "
            "VALUES ('99 BUG 001', 'Test', 'Model', 2020, true) "
            "RETURNING id"
        )
    )
    vehicle_id = vehicle.scalar()

    # Driver oluştur
    driver = await db_session.execute(
        text(
            "INSERT INTO soforler (ad_soyad, ad_soyad_bidx, telefon, ise_baslama, ehliyet_sinifi, aktif, score, manual_score, hiz_disiplin_skoru, agresif_surus_faktoru) "  # noqa: E501
            "VALUES (:ad, :ad_bidx, :tel, '2020-01-01', 'E', true, 1.0, 1.0, 1.0, 1.0) "
            "RETURNING id"
        ),
        {
            "ad": encrypt_pii("Test"),
            "ad_bidx": blind_index("Test"),
            "tel": encrypt_pii("5551234567"),
        },
    )
    driver_id = driver.scalar()

    # 3 "Completed" sefer (canonical İngilizce)
    for i in range(3):
        await db_session.execute(
            text(
                "INSERT INTO seferler (arac_id, sofor_id, tarih, cikis_yeri, varis_yeri, mesafe_km, durum, is_deleted, flat_distance_km) "  # noqa: E501
                "VALUES (:a, :d, '2024-01-01', 'Start', 'End', 450, 'Completed', false, 450) "
            ),
            {"a": vehicle_id, "d": driver_id},
        )

    # 2 "Planned" sefer (canonical İngilizce)
    for i in range(2):
        await db_session.execute(
            text(
                "INSERT INTO seferler (arac_id, sofor_id, tarih, cikis_yeri, varis_yeri, mesafe_km, durum, is_deleted, flat_distance_km) "  # noqa: E501
                "VALUES (:a, :d, '2024-01-02', 'Start', 'End', 580, 'Planned', false, 580) "
            ),
            {"a": vehicle_id, "d": driver_id},
        )

    await db_session.commit()

    # TEST: durum="Tamamlandı" filtresi
    stats_completed = await sefer_repo.get_trip_stats(durum="Tamamlandı")

    assert stats_completed["total_count"] == 3, (
        f"BUG T1-A: durum='Tamamlandı' filtresi çalışmıyor. "
        f"Beklenen: 3, Aldık: {stats_completed['total_count']}. "
        f"Sorun: sefer_repo.py:437-469 satırlarında base'deki durum filtresi stats_q'ya uygulanmıyor."
    )

    # TEST: durum="Planlandı" filtresi
    stats_planned = await sefer_repo.get_trip_stats(durum="Planlandı")

    assert stats_planned["total_count"] == 2, (
        f"BUG T1-A: durum='Planlandı' filtresi çalışmıyor. "
        f"Beklenen: 2, Aldık: {stats_planned['total_count']}"
    )

    # TEST: hiç durum filtresi yok (tüm seferler)
    stats_all = await sefer_repo.get_trip_stats()

    assert stats_all["total_count"] == 5, (
        f"Toplam seferler: beklenen 5, aldık {stats_all['total_count']}"
    )
