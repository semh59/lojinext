"""Tests for auth logout blacklist failure handling."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_logout_blacklist_failure_returns_warning(async_client, auth_headers):
    """When blacklist fails, response should contain warning key."""
    with patch(
        "v2.modules.auth_rbac.api.auth_routes.blacklist.add",
        side_effect=Exception("Redis down"),
    ):
        response = await async_client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "warning" in data


async def test_logout_blacklist_failure_revokes_session(async_client, auth_headers):
    """When blacklist fails, session must still be revoked."""
    mock_revoke = AsyncMock()

    from v2.modules.auth_rbac.api import auth_routes

    original_revoke = auth_routes.auth_service.revoke_session

    async def _fake_revoke(user_id, uow=None):
        return await mock_revoke(user_id)

    auth_routes.auth_service.revoke_session = _fake_revoke
    try:
        with patch(
            "v2.modules.auth_rbac.api.auth_routes.blacklist.add",
            side_effect=Exception("Redis down"),
        ):
            response = await async_client.post(
                "/api/v1/auth/logout", headers=auth_headers
            )
    finally:
        auth_routes.auth_service.revoke_session = original_revoke

    assert response.status_code == 200
    mock_revoke.assert_called_once()
