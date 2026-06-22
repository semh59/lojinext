"""Global request body-size cap — a DoS backstop.

Rejects requests whose declared ``Content-Length`` exceeds the configured limit
*before* the body is read into memory, returning 413. Per-endpoint upload checks
(e.g. the 10 MB Excel cap) remain the tight control; this is the coarse backstop
against absurd bodies that would otherwise be buffered in full.

Note: a request without a ``Content-Length`` (chunked transfer) is passed
through — the ASGI server enforces its own stream limits there. The common
attack (a single large declared body) is what this stops cheaply.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds ``max_body_bytes`` (413)."""

    def __init__(self, app, max_body_bytes: int):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = -1
            if declared > self.max_body_bytes:
                logger.warning(
                    "Request body too large: %d bytes > %d cap (path=%s)",
                    declared,
                    self.max_body_bytes,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "REQUEST_ENTITY_TOO_LARGE",
                            "message": "İstek gövdesi çok büyük.",
                        }
                    },
                )
        return await call_next(request)
