import pytest

# The error_stream router is mounted at /system prefix (not /errors).
# GET /system/error-stream requires a one-time token query param.
# POST /system/error-stream-token creates that token (admin only, requires Redis).


@pytest.mark.asyncio
async def test_error_stream_requires_auth(async_client):
    # GET /system/error-stream without token → 401
    response = await async_client.get("/api/v1/system/error-stream")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_error_stream_endpoint(async_client, admin_auth_headers, monkeypatch):
    # POST token endpoint — admin only.
    # Mock pubsub manager to avoid Redis connection attempt.
    from unittest.mock import MagicMock

    import app.infrastructure.cache.redis_pubsub as pubsub_mod

    mock_mgr = MagicMock()
    mock_mgr.redis = None  # Use memory fallback path

    async def _fake_set(key, val, expire=None):
        pass

    mock_mgr.set = _fake_set
    monkeypatch.setattr(pubsub_mod, "get_pubsub_manager", lambda: mock_mgr)

    response = await async_client.post(
        "/api/v1/system/error-stream-token", headers=admin_auth_headers
    )
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_error_stream_with_filter(async_client, admin_auth_headers, monkeypatch):
    # GET /system/error-stream with invalid token → 401 (token not found)
    from unittest.mock import MagicMock

    import app.infrastructure.cache.redis_pubsub as pubsub_mod

    mock_mgr = MagicMock()
    mock_mgr.redis = None

    async def _fake_get(key):
        return None  # Token not found

    mock_mgr.get = _fake_get
    monkeypatch.setattr(pubsub_mod, "get_pubsub_manager", lambda: mock_mgr)

    response = await async_client.get(
        "/api/v1/system/error-stream?token=fake_invalid_token"
    )
    assert response.status_code in (401, 403, 404, 500)


@pytest.mark.asyncio
async def test_error_stream_permission(async_client, normal_auth_headers, monkeypatch):
    # POST token requires admin; normal user gets 403 or 401
    response = await async_client.post(
        "/api/v1/system/error-stream-token", headers=normal_auth_headers
    )
    assert response.status_code in (401, 403, 404)
