from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_get_all_configs_success(async_client, admin_auth_headers, monkeypatch):
    """Test getting all configs."""
    expected_configs = [
        {
            "anahtar": "param1",
            "deger": "value1",
            "tip": "string",
            "birim": None,
            "min_deger": None,
            "max_deger": None,
            "grup": "general",
            "aciklama": "Test param",
            "yeniden_baslat": False,
        }
    ]
    mock_service = AsyncMock()
    mock_service.get_all = AsyncMock(return_value=expected_configs)

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_config.KonfigService",
        lambda db: mock_service,
    )

    response = await async_client.get(
        "/api/v1/admin/config/",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_config_by_key(async_client, admin_auth_headers, monkeypatch):
    """Test getting single config by key."""
    expected_config = {
        "anahtar": "param1",
        "deger": "value1",
        "tip": "string",
        "birim": None,
        "min_deger": None,
        "max_deger": None,
        "grup": "general",
        "aciklama": "Test",
        "yeniden_baslat": False,
    }

    mock_repo = AsyncMock()
    mock_repo.get_config = AsyncMock(return_value=expected_config)

    mock_service = AsyncMock()
    mock_service.repo = mock_repo

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_config.KonfigService",
        lambda db: mock_service,
    )

    response = await async_client.get(
        "/api/v1/admin/config/param1",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["anahtar"] == "param1"


@pytest.mark.asyncio
async def test_get_config_not_found(async_client, admin_auth_headers, monkeypatch):
    """Test getting non-existent config."""
    mock_repo = AsyncMock()
    mock_repo.get_config = AsyncMock(return_value=None)

    mock_service = AsyncMock()
    mock_service.repo = mock_repo

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_config.KonfigService",
        lambda db: mock_service,
    )

    response = await async_client.get(
        "/api/v1/admin/config/nonexistent",
        headers=admin_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_config_success(async_client, admin_auth_headers, monkeypatch):
    """Test updating a config."""
    old_config = {
        "anahtar": "param1",
        "deger": "old_value",
        "tip": "string",
        "birim": None,
        "min_deger": None,
        "max_deger": None,
        "grup": "general",
        "aciklama": "Test",
        "yeniden_baslat": False,
    }
    updated_config = {**old_config, "deger": "new_value"}

    mock_repo = AsyncMock()
    mock_repo.get_config = AsyncMock(return_value=old_config)

    mock_service = AsyncMock()
    mock_service.repo = mock_repo
    mock_service.update_config = AsyncMock(return_value=updated_config)

    mock_audit = AsyncMock()
    mock_audit.log_config_change = AsyncMock()

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_config.KonfigService",
        lambda db: mock_service,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_config.AdminAuditService",
        lambda: mock_audit,
    )

    response = await async_client.put(
        "/api/v1/admin/config/param1",
        json={"value": "new_value", "reason": "Test update"},
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
