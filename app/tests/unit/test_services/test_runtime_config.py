"""Runtime-config okuma yolunun gerçek-DB testleri (runtime-config epiği).

Kanıtlanan davranış: sistem_konfig satırı SERVİS DAVRANIŞINI gerçekten
değiştiriyor (epiğin varlık sebebi — daha önce UI'daki değerin hiçbir
etkisi yoktu). Mock yok: gerçek DB satırı + gerçek redis cache.
"""

from datetime import date

import pytest
from sqlalchemy import text

from app.infrastructure.cache.redis_cache import get_redis_cache
from v2.modules.admin_platform.application.runtime_config import get_runtime_float
from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector
from v2.modules.prediction_ml.domain.physics_model import build_vehicle_specs

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


async def test_vehicle_age_degradation_rate_db_row_read(db_session):
    """S2 Görev 2 — DB okuma yolu: get_runtime_float DB satırını gerçekten
    okur (KonfigService -> sistem_konfig -> redis cache invalidation)."""
    await _set_config_row(db_session, "VEHICLE_AGE_DEGRADATION_RATE", "0.07")
    assert await get_runtime_float("VEHICLE_AGE_DEGRADATION_RATE", 0.01) == 0.07


def test_build_vehicle_specs_uses_resolved_rate_not_settings():
    """S2 Görev 2 — davranış kanıtı: _build_vehicle_specs artık
    settings.VEHICLE_AGE_DEGRADATION_RATE'i DOĞRUDAN okumaz; çağıranın
    (predict_consumption, async boundary'de) geçtiği rate'i kullanır.
    Oran 0 -> yaş cezası yok; oran 0.05 -> belirgin ceza.
    """
    arac = {
        "bos_agirlik_kg": 8000,
        "motor_verimliligi": 0.40,
        "yil": date.today().year - 10,
    }
    specs_no_penalty, _ = build_vehicle_specs(arac, None, 0.0)
    specs_penalized, _ = build_vehicle_specs(arac, None, 0.05)

    assert specs_no_penalty.engine_efficiency == pytest.approx(0.40)
    assert specs_penalized.engine_efficiency < 0.40
    assert specs_penalized.engine_efficiency < specs_no_penalty.engine_efficiency
