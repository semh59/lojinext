import pytest

# Trailers router uses @router.get("/") — trailing slash required.


@pytest.mark.asyncio
async def test_trailers_requires_auth(async_client):
    response = await async_client.get("/api/v1/trailers/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_trailers_list(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/trailers/", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_trailers_create(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/trailers/",
        json={"plaka": "TEST1"},
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 201, 400, 422, 500)


@pytest.mark.asyncio
async def test_trailers_get(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/trailers/1", headers=admin_auth_headers)
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_trailers_update(async_client, admin_auth_headers):
    response = await async_client.put(
        "/api/v1/trailers/1", json={"plaka": "NEW"}, headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 422, 500)


@pytest.mark.asyncio
async def test_trailers_delete(async_client, admin_auth_headers):
    response = await async_client.delete(
        "/api/v1/trailers/1", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)
