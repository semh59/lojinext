"""MaxBodySizeMiddleware unit tests (ARCH-016) — dispatch-level, no DB/client."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.infrastructure.middleware.body_size_middleware import MaxBodySizeMiddleware

pytestmark = pytest.mark.unit

CAP = 1000


def _request(headers: dict) -> Request:
    raw = [(k.encode(), str(v).encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "POST", "path": "/x", "headers": raw})


def _mw() -> MaxBodySizeMiddleware:
    return MaxBodySizeMiddleware(app=lambda *a, **k: None, max_body_bytes=CAP)


async def test_rejects_oversized_body():
    mw = _mw()
    call_next = AsyncMock()
    resp = await mw.dispatch(_request({"content-length": CAP + 1}), call_next)
    assert resp.status_code == 413
    call_next.assert_not_awaited()  # rejected before the body is buffered


async def test_allows_body_at_cap():
    mw = _mw()
    sentinel = object()
    call_next = AsyncMock(return_value=sentinel)
    resp = await mw.dispatch(_request({"content-length": CAP}), call_next)
    assert resp is sentinel
    call_next.assert_awaited_once()


async def test_passes_through_when_no_content_length():
    mw = _mw()
    sentinel = object()
    call_next = AsyncMock(return_value=sentinel)
    resp = await mw.dispatch(_request({}), call_next)
    assert resp is sentinel


async def test_passes_through_on_malformed_content_length():
    mw = _mw()
    sentinel = object()
    call_next = AsyncMock(return_value=sentinel)
    resp = await mw.dispatch(_request({"content-length": "not-a-number"}), call_next)
    assert resp is sentinel
