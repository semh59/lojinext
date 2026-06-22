"""Coverage tests for app/api/v1/endpoints/error_stream.py (SSE streaming)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_PUBSUB_PATH = "app.infrastructure.cache.redis_pubsub.get_pubsub_manager"


# ─── POST /system/error-stream-token ─────────────────────────────────────────


async def test_create_sse_token_requires_admin(async_client):
    """No token → 401."""
    resp = await async_client.post("/api/v1/system/error-stream-token")
    assert resp.status_code == 401


async def test_create_sse_token_returns_token_and_ttl(async_client, admin_auth_headers):
    """Admin auth → receives a UUID token with 90s TTL."""
    fake_redis = AsyncMock()
    fake_redis.set = AsyncMock()

    fake_mgr = MagicMock()
    fake_mgr.redis = fake_redis

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.post(
            "/api/v1/system/error-stream-token",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["expires_in"] == 90


async def test_create_sse_token_redis_none_uses_mgr_set(
    async_client, admin_auth_headers
):
    """When redis attribute is None the manager's set() is called instead."""
    fake_mgr = AsyncMock()
    fake_mgr.redis = None
    fake_mgr.set = AsyncMock()

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.post(
            "/api/v1/system/error-stream-token",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200
    fake_mgr.set.assert_awaited_once()


# ─── GET /system/error-stream ─────────────────────────────────────────────────


async def test_error_stream_no_token_returns_401(async_client):
    """Missing ?token param → 401."""
    resp = await async_client.get("/api/v1/system/error-stream")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_error_stream_invalid_token_returns_401(async_client):
    """Token not found in Redis → 401."""
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=None)
    fake_redis.delete = AsyncMock()

    fake_mgr = MagicMock()
    fake_mgr.redis = fake_redis

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.get(
            "/api/v1/system/error-stream?token=invalid-token-uuid"
        )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"


async def test_error_stream_malformed_token_payload_returns_401(async_client):
    """Token found but payload is not valid JSON → 401."""
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=b"not-json")
    fake_redis.delete = AsyncMock()

    fake_mgr = MagicMock()
    fake_mgr.redis = fake_redis

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.get("/api/v1/system/error-stream?token=some-token")

    # malformed JSON → JSONDecodeError → 401
    assert resp.status_code == 401


async def test_error_stream_token_missing_user_id_returns_401(async_client):
    """Token payload present but missing user_id key → 401."""
    payload = json.dumps({"other_key": 99})
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=payload.encode())
    fake_redis.delete = AsyncMock()

    fake_mgr = MagicMock()
    fake_mgr.redis = fake_redis

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.get("/api/v1/system/error-stream?token=some-token")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"


async def test_error_stream_db_lookup_failure_returns_401(async_client):
    """DB error during user lookup → 401."""
    payload = json.dumps({"user_id": 999})
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=payload.encode())
    fake_redis.delete = AsyncMock()

    fake_mgr = MagicMock()
    fake_mgr.redis = fake_redis

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        with patch(
            "app.database.connection.AsyncSessionLocal",
            side_effect=Exception("DB failure"),
        ):
            resp = await async_client.get(
                "/api/v1/system/error-stream?token=some-token"
            )

    assert resp.status_code == 401


async def test_error_stream_inactive_user_returns_403(async_client, db_session):
    """Token valid but user is inactive → 403."""
    from sqlalchemy import select

    from app.core.security import get_password_hash
    from app.database.models import Kullanici, Rol

    # Ensure role exists
    result = await db_session.execute(select(Rol).where(Rol.ad == "izleyici"))
    role = result.scalar_one_or_none()
    if not role:
        role = Rol(ad="izleyici", yetkiler={"sefer:read": True})
        db_session.add(role)
        await db_session.flush()

    user = Kullanici(
        email="inactive_sse@test.com",
        ad_soyad="Inactive User",
        sifre_hash=get_password_hash("TestPass1"),
        rol_id=role.id,
        aktif=False,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    payload = json.dumps({"user_id": user.id})
    fake_redis = AsyncMock()
    fake_redis.get = AsyncMock(return_value=payload.encode())
    fake_redis.delete = AsyncMock()

    fake_mgr = MagicMock()
    fake_mgr.redis = fake_redis

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.get("/api/v1/system/error-stream?token=some-token")

    assert resp.status_code == 403


async def test_error_stream_none_redis_uses_mgr_get(async_client):
    """When redis is None, manager.get() is called."""
    fake_mgr = AsyncMock()
    fake_mgr.redis = None
    # Return None → token not found → 401
    fake_mgr.get = AsyncMock(return_value=None)

    with patch(_PUBSUB_PATH, return_value=fake_mgr):
        resp = await async_client.get("/api/v1/system/error-stream?token=abc")

    assert resp.status_code == 401
    fake_mgr.get.assert_awaited_once()


# ─── _sse_generator unit-level tests ─────────────────────────────────────────


async def test_sse_generator_too_many_streams():
    """When semaphore is locked, generator yields error event and returns."""
    from app.api.v1.endpoints.error_stream import _SSE_SEMAPHORE, _sse_generator

    # Acquire all 20 slots to trigger the "too many streams" branch
    acquired = []
    for _ in range(20):
        await _SSE_SEMAPHORE.acquire()
        acquired.append(True)

    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=True)

    events = []
    try:
        async for chunk in _sse_generator(user_id=1, request=request):
            events.append(chunk)
    finally:
        # Release all acquired slots
        for _ in acquired:
            _SSE_SEMAPHORE.release()

    assert any("too_many_streams" in e for e in events)


async def test_sse_generator_disconnects_cleanly():
    """Generator exits on disconnected request without yielding data."""
    from app.api.v1.endpoints.error_stream import _sse_generator

    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=True)

    mock_conn = AsyncMock()
    mock_conn.is_closed = MagicMock(return_value=False)
    mock_conn.add_listener = AsyncMock()
    mock_conn.remove_listener = AsyncMock()
    mock_conn.close = AsyncMock()

    mock_url = MagicMock()
    mock_url.set = MagicMock(return_value=mock_url)
    mock_url.__str__ = MagicMock(return_value="postgresql://test")

    with patch("asyncpg.connect", return_value=mock_conn):
        with patch("sqlalchemy.engine.url.make_url", return_value=mock_url):
            events = []
            async for chunk in _sse_generator(user_id=5, request=request):
                events.append(chunk)

    # No data events, just clean exit
    assert not any("data:" in e for e in events)
