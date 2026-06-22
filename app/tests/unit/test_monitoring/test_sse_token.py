"""SSE token creation and stream auth unit tests."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The functions under test import get_pubsub_manager lazily inside function bodies,
# so we must patch it at the definition site.
_PUBSUB_PATH = "app.infrastructure.cache.redis_pubsub.get_pubsub_manager"


# ─── POST /error-stream-token ──────────────────────────────────────────────────


@pytest.mark.unit
async def test_create_sse_token_returns_token_and_expiry():
    """create_sse_token returns dict with 'token' (UUID) and 'expires_in'=90."""
    from app.api.v1.endpoints.error_stream import create_sse_token

    mock_user = MagicMock()
    mock_user.id = 42

    mock_redis = AsyncMock()
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(_PUBSUB_PATH, return_value=mock_mgr):
        result = await create_sse_token(current_user=mock_user)

    assert "token" in result
    assert result["expires_in"] == 90
    # token must be a valid UUID
    uuid.UUID(result["token"])


@pytest.mark.unit
async def test_create_sse_token_stores_in_redis_with_ttl():
    """Token stored at sse_token:{uuid} with ex=90."""
    from app.api.v1.endpoints.error_stream import create_sse_token

    mock_user = MagicMock()
    mock_user.id = 7

    mock_redis = AsyncMock()
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(_PUBSUB_PATH, return_value=mock_mgr):
        result = await create_sse_token(current_user=mock_user)

    mock_redis.set.assert_called_once()
    args, kwargs = mock_redis.set.call_args
    key, payload_str = args[0], args[1]
    assert key == f"sse_token:{result['token']}"
    assert json.loads(payload_str)["user_id"] == 7
    assert kwargs.get("ex") == 90


# ─── GET /error-stream — auth checks ──────────────────────────────────────────


@pytest.mark.unit
async def test_error_stream_no_token_returns_401():
    """?token absent → 401."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {}

    response = await error_stream(request=mock_request)
    assert response.status_code == 401


@pytest.mark.unit
async def test_error_stream_empty_token_returns_401():
    """?token= (empty string) → 401."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"token": ""}

    response = await error_stream(request=mock_request)
    assert response.status_code == 401


@pytest.mark.unit
async def test_error_stream_nonexistent_token_returns_401():
    """Unknown token (Redis returns None) → 401."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"token": "nonexistent-token-xyz"}

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(_PUBSUB_PATH, return_value=mock_mgr):
        response = await error_stream(request=mock_request)

    assert response.status_code == 401


@pytest.mark.unit
async def test_error_stream_valid_token_deleted_before_db_check():
    """Valid token in Redis → deleted immediately before DB lookup."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    token = "valid-test-token-abc"
    user_payload = json.dumps({"user_id": 1})

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=user_payload)
    mock_redis.delete = AsyncMock()
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"token": token}

    # DB lookup returns None → 401/403, but delete was already called
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(_PUBSUB_PATH, return_value=mock_mgr),
        patch(
            "app.database.connection.AsyncSessionLocal",
            return_value=mock_session,
        ),
    ):
        response = await error_stream(request=mock_request)

    # Token must be deleted regardless of auth outcome
    mock_redis.delete.assert_called_once_with(f"sse_token:{token}")
    # User not found → 401 or 403
    assert response.status_code in (401, 403)
