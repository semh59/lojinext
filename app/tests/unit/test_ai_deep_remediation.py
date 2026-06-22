from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ai.chatbot import get_chatbot
from app.core.ai.rag_engine import get_rag_engine
from app.core.services.anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
    AnomalyType,
    SeverityEnum,
)


@pytest.mark.asyncio
async def test_rag_engine_regression_fixed():
    """EMBEDDING_MODEL özniteliğinin varlığını doğrula (Regression Test)"""
    rag = get_rag_engine()
    assert hasattr(rag, "EMBEDDING_MODEL")
    assert rag.EMBEDDING_MODEL is not None


@pytest.mark.asyncio
async def test_chatbot_singleton_instance():
    """Chatbot singleton örneği tek instance olmalı."""
    with patch("app.core.ai.chatbot._chatbot", None):
        cb1 = get_chatbot()
        cb2 = get_chatbot()
        assert cb1 is cb2


@pytest.mark.asyncio
async def test_anomaly_bulk_insert():
    """Bulk insert mantığının SQL çağrısını doğrula"""
    detector = AnomalyDetector()
    anomalies = [
        AnomalyResult(
            AnomalyType.TUKETIM, "arac", 1, 35.0, 32.0, 9.3, SeverityEnum.LOW, "test1"
        ),
        AnomalyResult(
            AnomalyType.TUKETIM, "arac", 2, 45.0, 32.0, 40.6, SeverityEnum.HIGH, "test2"
        ),
    ]

    with patch("app.core.services.anomaly_detector.UnitOfWork") as mock_uow_class:
        # Async context manager mock'la
        uow_instance = MagicMock()
        uow_instance.session.execute = AsyncMock()
        uow_instance.commit = AsyncMock()
        mock_uow_class.return_value.__aenter__.return_value = uow_instance

        await detector.save_anomalies(anomalies)

        # execute'un çağrıldığını ve params_list'in geçtiğini doğrula
        args, kwargs = uow_instance.session.execute.call_args
        assert len(args[1]) == 2  # 2 elemanlı liste geçmiş olmalı
        assert args[1][0]["kaynak_id"] == 1
        assert args[1][1]["kaynak_id"] == 2


@pytest.mark.asyncio
async def test_recommendation_cache_thread_safety():
    """Cache lock'unun varlığını doğrula"""
    from app.core.ai.recommendation_engine import get_recommendation_engine

    engine = get_recommendation_engine()
    assert hasattr(engine, "_lock")
    assert engine._lock is not None
