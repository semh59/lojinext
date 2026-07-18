from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.services.health_service import HealthService


@pytest.fixture
def health_service():
    return HealthService()


@pytest.mark.asyncio
async def test_check_db_healthy(health_service):
    # Mock engine.connect() context manager
    with patch("app.core.services.health_service.engine") as mock_engine:
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = None

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = None

        mock_engine.connect.return_value = mock_ctx

        result = await health_service.check_db()

        assert result["status"] == "healthy"
        assert "latency_ms" in result
        mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_check_db_unhealthy(health_service):
    with patch("app.core.services.health_service.engine") as mock_engine:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.side_effect = Exception("DB Down")
        mock_engine.connect.return_value = mock_ctx

        result = await health_service.check_db()

        assert result["status"] == "unhealthy"
        assert result["error"] == "DB Down"


@pytest.mark.asyncio
async def test_check_ai_readiness_healthy(health_service):
    # get_rag_engine fonksiyon içinde import edildiği için kaynağından
    # (v2.modules.ai_assistant.public) patch edilmeli
    with patch(
        "v2.modules.ai_assistant.public.get_rag_engine"
    ) as mock_get_rag:
        mock_rag = Mock()
        mock_rag.get_stats.return_value = {"initialized": True, "total_documents": 100}
        mock_get_rag.return_value = mock_rag

        result = await health_service.check_ai_readiness()

        assert result["status"] == "healthy"
        assert result["rag_engine"]["total_documents"] == 100
        # AUDIT-092: check_ai_readiness gerçek ensemble model adlarını (küçük harf) döner.
        assert "lightgbm" in result["models"]


@pytest.mark.asyncio
async def test_check_ai_readiness_degraded(health_service):
    with patch(
        "v2.modules.ai_assistant.public.get_rag_engine"
    ) as mock_get_rag:
        mock_rag = Mock()
        mock_rag.get_stats.return_value = {"initialized": False}
        mock_get_rag.return_value = mock_rag

        result = await health_service.check_ai_readiness()

        assert result["status"] == "degraded"
        assert result["rag_engine"]["initialized"] is False


@pytest.mark.asyncio
async def test_get_full_status(health_service):
    # Mock internal methods
    with (
        patch.object(health_service, "check_db", return_value={"status": "healthy"}),
        # AUDIT-090: get_full_status check_redis'i de toplar → mock'lanmalı.
        patch.object(health_service, "check_redis", return_value={"status": "healthy"}),
        patch.object(
            health_service, "check_ai_readiness", return_value={"status": "healthy"}
        ),
    ):
        result = await health_service.get_full_status()

        assert result["status"] == "healthy"
        assert "uptime_seconds" in result
        assert result["components"]["database"]["status"] == "healthy"
        assert result["components"]["ai_engine"]["status"] == "healthy"
