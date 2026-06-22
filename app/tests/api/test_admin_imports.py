from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_import_history_success(async_client, admin_auth_headers, monkeypatch):
    """Test getting import history."""
    mock_import_repo = AsyncMock()
    mock_import_repo.get_recent_jobs = AsyncMock(return_value=[])

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.import_repo = mock_import_repo

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_imports.UnitOfWork",
        lambda: mock_uow,
    )

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
async def test_import_history_with_limit(async_client, admin_auth_headers, monkeypatch):
    """Test import history with limit param."""
    mock_import_repo = AsyncMock()
    mock_import_repo.get_recent_jobs = AsyncMock(return_value=[])

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.import_repo = mock_import_repo

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_imports.UnitOfWork",
        lambda: mock_uow,
    )

    response = await async_client.get(
        "/api/v1/admin/imports/history?limit=20",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    # Verify limit param was passed
    mock_import_repo.get_recent_jobs.assert_called_with(limit=20)


@pytest.mark.asyncio
async def test_import_history_default_limit(
    async_client, admin_auth_headers, monkeypatch
):
    """Test import history uses default limit."""
    mock_import_repo = AsyncMock()
    mock_import_repo.get_recent_jobs = AsyncMock(return_value=[])

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.import_repo = mock_import_repo

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_imports.UnitOfWork",
        lambda: mock_uow,
    )

    response = await async_client.get(
        "/api/v1/admin/imports/history",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    # Verify default limit (50)
    mock_import_repo.get_recent_jobs.assert_called_with(limit=50)


@pytest.mark.asyncio
async def test_import_history_returns_list(
    async_client, admin_auth_headers, monkeypatch
):
    """Test import history returns list."""
    mock_import_repo = AsyncMock()
    mock_import_repo.get_recent_jobs = AsyncMock(return_value=[])

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.import_repo = mock_import_repo

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_imports.UnitOfWork",
        lambda: mock_uow,
    )

    response = await async_client.get(
        "/api/v1/admin/imports/history",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
