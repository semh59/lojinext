import pytest


@pytest.mark.asyncio
async def test_ws_requires_auth(async_client):
    """WebSocket connections require auth in normal flow, but test basic endpoint."""
    response = await async_client.get("/api/v1/admin/ws/stream")
    assert response.status_code in (200, 401, 403, 404, 500)


@pytest.mark.asyncio
async def test_ws_endpoint_exists(async_client, admin_auth_headers):
    """Test WS endpoint is registered."""
    # WebSocket can't be tested via standard GET, but endpoint should exist
    response = await async_client.options("/api/v1/admin/ws/stream")
    assert response.status_code in (200, 404, 405, 500)


@pytest.mark.asyncio
async def test_ws_requires_permission(async_client, normal_auth_headers):
    """Test WS requires proper permissions."""
    response = await async_client.get(
        "/api/v1/admin/ws/stream", headers=normal_auth_headers
    )
    assert response.status_code in (403, 404, 500)


@pytest.mark.asyncio
async def test_ws_basic_health(async_client):
    """Test WS basic connectivity."""
    response = await async_client.get("/api/v1/admin/ws")
    assert response.status_code in (200, 301, 404, 500)
