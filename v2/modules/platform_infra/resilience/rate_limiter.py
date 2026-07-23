"""
Rate Limiter - Async API Request Throttling
Redis-backed (INCR+EXPIRE fixed-window), shared across all uvicorn workers.

Redis erişilemezse fail-closed: `HTTPException(503)` — sessiz in-memory
fallback yok (bkz. `TASKS/faz2-guvenlik-state-redis.md`). Önceki sürekli-
refill token-bucket algoritması tek-process içindi; bu artık sabit-pencere
sayaca döndü (aynı kanıtlı desen: `rate_limit_middleware.py`'nin
`_increment_redis`'i) — davranış değişikliği kasıtlı, paylaşımlı/doğru
sayım için "smooth" refill feda edildi.
"""

import hashlib
from functools import wraps
from typing import Dict, Optional

from fastapi import HTTPException, Request, status

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


def _get_redis():
    """Shared async Redis client, or None if unavailable (same access point
    as `rate_limit_middleware.py`/`security_probe.py` — one connection)."""
    from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

    mgr = get_pubsub_manager()
    return mgr._redis


class AsyncRateLimiter:
    """Named, Redis-backed fixed-window rate limiter."""

    def __init__(self, rate: float, period: float = 1.0, name: str = "default"):
        """
        Args:
            rate: period içinde izin verilen maksimum istek sayısı
            period: süre (saniye)
            name: Redis key'ini oluşturan mantıksal isim — aynı isimdeki tüm
                worker'lar AYNI Redis key'ini paylaşır (bu, çok-worker
                doğruluğunun kaynağı).
        """
        self.rate = rate
        self.period = period
        self.name = name

    async def acquire(self) -> None:
        """Bir slot al; kapasite doluysa 429, Redis erişilemezse 503 fırlat."""
        # Master switch — kapasite yük testinde rate-limit'i tamamen atla.
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return

        redis = _get_redis()
        if redis is None:
            await self._fail_closed(RuntimeError("no redis client configured"))
            return

        try:
            key = f"ratelimit:{self.name}"
            window_sec = max(int(self.period), 1)
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window_sec)
            if count > self.rate:
                ttl = await redis.ttl(key)
                wait_time = ttl if ttl and ttl > 0 else window_sec
                logger.warning(
                    "Rate limit exceeded for '%s'. Try again in %ss", self.name, wait_time
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": str(int(wait_time) + 1)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            await self._fail_closed(exc)

    async def _fail_closed(self, reason: Exception) -> None:
        from v2.modules.platform_infra.monitoring import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
            aemit,
        )

        logger.critical(
            "Rate limiter '%s' unavailable: Redis unreachable (%s) — failing closed",
            self.name,
            reason,
        )
        await aemit(
            ErrorEvent(
                layer=ErrorLayer.SECURITY,
                category="rate_limiter_degraded",
                severity=ErrorSeverity.CRITICAL,
                message=f"Rate limiter '{self.name}' failing closed — Redis unreachable",
                metadata={"limiter": self.name, "reason": str(reason)},
            )
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable. Please try again shortly.",
        )

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class RateLimiterRegistry:
    """
    Singleton registry for named rate limiters.
    Her API için ayrı limiter oluşturur.
    """

    _limiters: Dict[str, AsyncRateLimiter] = {}

    @classmethod
    async def get(
        cls,
        name: str,
        rate: float = settings.EXTERNAL_API_RATE_LIMIT,
        period: float = 1.0,
    ) -> AsyncRateLimiter:
        """
        Named rate limiter al veya oluştur.

        Args:
            name: Limiter adı (örn: "openroute", "weather") — aynı zamanda
                Redis key'i (bkz. `AsyncRateLimiter.name`)
            rate: Saniyede izin verilen istek sayısı
            period: Süre (saniye)
        """
        if name not in cls._limiters:
            cls._limiters[name] = AsyncRateLimiter(rate, period, name=name)
            logger.info(f"Created rate limiter '{name}': {rate} req/{period}s")
        return cls._limiters[name]

    @classmethod
    def get_sync(
        cls,
        name: str,
        rate: float = settings.EXTERNAL_API_RATE_LIMIT,
        period: float = 1.0,
    ) -> AsyncRateLimiter:
        """Senkron ortamda limiter oluştur (startup için)"""
        if name not in cls._limiters:
            cls._limiters[name] = AsyncRateLimiter(rate, period, name=name)
        return cls._limiters[name]


class RateLimiterDependency:
    """FastAPI Dependency for Rate Limiting.

    ``per_user=True`` (opt-in, default False) buckets by caller identity
    instead of sharing one global bucket for the endpoint. 2026-07-05
    tespiti: global bucket, çok-operatörlü üretimde bir kullanıcının
    upload'unu diğerinin isteğini bloklar. Identity DB'den çözülmez (limiter
    ucuz kalmalı) — ``Authorization`` header varsa onun sha256[:12]'si,
    yoksa ``request.client.host``. Bucket key: ``f"{self.key}:{ident}"``.
    """

    def __init__(
        self,
        key: str,
        rate: float = settings.EXTERNAL_API_RATE_LIMIT,
        period: float = 1.0,
        per_user: bool = False,
    ):
        self.key = key
        self.rate = rate
        self.period = period
        self.per_user = per_user

    def _bucket_key(self, request: Optional[Request]) -> str:
        if not self.per_user:
            return self.key
        ident: Optional[str] = None
        if request is not None:
            auth = request.headers.get("Authorization")
            if auth:
                ident = hashlib.sha256(auth.encode("utf-8")).hexdigest()[:12]
            elif request.client:
                ident = request.client.host
        return f"{self.key}:{ident or 'anon'}"

    # NOTE: annotation must be exactly ``Request`` (not ``Optional[Request]``)
    # so FastAPI's dependency analysis special-cases it (lenient_issubclass
    # check in fastapi.dependencies.utils.analyze_param) and injects the real
    # request instead of trying to build a Pydantic body field from it — an
    # Optional-wrapped annotation isn't a class and raised
    # ``FastAPIError: Invalid args for response field!`` at route
    # registration for every RateLimiterDependency usage, not just per_user
    # ones. The ``= None`` default only matters for direct (non-FastAPI)
    # calls, e.g. in unit tests.
    async def __call__(self, request: Request = None):  # type: ignore[assignment]
        bucket_key = self._bucket_key(request)
        limiter = await RateLimiterRegistry.get(bucket_key, self.rate, self.period)
        await limiter.acquire()


def rate_limited(
    limiter_name: str,
    rate: float = settings.EXTERNAL_API_RATE_LIMIT,
    period: float = 1.0,
):
    """
    Decorator: Fonksiyonu rate limit ile korur.
    NOT: Bu decorator FastAPI dependency injection ile çakışabilir.
    Mümkünse Depends(RateLimiterDependency(...)) kullanın.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            limiter = await RateLimiterRegistry.get(limiter_name, rate, period)
            await limiter.acquire()
            return await func(*args, **kwargs)

        return wrapper

    return decorator
