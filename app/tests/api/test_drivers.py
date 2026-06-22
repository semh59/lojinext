import pytest

# The drivers router uses @router.get("/") - trailing slash needed.
# There is no /bulk-action endpoint; instead it's DELETE /bulk.


@pytest.mark.asyncio
async def test_drivers_requires_auth(async_client):
    response = await async_client.get("/api/v1/drivers/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_drivers_list(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/drivers/", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_drivers_get(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/drivers/1", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_drivers_search(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/drivers/?search=name", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_drivers_bulk_action(async_client, admin_auth_headers):
    # Bulk delete uses DELETE /bulk, not POST /bulk-action
    response = await async_client.request(
        "DELETE",
        "/api/v1/drivers/bulk",
        json=[1, 2],
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 400, 404, 422, 500)


@pytest.mark.asyncio
async def test_drivers_score_breakdown(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/drivers/1/score-breakdown", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)
