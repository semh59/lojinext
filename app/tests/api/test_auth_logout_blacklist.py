"""Tests for auth logout blacklist failure handling."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_logout_blacklist_failure_returns_warning(async_client, auth_headers):
    """When blacklist fails, response should contain warning key."""
    with patch(
        "app.api.v1.endpoints.auth.blacklist.add",
        side_effect=Exception("Redis down"),
    ):
        response = await async_client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "warning" in data


async def test_logout_blacklist_failure_revokes_session(async_client, auth_headers):
    """When blacklist fails, session must still be revoked."""
    mock_revoke = AsyncMock()

    async def _fake_auth_service():
        from app.core.services.auth_service import AuthService

        svc = AsyncMock(spec=AuthService)
        svc.revoke_session = mock_revoke
        return svc

    from app.api.deps import get_auth_service
    from app.main import app

    app.dependency_overrides[get_auth_service] = _fake_auth_service
    try:
        with patch(
            "app.api.v1.endpoints.auth.blacklist.add",
            side_effect=Exception("Redis down"),
        ):
            response = await async_client.post(
                "/api/v1/auth/logout", headers=auth_headers
            )
    finally:
        app.dependency_overrides.pop(get_auth_service, None)

    assert response.status_code == 200
    mock_revoke.assert_called_once()
