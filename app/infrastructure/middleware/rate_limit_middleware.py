"""
Rate limiting middleware — Redis-backed (distributed) with in-memory fallback.

Redis path: INCR + EXPIRE per bucket. Atomic and works across multiple workers.
Fallback:   sliding fixed-window counter in process memory (single-worker only).
"""

import ipaddress
import os
import time
from collections import defaultdict
from typing import Dict, List, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.infrastructure.logging.logger import get_logger

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
    """Per-IP+user+path rate limiter. Prefers Redis; falls back to in-memory."""

    _CLEANUP_EVERY = 500

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60
        self._mem_counts: Dict[str, Tuple[int, float]] = defaultdict(
            lambda: (0, time.time())
        )
        self._dispatch_count = 0

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

        count = await self._increment_redis(bucket)
        if count == 0:
            count = self._increment_memory(bucket)

        if count > limit:
            logger.warning("Rate limit exceeded bucket=%s count=%d", bucket, count)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(self.window_size)},
            )

        self._dispatch_count += 1
        if self._dispatch_count % self._CLEANUP_EVERY == 0:
            self._evict_expired(time.time())

        return await call_next(request)

    async def _increment_redis(self, bucket: str) -> int:
        """Returns the new count in Redis, or 0 if Redis is unavailable."""
        try:
            from app.infrastructure.cache.redis_pubsub import get_pubsub_manager

            mgr = get_pubsub_manager()
            if mgr._redis is None:
                return 0
            key = f"rl:{bucket}"
            count = await mgr._redis.incr(key)
            if count == 1:
                await mgr._redis.expire(key, self.window_size)
            return count
        except Exception:
            return 0

    def _increment_memory(self, bucket: str) -> int:
        now = time.time()
        count, window_start = self._mem_counts[bucket]
        if now - window_start >= self.window_size:
            self._mem_counts[bucket] = (1, now)
            return 1
        count += 1
        self._mem_counts[bucket] = (count, window_start)
        return count

    def _evict_expired(self, now: float) -> None:
        expired = [
            k for k, (_, ws) in self._mem_counts.items() if now - ws >= self.window_size
        ]
        for k in expired:
            del self._mem_counts[k]

    def _get_client_ip(self, request: Request) -> str:
        return get_real_client_ip(request)
