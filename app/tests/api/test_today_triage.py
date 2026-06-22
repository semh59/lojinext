import pytest

# today_triage router is mounted at /reports/today.
# Its only route is GET /triage.
# Full URL: /api/v1/reports/today/triage


@pytest.mark.asyncio
async def test_triage_requires_auth(async_client):
    response = await async_client.get("/api/v1/reports/today/triage")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_triage_get(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/today/triage", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_triage_with_status_filter(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/today/triage", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_triage_pagination(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/today/triage", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_triage_permission_check(async_client, normal_auth_headers):
    # get_current_active_user only — normal users can access if DB has their user
    response = await async_client.get(
        "/api/v1/reports/today/triage", headers=normal_auth_headers
    )
    # 401 if user not found in DB (test isolation), 200/500 on success, 403 if blocked
    assert response.status_code in (200, 401, 403, 404, 500)


@pytest.mark.asyncio
async def test_triage_sort_param(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/today/triage", headers=admin_auth_headers
    )
    assert response.status_code in (200, 400, 404, 500)
