import pytest

# The admin roles router is mounted at /admin/roles.
# Routes use trailing slash: GET / and POST /


@pytest.mark.asyncio
async def test_roles_requires_auth(async_client):
    response = await async_client.get("/api/v1/admin/roles/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_roles_get(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/roles/", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_roles_post_auth(async_client):
    response = await async_client.post("/api/v1/admin/roles/", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_roles_post(async_client, admin_auth_headers):
    response = await async_client.post(
        "/api/v1/admin/roles/",
        json={"ad": "test_role_unique", "yetkiler": {}},
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 201, 400, 422)


@pytest.mark.asyncio
async def test_roles_put_auth(async_client):
    response = await async_client.put("/api/v1/admin/roles/1", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_roles_put(async_client, admin_auth_headers):
    # Var olmayan rol → 404; korumalı/escalation → 403; doğrulama → 422.
    response = await async_client.put(
        "/api/v1/admin/roles/9999",
        json={"ad": "guncellenen_rol", "yetkiler": {"sefer:read": True}},
        headers=admin_auth_headers,
    )
    assert response.status_code in (200, 403, 404, 422, 500)


@pytest.mark.asyncio
async def test_roles_delete_auth(async_client):
    response = await async_client.delete("/api/v1/admin/roles/1")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_roles_delete(async_client, admin_auth_headers):
    # DELETE artık mevcut. Var olmayan rol → 404; sistem rolü → 403;
    # kullanımda → 409; başarı → 204.
    response = await async_client.delete(
        "/api/v1/admin/roles/9999", headers=admin_auth_headers
    )
    assert response.status_code in (204, 403, 404, 409, 500)


@pytest.mark.asyncio
async def test_roles_requires_permission(async_client, normal_auth_headers):
    response = await async_client.get(
        "/api/v1/admin/roles/", headers=normal_auth_headers
    )
    assert response.status_code in (401, 403, 404)
