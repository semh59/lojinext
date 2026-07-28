"""
Rate limiting middleware — Redis-backed (distributed), fail-closed.

`app/infrastructure/middleware/rate_limit_middleware.py`'den dalga 17
(platform_infra) denetiminde taşındı — main.py'nin ASGI middleware zinciri
+ logging_middleware.py'nin get_real_client_ip() çağrısı, genuinely
cross-cutting.

Redis path: INCR + EXPIRE per bucket. Atomic and works across multiple workers.
Redis erişilemezse: istek 503 ile reddedilir + CRITICAL log (bkz.
`TASKS/faz2-guvenlik-state-redis.md`) — eskiden burada sessizce tek-worker
in-memory sayaca düşülüyordu (MEMORY §4.1'in tam da şikayet ettiği "çalışıyor
gibi görünüp seyrelmiş" davranış); o fallback kasıtlı olarak kaldırıldı.
"""

import ipaddress
import os
from typing import List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

_SKIP_PATHS = frozenset(
    [
        "/docs",
        "/openapi.json",
        "/",
    ]
)

# Login endpoint gets a tighter limit: 10 attempts per minute per IP.
_AUTH_PATHS = frozenset(["/api/v1/auth/token"])
_AUTH_LIMIT = 10

# Trusted reverse-proxy CIDRs — only accept X-Forwarded-For from these.
# Covers RFC-1918 + loopback + typical Docker bridge networks.
_TRUSTED_PROXY_NETS: List[ipaddress.IPv4Network] = [
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
]

# Allow operators to extend trusted CIDRs via env (comma-separated CIDR list).
_extra = os.getenv("TRUSTED_PROXY_CIDRS", "")
for _cidr in filter(None, _extra.split(",")):
    try:
        _TRUSTED_PROXY_NETS.append(ipaddress.IPv4Network(_cidr.strip(), strict=False))
    except ValueError:
        logger.warning("Invalid TRUSTED_PROXY_CIDRS entry ignored: %s", _cidr.strip())


def _is_trusted_proxy(host: str) -> bool:
    """Return True if the direct TCP peer is a trusted proxy."""
    try:
        addr = ipaddress.IPv4Address(host)
        return any(addr in net for net in _TRUSTED_PROXY_NETS)
    except ValueError:
        return False


def get_real_client_ip(request: "Request") -> str:
    """Return the real client IP, honouring X-Forwarded-For only from trusted proxies."""
    direct_host = request.client.host if request.client else ""
    if direct_host and _is_trusted_proxy(direct_host):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return direct_host or "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP+user+path rate limiter. Redis-backed, fail-closed on Redis outage."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60

    async def dispatch(self, request: Request, call_next):
        import sys

        from app.config import settings

        if (
            request.url.path in _SKIP_PATHS
            or not getattr(settings, "RATE_LIMIT_ENABLED", True)
            or settings.ENVIRONMENT in ("dev", "test")
            or "pytest" in sys.modules
        ):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        user_id = getattr(request.state, "user_id", None) or request.headers.get(
            "X-User-ID"
        )
        bucket = f"{client_ip}:{user_id or 'anon'}:{request.url.path}"

        # Auth endpoints use a tighter per-IP limit (brute-force protection).
        limit = (
            _AUTH_LIMIT if request.url.path in _AUTH_PATHS else self.requests_per_minute
        )

        from v2.modules.platform_infra.context.request_context import (
            get_correlation_id,
        )

        try:
            count = await self._increment_redis(bucket)
        except Exception as exc:
            logger.critical(
                "Rate limiter unavailable (Redis unreachable): %s — failing closed "
                "for bucket=%s",
                exc,
                bucket,
            )
            from v2.modules.platform_infra.monitoring import (
                ErrorEvent,
                ErrorLayer,
                ErrorSeverity,
                aemit,
            )

            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.SECURITY,
                    category="rate_limiter_degraded",
                    severity=ErrorSeverity.CRITICAL,
                    message="RateLimitMiddleware failing closed — Redis unreachable",
                    metadata={"bucket": bucket, "reason": str(exc)},
                )
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "RATE_LIMITER_UNAVAILABLE",
                        "message": "Service temporarily unavailable. Please try again shortly.",
                        "trace_id": get_correlation_id() or "",
                    }
                },
            )

        if count > limit:
            logger.warning("Rate limit exceeded bucket=%s count=%d", bucket, count)
            # 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): eskiden
            # {"detail": "..."} dönüyordu — projenin standart hata zarfını
            # ({"error": {"code","message","trace_id"}}, bkz. main.py
            # http_exception_handler) bypass ediyordu, frontend'in genel
            # hata-zarfı ayrıştırıcısı bunu tanımıyordu.
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again later.",
                        "trace_id": get_correlation_id() or "",
                    }
                },
                headers={"Retry-After": str(self.window_size)},
            )

        return await call_next(request)

    async def _increment_redis(self, bucket: str) -> int:
        """Returns the new count in Redis. Raises if Redis is unavailable —
        callers must fail closed (no silent in-memory fallback, see module
        docstring)."""
        from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

        mgr = get_pubsub_manager()
        if mgr._redis is None:
            raise RuntimeError("no redis client configured")
        key = f"rl:{bucket}"
        count = await mgr._redis.incr(key)
        if count == 1:
            await mgr._redis.expire(key, self.window_size)
        return count

    def _get_client_ip(self, request: Request) -> str:
        return get_real_client_ip(request)
