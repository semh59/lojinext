"""
T1-B: analiz_repo.get_recent_unread_alerts() — anomali uyarı akışı.

Gerçek şema: tablo `anomalies` (İngilizce), model `Anomaly`. "Okunmamış" =
`acknowledged_at IS NULL`. Sorgu `kaynak_tip AS title, aciklama AS message,
severity, created_at` döndürür. (BUG-003: kaynakta `FROM anomalier` yazım
hatası `anomalies` olarak düzeltildi.)
"""

from datetime import date, datetime, timezone

import pytest

from v2.modules.anomaly.public import Anomaly


def _anomaly(kaynak_id: int, aciklama: str, *, acknowledged: bool = False) -> Anomaly:
    return Anomaly(
        tarih=date.today(),
        tip="tuketim",
        kaynak_tip="sefer",
        kaynak_id=kaynak_id,
        deger=45.0,
        beklenen_deger=30.0,
        sapma_yuzde=50.0,
        severity="high",
        aciklama=aciklama,
        acknowledged_at=datetime.now(timezone.utc) if acknowledged else None,
    )


@pytest.mark.integration
async def test_get_recent_unread_alerts_returns_data(db_session, analiz_repo):
    """Okunmamış (acknowledged_at IS NULL) anomali uyarıları fetch edilmeli."""
    db_session.add(_anomaly(1, "FUEL_OVERCONSUMPTION"))
    await db_session.commit()

    results = await analiz_repo.get_recent_unread_alerts(limit=5)

    assert len(results) > 0, f"Anomali uyarıları boş döndü. Sonuç: {results}"
    assert results[0].get("message") == "FUEL_OVERCONSUMPTION"


@pytest.mark.integration
async def test_get_recent_unread_alerts_excludes_read(db_session, analiz_repo):
    """Acknowledge edilmiş (okunmuş) anomaliler dışlanmalı."""
    db_session.add(_anomaly(1, "ACKNOWLEDGED_ONE", acknowledged=True))
    db_session.add(_anomaly(2, "LATE_ARRIVAL", acknowledged=False))
    await db_session.commit()

    results = await analiz_repo.get_recent_unread_alerts(limit=10)

    assert len(results) == 1, f"Beklenen 1 okunmamış, aldık {len(results)}: {results}"
    assert results[0].get("message") == "LATE_ARRIVAL"


@pytest.mark.integration
async def test_get_recent_unread_alerts_respects_limit(db_session, analiz_repo):
    """Limit parametresine saygı gösterilmeli."""
    for i in range(10):
        db_session.add(_anomaly(i, f"TYPE_{i}"))
    await db_session.commit()

    results = await analiz_repo.get_recent_unread_alerts(limit=3)
    assert len(results) == 3, f"limit=3 beklendi, aldık {len(results)}"

    results_many = await analiz_repo.get_recent_unread_alerts(limit=20)
    assert len(results_many) == 10, f"10 kayıt beklendi, aldık {len(results_many)}"
