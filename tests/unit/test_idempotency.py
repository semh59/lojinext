import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from app.infrastructure.resilience.idempotency import IdempotencyGuard


@pytest.mark.asyncio
async def test_idempotency_guard_no_key():
    guard = IdempotencyGuard()
    request = MagicMock(spec=Request)
    request.headers = {}

    # Should return silently
    result = await guard(request)
    assert result is None


@pytest.mark.asyncio
async def test_idempotency_guard_first_request():
    """First call with a fresh unique key must not raise — real Redis set_nx inserts it."""
    guard = IdempotencyGuard()
    request = MagicMock(spec=Request)
    unique_key = f"test-{uuid.uuid4()}"
    request.headers = {"X-Idempotency-Key": unique_key}
    request.state = MagicMock()
    request.state.user = MagicMock(id=1)

    # Must not raise — key was not present in Redis DB 15
    await guard(request)


@pytest.mark.asyncio
async def test_idempotency_guard_duplicate_request():
    """Second call with the same key must raise 409 — real Redis set_nx sees the existing key."""
    guard = IdempotencyGuard()
    request = MagicMock(spec=Request)
    unique_key = f"test-{uuid.uuid4()}"
    request.headers = {"X-Idempotency-Key": unique_key}
    request.state = MagicMock()
    request.state.user = MagicMock(id=1)

    # First call sets the key
    await guard(request)

    # Second call with same key must raise 409
    with pytest.raises(HTTPException) as exc_info:
        await guard(request)

    assert exc_info.value.status_code == 409
    assert "zaten işleniyor" in exc_info.value.detail
