"""
Rate Limiter - Async API Request Throttling
External API'lere yapılan istekleri sınırlar.
"""

import asyncio
import hashlib
from functools import wraps
from typing import Dict, Optional

from fastapi import Request

from app.config import settings
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


class AsyncRateLimiter:
    """
    Token Bucket algoritması ile async rate limiter.
    Harici kütüphane bağımlılığı olmadan çalışır.
    """

    def __init__(self, rate: float, period: float = 1.0):
        """
        Args:
            rate: period içinde izin verilen maksimum istek sayısı
            period: süre (saniye)
        """
        self.rate = rate
        self.period = period
        self.tokens = rate
        self._last_update: Optional[float] = None  # Lazy initialization
        self._lock = asyncio.Lock()

    def _get_time(self) -> float:
        """Async-safe zaman alma (lazy init desteği)"""
        try:
            loop = asyncio.get_running_loop()
            return loop.time()
        except RuntimeError:
            # Event loop yoksa fallback
            import time

            return time.monotonic()

    async def acquire(self):
        """Bir token al, yoksa 429 fırlat"""
        # Master switch — kapasite yük testinde rate-limit'i tamamen atla.
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return
        async with self._lock:
            now = self._get_time()

            # Lazy initialization
            if self._last_update is None:
                self._last_update = now

            elapsed = now - self._last_update
            self.tokens = min(
                self.rate, self.tokens + elapsed * (self.rate / self.period)
            )
            self._last_update = now

            if self.tokens < 1:
                # API Audit Requirement: Reject immediately with 429
                wait_time = (1 - self.tokens) * (self.period / self.rate)
                logger.warning(f"Rate limit exceeded. Try again in {wait_time:.2f}s")
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": str(int(wait_time) + 1)},
                )
            else:
                self.tokens -= 1

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
    _lock = asyncio.Lock()

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
            name: Limiter adı (örn: "openroute", "weather")
            rate: Saniyede izin verilen istek sayısı
            period: Süre (saniye)
        """
        async with cls._lock:
            if name not in cls._limiters:
                cls._limiters[name] = AsyncRateLimiter(rate, period)
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
            cls._limiters[name] = AsyncRateLimiter(rate, period)
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
            async with limiter:
                # acquire method called by __aenter__
                # But our acquire logic was updated to raise exception.
                pass
            return await func(*args, **kwargs)

        return wrapper

    return decorator
