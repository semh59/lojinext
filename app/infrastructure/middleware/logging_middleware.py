import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from v2.modules.platform_infra.context.request_context import get_correlation_id
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Enterprise-grade Request Logging Middleware.

    Özellikler:
    - X-Correlation-ID takibi (Distributed tracing için)
    - İstek süresi ölçümü (Latency)
    - İstek ve yanıt detaylarının loglanması (JSON)
    - Hassas verilerin maskelenmesi (Body logging kapalı tutulur)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    def _mask_path(self, path: str) -> str:
        """Query parametrelerindeki hassas verileri maskele"""
        import re

        # token=..., password=..., key=..., secret=...
        pattern = r"(token|password|key|secret|api_key)=([^&]+)"
        return re.sub(pattern, r"\1=***", path)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # 1. Correlation ID — CorrelationMiddleware tarafından context'e zaten set edilmiştir
        correlation_id = get_correlation_id()

        # 2. İstek Logu (Structured)
        client_host = request.client.host if request.client else "unknown"

        masked_path = self._mask_path(str(request.url))
        # Sadece path kısmını al (query param dahil tüm URL'i maskeledik)

        request_log = {
            "event": "request_received",
            "correlation_id": correlation_id,
            "method": request.method,
            "path": masked_path,
            "client_ip": client_host,
            "user_agent": request.headers.get("user-agent", "unknown"),
        }
        logger.info(
            f"Incoming Request: {request.method} {masked_path}", extra=request_log
        )

        try:
            # Reset N+1 query counter for this request
            from v2.modules.platform_infra.monitoring.db_probe import (
                reset_query_counter,
                reset_recent_queries,
            )

            reset_query_counter()
            reset_recent_queries()

            # Path ContextVar — n_plus_one / slow_query event'lerinin hangi
            # endpoint'te tetiklendiğini bilebilmek için
            from v2.modules.platform_infra.context.request_context import (
                set_request_path,
            )

            set_request_path(f"{request.method} {request.url.path}")

            # 3. İsteğin İşlenmesi
            response = await call_next(request)

            # Response Header'a ID ekle
            response.headers["X-Correlation-ID"] = correlation_id

            # Security probe
            from app.infrastructure.middleware.rate_limit_middleware import (
                get_real_client_ip,
            )
            from v2.modules.platform_infra.monitoring.security_probe import (
                get_brute_force_detector,
                get_rbac_tracker,
            )

            client_ip = get_real_client_ip(request)
            get_brute_force_detector().record(client_ip, response.status_code)
            if response.status_code == 403:
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    get_rbac_tracker().record(user_id, request.url.path)

            # 4. Yanıt Logu (Success)
            process_time = (time.time() - start_time) * 1000  # ms

            # Security headers ekle
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"

            response_log = {
                "event": "request_processed",
                "correlation_id": correlation_id,
                "status_code": response.status_code,
                "latency_ms": round(process_time, 2),
                "path": masked_path,
            }

            # Performans uyarısı (>1s yavaş kabul edilir)
            if process_time > 1000:
                logger.warning(
                    f"Slow Request: {request.method} {request.url.path} took {process_time:.2f}ms",
                    extra=response_log,
                )
            else:
                logger.info(
                    f"Request Completed: {response.status_code}", extra=response_log
                )

            return response

        except Exception as e:
            # 5. Hata Logu (Exception) — WARNING level so Sentry's LoggingIntegration
            # does not create a duplicate event (the re-raise will be captured by
            # sentry_sdk.capture_exception() in unhandled_exception_handler).
            process_time = (time.time() - start_time) * 1000

            error_log = {
                "event": "request_failed",
                "correlation_id": correlation_id,
                "error": str(e),
                "latency_ms": round(process_time, 2),
                "path": request.url.path,
            }
            logger.warning(f"Request Failed: {e!s}", extra=error_log)
            raise e
