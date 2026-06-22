from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_override_trip_attribution_single_success(
    async_client, admin_auth_headers, monkeypatch
):
    """Test single attribution override happy path."""
    mock_service = AsyncMock()
    mock_service.override_attribution = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_attribution.AttributionService",
        lambda uow: mock_service,
    )

    response = await async_client.post(
        "/api/v1/admin/attribution/override",
        json={
            "sefer_id": 1,
            "new_arac_id": 2,
            "new_sofor_id": 3,
            "reason": "Test override",
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sefer_id"] == 1
    assert data["success"] is True


@pytest.mark.asyncio
async def test_override_trip_attribution_bulk_success(
    async_client, admin_auth_headers, monkeypatch
):
    """Test bulk attribution override happy path."""
    mock_service = AsyncMock()
    mock_service.override_attribution = AsyncMock(return_value=True)

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_attribution.AttributionService",
        lambda uow: mock_service,
    )

    response = await async_client.post(
        "/api/v1/admin/attribution/bulk-override",
        json=[
            {"sefer_id": 1, "new_arac_id": 2, "new_sofor_id": 3, "reason": "Test 1"},
            {"sefer_id": 4, "new_arac_id": 5, "new_sofor_id": 6, "reason": "Test 2"},
        ],
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["success"] is True for item in data)


@pytest.mark.asyncio
async def test_override_trip_attribution_no_permission(
    async_client, normal_auth_headers
):
    """Test attribution override without permission → 403."""
    response = await async_client.post(
        "/api/v1/admin/attribution/override",
        json={
            "sefer_id": 1,
            "new_arac_id": 2,
            "new_sofor_id": 3,
            "reason": "No permission",
        },
        headers=normal_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_override_trip_attribution_failure_returns_false(
    async_client, admin_auth_headers, monkeypatch
):
    """Test attribution override returns false when service can't update."""
    mock_service = AsyncMock()
    mock_service.override_attribution = AsyncMock(return_value=False)

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_attribution.AttributionService",
        lambda uow: mock_service,
    )

    response = await async_client.post(
        "/api/v1/admin/attribution/override",
        json={
            "sefer_id": 9999,
            "new_arac_id": 2,
            "new_sofor_id": 3,
            "reason": "Bad sefer",
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_override_trip_attribution_service_error(
    async_client, admin_auth_headers, monkeypatch
):
    """Test attribution override with service exception → 500."""
    mock_service = AsyncMock()
    mock_service.override_attribution = AsyncMock(
        side_effect=Exception("Database error")
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.admin_attribution.AttributionService",
        lambda uow: mock_service,
    )

    response = await async_client.post(
        "/api/v1/admin/attribution/override",
        json={
            "sefer_id": 1,
            "new_arac_id": 2,
            "new_sofor_id": 3,
            "reason": "Error",
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_override_trip_attribution_auth_required(
    async_client,
):
    """Test attribution override requires authentication."""
    response = await async_client.post(
        "/api/v1/admin/attribution/override",
        json={
            "sefer_id": 1,
            "new_arac_id": 2,
            "new_sofor_id": 3,
            "reason": "No auth",
        },
    )

    assert response.status_code == 401
