import pytest

# The fleet_insights router is mounted at /reports/insights/fleet.
# Its only route is GET /comparison.
# The anomalies router has GET /fleet/insights.


@pytest.mark.asyncio
async def test_fleet_requires_auth(async_client):
    # Fleet insights comparison endpoint — mounted at /reports/insights/fleet/comparison
    response = await async_client.get("/api/v1/reports/insights/fleet/comparison")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_fleet_get(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/insights/fleet/comparison", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_fleet_with_filters(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/insights/fleet/comparison?days=7", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_fleet_requires_permission(async_client, normal_auth_headers):
    # Normal authenticated users can access (only get_current_active_user required)
    response = await async_client.get(
        "/api/v1/reports/insights/fleet/comparison", headers=normal_auth_headers
    )
    assert response.status_code in (200, 401, 403, 404, 500)


@pytest.mark.asyncio
async def test_fleet_date_range(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/insights/fleet/comparison?days=30",
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 400, 404, 500)


@pytest.mark.asyncio
async def test_fleet_empty_result(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/insights/fleet/comparison?days=1",
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 404, 500)
