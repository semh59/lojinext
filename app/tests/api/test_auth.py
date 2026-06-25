"""Authentication endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_login_success(async_client, monkeypatch):
    """Test login with valid credentials → 200 with token.

    The auth endpoint calls auth_service.authenticate() via FastAPI DI.
    We mock it by patching AuthService.authenticate directly.
    """
    from app.core.services import auth_service as auth_svc_mod

    async def _fake_authenticate(self, email, password, request):
        return ("fake_access_token", "fake_refresh_token")

    monkeypatch.setattr(auth_svc_mod.AuthService, "authenticate", _fake_authenticate)

    test_password = "password123"  # pragma: allowlist secret
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": test_password},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client, monkeypatch):
    """Test login with invalid credentials → 401."""
    # Don't patch anything — the real auth will fail with 401 for unknown user
    wrong_password = "wrongpassword"  # pragma: allowlist secret
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "nonexistent_testuser", "password": wrong_password},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(async_client, admin_auth_headers):
    """Test logout clears session → 200 (real Redis blacklist.add)."""
    response = await async_client.post(
        "/api/v1/auth/logout", headers=admin_auth_headers
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_logout_requires_auth(async_client):
    """Test logout without auth → 401."""
    response = await async_client.post("/api/v1/auth/logout")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(async_client, monkeypatch):
    """Test token refresh with valid refresh token → 200.

    The refresh endpoint calls auth_service.refresh_session().
    We mock it directly on AuthService.
    """
    from app.core.services import auth_service as auth_svc_mod

    async def _fake_refresh(self, token):
        return ("new_access_token", "new_refresh_token")

    monkeypatch.setattr(auth_svc_mod.AuthService, "refresh_session", _fake_refresh)

    response = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "fake_refresh_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_refresh_token_invalid(async_client):
    """Test token refresh with invalid token → 401 (real AuthService validates JWT)."""
    response = await async_client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "invalid_token"}
    )

    assert response.status_code == 401
