"""
Rate Limiter - Async API Request Throttling
External API'lere yapılan istekleri sınırlar.
"""

import asyncio
from functools import wraps
from typing import Dict, Optional

from app.config import settings
from app.infrastructure.logging.logger import get_logger

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
    """FastAPI Dependency for Rate Limiting"""

    def __init__(
        self,
        key: str,
        rate: float = settings.EXTERNAL_API_RATE_LIMIT,
        period: float = 1.0,
    ):
        self.key = key
        self.rate = rate
        self.period = period

    async def __call__(self):
        limiter = await RateLimiterRegistry.get(self.key, self.rate, self.period)
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
