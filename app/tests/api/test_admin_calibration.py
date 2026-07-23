from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_calibrate_route_success(async_client, admin_auth_headers, monkeypatch):
    """Test route calibration success."""
    mock_service_instance = AsyncMock()
    mock_service_instance.calibrate_route_from_trip = AsyncMock(return_value=True)

    mock_service_class = MagicMock(return_value=mock_service_instance)

    monkeypatch.setattr(
        "v2.modules.route_simulation.api.admin_calibration_routes.RouteCalibrationService",
        mock_service_class,
    )

    response = await async_client.post(
        "/api/v1/admin/calibration/calibrate/1",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_calibrate_route_insufficient_data(
    async_client, admin_auth_headers, monkeypatch
):
    """Test calibration fails with insufficient data."""
    mock_service_instance = AsyncMock()
    mock_service_instance.calibrate_route_from_trip = AsyncMock(return_value=False)

    mock_service_class = MagicMock(return_value=mock_service_instance)

    monkeypatch.setattr(
        "v2.modules.route_simulation.api.admin_calibration_routes.RouteCalibrationService",
        mock_service_class,
    )

    response = await async_client.post(
        "/api/v1/admin/calibration/calibrate/999",
        headers=admin_auth_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_calibrate_route_no_permission(async_client, normal_auth_headers):
    """Test calibration requires permission."""
    response = await async_client.post(
        "/api/v1/admin/calibration/calibrate/1",
        headers=normal_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_match_trip_to_path_success(
    async_client, admin_auth_headers, monkeypatch
):
    """Test matching trip to path."""
    expected_result = {"match": True, "confidence": 0.95}
    mock_service_instance = AsyncMock()
    mock_service_instance.match_sefer_to_path = AsyncMock(return_value=expected_result)

    mock_service_class = MagicMock(return_value=mock_service_instance)

    monkeypatch.setattr(
        "v2.modules.route_simulation.api.admin_calibration_routes.RouteCalibrationService",
        mock_service_class,
    )

    response = await async_client.get(
        "/api/v1/admin/calibration/match/1",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["match"] is True


@pytest.mark.asyncio
async def test_match_trip_returns_data(async_client, admin_auth_headers, monkeypatch):
    """Test match returns result even if not perfect."""
    expected_result = {"match": False, "confidence": 0.45}
    mock_service_instance = AsyncMock()
    mock_service_instance.match_sefer_to_path = AsyncMock(return_value=expected_result)

    mock_service_class = MagicMock(return_value=mock_service_instance)

    monkeypatch.setattr(
        "v2.modules.route_simulation.api.admin_calibration_routes.RouteCalibrationService",
        mock_service_class,
    )

    response = await async_client.get(
        "/api/v1/admin/calibration/match/1",
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["match"] is False


@pytest.mark.asyncio
async def test_match_trip_no_permission(async_client, normal_auth_headers):
    """Test match requires permission."""
    response = await async_client.get(
        "/api/v1/admin/calibration/match/1",
        headers=normal_auth_headers,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_calibrate_auth_required(async_client):
    """Test calibration requires authentication."""
    response = await async_client.post(
        "/api/v1/admin/calibration/calibrate/1",
    )

    assert response.status_code == 401
