"""Health check endpoint tests."""

from unittest.mock import AsyncMock

import pytest


def _make_healthy_payload():
    return {
        "status": "healthy",
        "uptime_seconds": 1000,
        "timestamp": "2026-06-02T19:00:00Z",
        "components": {
            "database": {"status": "healthy"},
            "cache": {"status": "healthy"},
            "queue": {"status": "healthy"},
        },
    }


def _make_unhealthy_payload():
    return {
        "status": "unhealthy",
        "uptime_seconds": 500,
        "timestamp": "2026-06-02T19:00:00Z",
        "components": {
            "database": {"status": "down", "error": "Connection refused"},
            "cache": {"status": "healthy"},
            "queue": {"status": "healthy"},
        },
    }


@pytest.mark.asyncio
async def test_health_check_all_healthy(async_client):
    """Test health check when all components are healthy → 200."""
    from app.main import app
    from v2.modules.admin_platform.application.health_service import (
        HealthService,
        get_health_service,
    )

    mock_service = AsyncMock(spec=HealthService)
    mock_service.get_full_status = AsyncMock(return_value=_make_healthy_payload())

    async def _override():
        return mock_service

    app.dependency_overrides[get_health_service] = _override
    try:
        response = await async_client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    finally:
        app.dependency_overrides.pop(get_health_service, None)


@pytest.mark.asyncio
async def test_health_check_database_down(async_client):
    """Test health check when database is down → 503."""
    from app.main import app
    from v2.modules.admin_platform.application.health_service import (
        HealthService,
        get_health_service,
    )

    mock_service = AsyncMock(spec=HealthService)
    mock_service.get_full_status = AsyncMock(return_value=_make_unhealthy_payload())

    async def _override():
        return mock_service

    app.dependency_overrides[get_health_service] = _override
    try:
        response = await async_client.get("/api/v1/health/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
    finally:
        app.dependency_overrides.pop(get_health_service, None)


@pytest.mark.asyncio
async def test_health_check_does_not_leak_internal_details(async_client):
    """The public (unauthenticated) health endpoint must expose only component
    status — never raw error strings (DB/Redis host/credentials) or AI-engine
    internals."""
    from app.main import app
    from v2.modules.admin_platform.application.health_service import (
        HealthService,
        get_health_service,
    )

    payload = {
        "status": "unhealthy",
        "uptime_seconds": 500,
        "components": {
            "database": {
                "status": "unhealthy",
                "error": "connection to host=db.internal port=5432 user=secret failed",
            },
            "ai_engine": {
                "status": "degraded",
                "rag_engine": {"index_path": "/app/data/ai_kb", "docs": 1234},
                "models": ["LightGBM", "LSTM", "RAG"],
            },
        },
    }

    mock_service = AsyncMock(spec=HealthService)
    mock_service.get_full_status = AsyncMock(return_value=payload)

    async def _override():
        return mock_service

    app.dependency_overrides[get_health_service] = _override
    try:
        response = await async_client.get("/api/v1/health/")
        body = response.text
        data = response.json()
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert data["components"]["database"]["status"] == "unhealthy"
    # No leaked internals anywhere in the serialized response.
    assert "db.internal" not in body
    assert "secret" not in body
    assert "rag_engine" not in body
    assert "index_path" not in body
    assert data["components"]["database"].get("error") is None


@pytest.mark.asyncio
async def test_health_check_cache_down(async_client):
    """Test health check with cache down but database healthy → 200."""
    from app.main import app
    from v2.modules.admin_platform.application.health_service import (
        HealthService,
        get_health_service,
    )

    payload = {
        "status": "healthy",
        "uptime_seconds": 1000,
        "timestamp": "2026-06-02T19:00:00Z",
        "components": {
            "database": {"status": "healthy"},
            "cache": {"status": "down"},
            "queue": {"status": "healthy"},
        },
    }

    mock_service = AsyncMock(spec=HealthService)
    mock_service.get_full_status = AsyncMock(return_value=payload)

    async def _override():
        return mock_service

    app.dependency_overrides[get_health_service] = _override
    try:
        response = await async_client.get("/api/v1/health/")
        # Cache down doesn't affect status code (only database does)
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_health_service, None)


@pytest.mark.asyncio
async def test_health_check_returns_json(async_client):
    """Test health check response is valid JSON with required fields."""
    from app.main import app
    from v2.modules.admin_platform.application.health_service import (
        HealthService,
        get_health_service,
    )

    payload = {
        "status": "healthy",
        "uptime_seconds": 1000,
        "timestamp": "2026-06-02T19:00:00Z",
        "components": {
            "database": {"status": "healthy"},
        },
    }

    mock_service = AsyncMock(spec=HealthService)
    mock_service.get_full_status = AsyncMock(return_value=payload)

    async def _override():
        return mock_service

    app.dependency_overrides[get_health_service] = _override
    try:
        response = await async_client.get("/api/v1/health/")
        data = response.json()
        assert "status" in data
        assert "components" in data
    finally:
        app.dependency_overrides.pop(get_health_service, None)
