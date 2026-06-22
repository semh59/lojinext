import pytest

# Mark as async test
pytestmark = pytest.mark.asyncio


async def test_fleet_insights_endpoint_success(
    async_client, async_normal_user_token_headers
):
    """
    Test /fleet/insights endpoint returns 200 and valid structure.
    """
    response = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=30",
        headers=async_normal_user_token_headers,
    )
    assert response.status_code == 200

    data = response.json()
    if "data" in data:
        data = data["data"]
    assert "leakage" in data
    assert "maintenance" in data


async def test_fleet_insights_invalid_days(
    async_client, async_normal_user_token_headers
):
    """
    Test validation error for invalid 'days' parameter.
    """
    # Too small
    response = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=1",
        headers=async_normal_user_token_headers,
    )
    assert response.status_code == 422

    # Too large
    response = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=100",
        headers=async_normal_user_token_headers,
    )
    assert response.status_code == 422
