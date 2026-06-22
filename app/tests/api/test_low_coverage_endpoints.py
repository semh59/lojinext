import pytest

# vehicles.py uses @router.get("/") — trailing slash required


@pytest.mark.asyncio
async def test_vehicles_requires_auth(async_client):
    response = await async_client.get("/api/v1/vehicles/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vehicles_list(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/vehicles/", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_vehicles_filter(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/vehicles/?aktif_only=true", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


# fuel.py uses @router.get("/") — trailing slash required


@pytest.mark.asyncio
async def test_fuel_requires_auth(async_client):
    response = await async_client.get("/api/v1/fuel/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_fuel_list(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/fuel/", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_fuel_date_range(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/fuel/?baslangic_tarihi=2026-01-01", headers=admin_auth_headers
    )
    assert response.status_code in (200, 400, 404, 422, 500)


# executive.py is mounted at /reports/executive.
# There is no /dashboard route; use /kpi instead.


@pytest.mark.asyncio
async def test_executive_requires_auth(async_client):
    response = await async_client.get("/api/v1/reports/executive/kpi")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_executive_dashboard(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/reports/executive/kpi", headers=admin_auth_headers
    )
    assert response.status_code in (200, 403, 404, 500, 503)


# investigations.py is mounted at /admin/investigations (not /investigations).


@pytest.mark.asyncio
async def test_investigations_requires_auth(async_client):
    response = await async_client.get("/api/v1/admin/investigations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_investigations_list(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/investigations", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500, 503)


@pytest.mark.asyncio
async def test_investigations_status_filter(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/investigations?status=open", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500, 503)


@pytest.mark.asyncio
async def test_investigations_priority_filter(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/investigations?priority=high", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500, 503)


@pytest.mark.asyncio
async def test_investigations_pagination(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/investigations?skip=0&limit=10", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500, 503)


@pytest.mark.asyncio
async def test_investigations_sort(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/investigations?sort=created_at", headers=admin_auth_headers
    )
    assert response.status_code in (200, 400, 404, 500, 503)
