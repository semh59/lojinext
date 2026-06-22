"""
Correlation ID Middleware
Her request'e unique ID atar, response header'a ekler
Distributed tracing için gerekli
"""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.infrastructure.context.request_context import clear_context, set_correlation_id
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# UUID4 format regex
UUID4_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$",
    re.IGNORECASE,
)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Her HTTP isteğine correlation ID atar.

    Header: X-Correlation-ID

    Kullanım:
        app.add_middleware(CorrelationMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        # Gelen header'dan al veya yeni oluştur
        correlation_id = request.headers.get("X-Correlation-ID")

        # UUID format validation
        if correlation_id and not UUID4_PATTERN.match(correlation_id):
            logger.warning(
                f"Invalid correlation ID format received: {correlation_id[:50]}"
            )
            correlation_id = None  # Geçersiz format, yeni üret

        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Context'e ayarla (tüm async call'larda erişilebilir)
        set_correlation_id(correlation_id)

        # Debug log
        logger.debug(
            f"Request started: {request.method} {request.url.path} [cid={correlation_id[:8]}]"
        )

        try:
            response = await call_next(request)
            # Response header'a ekle
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            # Context'i temizle
            clear_context()
