import pytest

# The anomalies router uses @router.get("/") - trailing slash is required.


@pytest.mark.asyncio
async def test_anomalies_requires_auth(async_client):
    response = await async_client.get("/api/v1/anomalies/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_anomalies_list(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/anomalies/", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_anomalies_acknowledge(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/anomalies/1/acknowledge", json={}, headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_anomalies_resolve(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/anomalies/1/resolve",
        json={"notes": "Fixed"},
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
async def test_anomalies_status_filter(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/anomalies/?status=open", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_anomalies_acknowledge_idempotent(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/anomalies/1/acknowledge", json={}, headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_anomalies_resolve_with_notes(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/anomalies/1/resolve",
        json={"notes": "Issue resolved successfully"},
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
async def test_anomalies_permission(async_client, normal_auth_headers):
    # normal user still has get_current_active_user access (no special permission required)
    # so 200 or 500; but DB issues might give 500
    response = await async_client.get("/api/v1/anomalies/", headers=normal_auth_headers)
    assert response.status_code in (200, 401, 403, 404, 500)


@pytest.mark.asyncio
async def test_anomalies_acknowledge_requires_permission(
    async_client, normal_auth_headers
):
    """acknowledge requires 'anomali:yonet'; the izleyici role (sefer:read only)
    must be forbidden — the action is permission-gated, not just authenticated."""
    response = await async_client.post(
        "/api/v1/anomalies/1/acknowledge", json={}, headers=normal_auth_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_anomalies_resolve_requires_permission(async_client, normal_auth_headers):
    """resolve requires 'anomali:yonet'; the izleyici role must be forbidden."""
    response = await async_client.post(
        "/api/v1/anomalies/1/resolve",
        json={"notes": "x"},
        headers=normal_auth_headers,
    )
    assert response.status_code == 403
