import pytest


@pytest.mark.asyncio
async def test_import_history_success(async_client, admin_auth_headers):
    """Test getting import history → 200 (real UnitOfWork, empty test DB)."""
    response = await async_client.get(
        "/api/v1/admin/imports/history",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_import_history_requires_permission(async_client, normal_auth_headers):
    """Test history requires permission."""
    response = await async_client.get(
        "/api/v1/admin/imports/history",
        headers=normal_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_history_requires_auth(async_client):
    """Test history requires auth."""
    response = await async_client.get("/api/v1/admin/imports/history")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_import_history_with_limit(async_client, admin_auth_headers):
    """Test import history with limit param → 200 (real UnitOfWork)."""
    response = await async_client.get(
        "/api/v1/admin/imports/history?limit=20",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_import_history_rejects_huge_limit(async_client, admin_auth_headers):
    """2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 20): `limit` üst
    sınırı yoktu — `?limit=999999999` tüm tabloyu OOM riskiyle çekebilirdi.
    Artık server-side bir üst sınır var, aşan değer 422 ile reddedilir."""
    response = await async_client.get(
        "/api/v1/admin/imports/history?limit=999999999",
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_import_history_default_limit(async_client, admin_auth_headers):
    """Test import history uses default limit → 200 (real UnitOfWork)."""
    response = await async_client.get(
        "/api/v1/admin/imports/history",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_import_history_returns_list(async_client, admin_auth_headers):
    """Test import history returns list → 200 (real UnitOfWork)."""
    response = await async_client.get(
        "/api/v1/admin/imports/history",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
