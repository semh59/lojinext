"""Runtime-config okuma yolunun gerçek-DB testleri (runtime-config epiği).

Kanıtlanan davranış: sistem_konfig satırı SERVİS DAVRANIŞINI gerçekten
değiştiriyor (epiğin varlık sebebi — daha önce UI'daki değerin hiçbir
etkisi yoktu). Mock yok: gerçek DB satırı + gerçek redis cache.
"""

import pytest
from sqlalchemy import text

from app.core.services.anomaly_detection_service import AnomalyDetectionService
from app.core.services.anomaly_detector import AnomalyDetector
from app.core.services.runtime_config import get_runtime_float
from app.infrastructure.cache.redis_cache import get_redis_cache

pytestmark = pytest.mark.unit


async def _set_config_row(db_session, key: str, deger_json: str) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO sistem_konfig (anahtar, deger, tip, grup, yeniden_baslat)
            VALUES (:k, CAST(:v AS jsonb), 'number', 'anomali', FALSE)
            ON CONFLICT (anahtar) DO UPDATE SET deger = EXCLUDED.deger
            """
        ),
        {"k": key, "v": deger_json},
    )
    await db_session.commit()
    # KonfigService redis'te 1 saat cache'ler; testte taze okumaya zorla.
    get_redis_cache().delete(f"config:val:{key}")


async def _delete_config_row(db_session, key: str) -> None:
    await db_session.execute(
        text("DELETE FROM sistem_konfig WHERE anahtar = :k"), {"k": key}
    )
    await db_session.commit()
    get_redis_cache().delete(f"config:val:{key}")


async def test_get_runtime_float_reads_db_row(db_session):
    await _set_config_row(db_session, "ANOMALY_Z_THRESHOLD", "4.2")
    assert await get_runtime_float("ANOMALY_Z_THRESHOLD", 2.5) == 4.2


async def test_get_runtime_float_falls_back_when_row_missing(db_session):
    await _delete_config_row(db_session, "ANOMALY_Z_THRESHOLD")
    assert await get_runtime_float("ANOMALY_Z_THRESHOLD", 2.5) == 2.5


async def test_get_runtime_float_falls_back_on_non_numeric(db_session):
    await _set_config_row(db_session, "ANOMALY_Z_THRESHOLD", '"bozuk"')
    assert await get_runtime_float("ANOMALY_Z_THRESHOLD", 2.5) == 2.5


async def test_detect_anomalies_behavior_follows_db_threshold(db_session):
    """Epiğin asıl kanıtı: UI'dan (DB'den) değişen eşik, tespiti değiştirir.

    Örneklem: 10×30.0 + tek 45.0 → outlier z-skoru ≈ 3.3.
    Eşik 99 → anomali YOK; eşik 1.0 → outlier anomali. (use_iqr=False:
    IQR yolu z-eşiğinden bağımsız, kanıtı bulandırmasın.)
    """
    service = AnomalyDetectionService()
    consumptions = [30.0] * 10 + [45.0]

    await _set_config_row(db_session, "ANOMALY_Z_THRESHOLD", "99")
    tolerant = await service.detect_anomalies(consumptions, use_iqr=False)
    assert tolerant == []

    await _set_config_row(db_session, "ANOMALY_Z_THRESHOLD", "1.0")
    sensitive = await service.detect_anomalies(consumptions, use_iqr=False)
    assert any(r.value == 45.0 for r in sensitive)


async def test_anomaly_detector_consumption_anomalies_follows_db_threshold(
    db_session,
):
    """S2 Görev 1: AnomalyDetector.detect_consumption_anomalies eşiği artık
    Z_THRESHOLD class-attr (import-time frozen) yerine runtime_config'ten
    async boundary'de çözülüyor. Bu, DB satırındaki değerin gerçekten
    kullanıldığının kanıtı — detect_consumption_anomalies confirmed
    (z_anomalies AND iqr_anomalies) gerektirdiğinden, veri seti hem
    IQR hem Z açısından outlier üretecek şekilde seçildi (10x30.0 + 1x45.0
    -> IQR bounds tam 30.0'da daralır, z-skoru ~3.3).
    """
    detector = AnomalyDetector()
    consumptions = [30.0] * 10 + [45.0]

    await _set_config_row(db_session, "ANOMALY_Z_THRESHOLD", "99")
    tolerant = await detector.detect_consumption_anomalies(consumptions, arac_id=1)
    assert tolerant == []

    await _set_config_row(db_session, "ANOMALY_Z_THRESHOLD", "1.0")
    sensitive = await detector.detect_consumption_anomalies(consumptions, arac_id=1)
    assert any(r.deger == 45.0 for r in sensitive)
