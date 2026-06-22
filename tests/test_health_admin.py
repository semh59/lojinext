from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.health_service import HealthService


@pytest.mark.asyncio
async def test_health_service_admin_details():
    service = HealthService()

    # Mocking components that involve DB, Redis or RAG (all three needed for healthy overall)
    with (
        patch.object(HealthService, "check_db", return_value={"status": "healthy"}),
        patch.object(HealthService, "check_redis", return_value={"status": "healthy"}),
        patch.object(
            HealthService, "check_ai_readiness", return_value={"status": "healthy"}
        ),
    ):
        details = await service.get_admin_health_details()

        assert details["status"] == "healthy"
        assert "sentry" in details
        assert "circuit_breakers" in details
        assert "backups" in details
        assert "enabled" in details["sentry"]


@pytest.mark.asyncio
async def test_health_service_check_db_healthy():
    """Verify DB health check logic."""
    service = HealthService()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    with patch("app.core.services.health_service.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        status = await service.check_db()
        assert status["status"] == "healthy"
        assert "latency_ms" in status


@pytest.mark.asyncio
async def test_health_service_check_ai_readiness_failure():
    """Verify AI readiness when RAG fails or is not initialized."""
    service = HealthService()
    # Path changed to where it's actually imported in the service method or where it resides
    with patch("app.core.ai.rag_engine.get_rag_engine") as mock_get_rag:
        mock_rag = MagicMock()
        mock_rag.get_stats.return_value = {"initialized": False}
        mock_get_rag.return_value = mock_rag

        status = await service.check_ai_readiness()
        assert status["status"] == "degraded"
