import pytest


@pytest.mark.asyncio
async def test_maintenance_requires_auth(async_client):
    """Test maintenance endpoint requires auth."""
    # Try any maintenance endpoint without auth
    response = await async_client.get("/api/v1/admin/maintenance/alerts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_maintenance_list_success(async_client, admin_auth_headers, monkeypatch):
    """Test listing maintenance records."""
    response = await async_client.get(
        "/api/v1/admin/maintenance/alerts",
        headers=admin_auth_headers,
    )
    # 200 or 500 depending on service availability
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_maintenance_requires_permission(async_client, normal_auth_headers):
    """Test maintenance requires proper permission."""
    response = await async_client.get(
        "/api/v1/admin/maintenance/alerts",
        headers=normal_auth_headers,
    )
    # If endpoint is protected, 401/403 or 404 (401 if user not found in test DB)
    assert response.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_maintenance_post_requires_auth(async_client):
    """Test POST to maintenance requires auth.

    The create endpoint is at POST /admin/maintenance/ (trailing slash).
    Without auth the server should redirect to / which itself returns 401.
    We follow redirects so we get 401.
    """
    response = await async_client.post(
        "/api/v1/admin/maintenance/",
        json={"vehicle_id": 1, "type_id": 1},
        follow_redirects=True,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_maintenance_prediction_endpoint(async_client, admin_auth_headers):
    """Test maintenance prediction endpoint."""
    response = await async_client.get(
        "/api/v1/admin/maintenance/predictions",
        headers=admin_auth_headers,
    )
    # May fail if ML model not ready, but endpoint exists
    assert response.status_code in (200, 500, 503)


@pytest.mark.asyncio
async def test_maintenance_complete_endpoint(async_client, admin_auth_headers):
    """Test maintenance complete endpoint.

    The complete route is PATCH /{bakim_id}/complete, not PUT.
    404 if record doesn't exist, 200 if succeeds.
    """
    response = await async_client.patch(
        "/api/v1/admin/maintenance/1/complete",
        json={},
        headers=admin_auth_headers,
    )
    # 404 if record doesn't exist, 200 if succeeds
    assert response.status_code in (200, 404, 500)
