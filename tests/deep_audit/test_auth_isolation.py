import pytest


@pytest.mark.asyncio
async def test_admin_access_by_user(async_client):
    """
    Auth Test.
    """
    # Invalid Token check
    headers = {"Authorization": "Bearer invalid_token"}
    res = await async_client.delete("/api/v1/fuel/1", headers=headers)
    assert res.status_code == 401
