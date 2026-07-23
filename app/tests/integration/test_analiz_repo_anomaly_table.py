"""
T1-B: analiz_repo.get_recent_unread_alerts() yanlış kolon adları — satır 388-403.

Bug Açıklaması:
  Fonksiyon queries kolon adları: siddet (yanlış, doğru: severity),
  olusturma_tarihi (yanlış, doğru: created_at), okundu (yanlış, hiç yok).
  Exception sessizce catch ediliyor → [] dönüyor.
  Sonuç: AI context'e boş veri gidiyor.

Beklenen: get_recent_unread_alerts() anomali kayıtlarını dönmeli.
"""

from datetime import date

import pytest
from sqlalchemy import insert

from v2.modules.anomaly.public import Anomaly


@pytest.mark.integration
async def test_get_recent_unread_alerts_returns_anomalies(db_session, analiz_repo):
    """
    get_recent_unread_alerts() anomali tablosundan veri almalı.
    Kolon adları yanlış (siddet→severity, olusturma_tarihi→created_at, okundu yok) → [] dönüyor (BUG).
    """

    # Setup: anomalies tablosuna anomali kayıtları ekle
    now = date.today()

    # Raw SQL insert (ORM kullanmaktan kaçın)
    await db_session.execute(
        insert(Anomaly).values(
            tarih=now,
            tip="FUEL_OVERCONSUMPTION",
            kaynak_tip="sefer",
            kaynak_id=999,
            deger=45,
            beklenen_deger=30,
            sapma_yuzde=50,
            severity="high",
            aciklama="Fuel consumption too high",
        )
    )

    await db_session.execute(
        insert(Anomaly).values(
            tarih=now,
            tip="LATE_DELIVERY",
            kaynak_tip="sofor",
            kaynak_id=888,
            deger=150,
            beklenen_deger=120,
            sapma_yuzde=25,
            severity="medium",
            aciklama="Delivery delayed",
        )
    )

    # Üçüncü anomali
    await db_session.execute(
        insert(Anomaly).values(
            tarih=now,
            tip="MAINTENANCE_DUE",
            kaynak_tip="arac",
            kaynak_id=777,
            deger=5,
            beklenen_deger=10,
            sapma_yuzde=50,
            severity="low",
            aciklama="Maintenance due soon",
        )
    )

    await db_session.commit()

    # TEST: get_recent_unread_alerts
    results = await analiz_repo.get_recent_unread_alerts(limit=10)

    assert len(results) >= 3, (
        f"BUG T1-B: get_recent_unread_alerts() veri dönmüyor. "
        f"Beklenen: >=3 anomali, Aldık: {len(results)}. "
        f"Sorun: analiz_repo.py:388-403 satırlarında kolon adları yanlış (siddet, olusturma_tarihi, okundu). "
        f"Doğru: severity, created_at kullanılmalı; okundu kolon'u yok."
    )


@pytest.mark.integration
async def test_get_recent_unread_alerts_limit(db_session, analiz_repo):
    """Limit parametresi saygı gösterilmeli."""

    now = date.today()

    # 10 anomali oluştur
    for i in range(10):
        await db_session.execute(
            insert(Anomaly).values(
                tarih=now,
                tip=f"TYPE_{i}",
                kaynak_tip=f"type_{i}",
                kaynak_id=1000 + i,
                deger=float(i),
                beklenen_deger=float(i + 1),
                sapma_yuzde=float(i * 10),
                severity="high" if i % 2 == 0 else "medium",
                aciklama=f"Anomaly {i}",
            )
        )

    await db_session.commit()

    # Test limit=3
    results_3 = await analiz_repo.get_recent_unread_alerts(limit=3)
    assert len(results_3) == 3, f"limit=3: beklenen 3, aldık {len(results_3)}"

    # Test limit=20
    results_20 = await analiz_repo.get_recent_unread_alerts(limit=20)
    assert len(results_20) >= 10, (
        f"limit=20: en az 10 anomali dönmesi beklendi, aldık {len(results_20)}"
    )
