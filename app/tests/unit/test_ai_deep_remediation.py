import pytest
from sqlalchemy import select

from app.database.models import Anomaly
from v2.modules.ai_assistant.infrastructure.rag.rag_engine import get_rag_engine
from v2.modules.anomaly.application.detect_anomaly import (
    AnomalyDetector,
    AnomalyResult,
    AnomalyType,
    SeverityEnum,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_rag_engine_regression_fixed():
    """EMBEDDING_MODEL özniteliğinin varlığını doğrula (Regression Test)"""
    rag = get_rag_engine()
    assert hasattr(rag, "EMBEDDING_MODEL")
    assert rag.EMBEDDING_MODEL is not None


@pytest.mark.asyncio
async def test_anomaly_bulk_insert(db_session):
    """Bulk insert gerçekten 2 anomaly satırı yazmalı (mock execute çağrısı değil,
    gerçek anomalies satırları — eski test yalnız session.execute.call_args'ı
    doğruluyordu, persist'i değil)."""
    detector = AnomalyDetector()
    anomalies = [
        AnomalyResult(
            AnomalyType.TUKETIM, "arac", 1, 35.0, 32.0, 9.3, SeverityEnum.LOW, "test1"
        ),
        AnomalyResult(
            AnomalyType.TUKETIM, "arac", 2, 45.0, 32.0, 40.6, SeverityEnum.HIGH, "test2"
        ),
    ]

    count = await detector.save_anomalies(anomalies)

    assert count == 2
    rows = (
        (await db_session.execute(select(Anomaly).order_by(Anomaly.kaynak_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert [r.kaynak_id for r in rows] == [1, 2]
    assert [r.deger for r in rows] == [35.0, 45.0]


@pytest.mark.asyncio
async def test_recommendation_cache_thread_safety():
    """Cache lock'unun varlığını doğrula"""
    from v2.modules.ai_assistant.application.recommendation_engine import (
        get_recommendation_engine,
    )

    engine = get_recommendation_engine()
    assert hasattr(engine, "_lock")
    assert engine._lock is not None
