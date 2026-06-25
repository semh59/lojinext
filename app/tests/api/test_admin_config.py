import pytest

from app.tests._helpers.seed import seed_sistem_konfig


@pytest.mark.asyncio
async def test_get_all_configs_success(async_client, admin_auth_headers):
    """Test getting all configs → 200, list (real KonfigService against test DB)."""
    response = await async_client.get(
        "/api/v1/admin/config/",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_config_by_key(async_client, admin_auth_headers, db_session):
    """Test getting single config by key → 200 (seeded row via real repo)."""
    await seed_sistem_konfig(
        db_session, anahtar="param1", deger={"v": "value1"}, tip="json", grup="test"
    )

    response = await async_client.get(
        "/api/v1/admin/config/param1",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["anahtar"] == "param1"


@pytest.mark.asyncio
async def test_get_config_not_found(async_client, admin_auth_headers):
    """Test getting non-existent config → 404 (real repo returns None)."""
    response = await async_client.get(
        "/api/v1/admin/config/nonexistent",
        headers=admin_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_config_success(async_client, admin_auth_headers, db_session):
    """Test updating a config → 200 (real KonfigService + AdminAuditService)."""
    await seed_sistem_konfig(
        db_session, anahtar="param1", deger={"v": "old_value"}, tip="json", grup="test"
    )

    response = await async_client.put(
        "/api/v1/admin/config/param1",
        json={"value": {"v": "new_value"}, "reason": "Test update"},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_config_requires_permission(async_client, normal_auth_headers):
    """Test config update requires permission."""
    response = await async_client.put(
        "/api/v1/admin/config/param1",
        json={"value": "new_value"},
        headers=normal_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_config_requires_auth(async_client):
    """Test config get requires auth."""
    response = await async_client.get("/api/v1/admin/config/")

    assert response.status_code == 401
