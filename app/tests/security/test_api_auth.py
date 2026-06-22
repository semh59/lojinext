import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_unauthenticated_access_returns_401(async_client):
    """Verify that unprotected access to sensitive endpoints returns 401"""
    endpoints = [
        "/api/v1/vehicles/",
        "/api/v1/drivers/",
        "/api/v1/trips/",
        "/api/v1/fuel/",
        "/api/v1/locations/",
        "/api/v1/anomalies/fleet/insights",
        "/api/v1/predictions/predict",
        "/api/v1/reports/dashboard",
        "/api/v1/weather/forecast",
    ]

    for endpoint in endpoints:
        # Most are GET, predictions/weather/routes are POST
        if "predict" in endpoint or "forecast" in endpoint or "analyze" in endpoint:
            response = await async_client.post(endpoint, json={})
        else:
            response = await async_client.get(endpoint)

        assert response.status_code == 401, (
            f"Endpoint {endpoint} should be protected by auth"
        )


@pytest.mark.asyncio
async def test_admin_only_endpoints(async_client):
    """Verify that admin-only endpoints return 401 for unauthenticated"""
    admin_endpoints = [
        ("/api/v1/vehicles/", "POST"),
        ("/api/v1/drivers/", "POST"),
        ("/api/v1/trips/", "POST"),
        ("/api/v1/fuel/", "POST"),
        ("/api/v1/predictions/train/test_arac?model_type=linear", "POST"),
    ]

    for endpoint, method in admin_endpoints:
        if method == "POST":
            response = await async_client.post(endpoint, json={})
        elif method == "DELETE":
            response = await async_client.delete(endpoint)

        assert response.status_code == 401, (
            f"Admin endpoint {endpoint} should return 401 when no token provided"
        )


@pytest.mark.asyncio
async def test_auth_token_endpoint_works(async_client):
    """Verify that auth token endpoint responds correctly"""
    response = await async_client.post(
        "/api/v1/auth/token", data={"username": "test", "password": "test"}
    )
    # Should be 401 since user 'test' doesn't exist, but NOT 404 or 500
    assert response.status_code == 401
