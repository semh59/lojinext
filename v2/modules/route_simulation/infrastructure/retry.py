"""Async retry helper with exponential backoff (Phase 2.4).

`app/infrastructure/resilience/retry.py`'den dalga 17 (platform-infra)
denetiminde taşındı — tek çağıranı route_simulation (`mapbox_client.py`/
`open_meteo_client.py`), genel-amaçlı bir platform-infra soyutlaması değil.

Plan §10 risk satırı: "Mapbox quota/cost" + ek "Open-Meteo SLA".
Dış HTTP servislerine transient 5xx, timeout veya network hatasında
3 deneme exponential backoff (0.5s → 1s → 2s, default).

4xx (auth, validation, 429 rate limit) instant fail — caller body
'sini yeni request'le tekrar etmesi gerekir, retry boşa.

Pattern:
    async def fetch(...) -> Response | None:
        async with httpx.AsyncClient() as c:
            r = await c.get(...)
            return r

    result = await with_async_retry(fetch, max_attempts=3)
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Tuple, TypeVar

import httpx

from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Network'te transient sayılan istisnalar
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[type[BaseException], ...] = (
    httpx.RequestError,  # connect/read/write/timeout/network
    asyncio.TimeoutError,
    ConnectionError,
)


async def with_async_retry(
    coro_fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay_s: float = 0.5,
    backoff_factor: float = 2.0,
    retry_on: Tuple[type[BaseException], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    label: str = "request",
    **kwargs: Any,
) -> T:
    """coro_fn'i deneme-yanılma ile çağır.

    Args:
        coro_fn: async fonksiyon
        max_attempts: toplam deneme sayısı (>=1)
        base_delay_s: ilk retry öncesi bekleme
        backoff_factor: her denemede çarpılır (1.0 = sabit, 2.0 = expo)
        retry_on: tekrar denenecek exception sınıfları
        label: log için açıklayıcı isim
        *args, **kwargs: coro_fn'e geçer

    Returns:
        coro_fn'in başarılı sonucu

    Raises:
        Son denemenin exception'ı (max_attempts tükenince).
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return await coro_fn(*args, **kwargs)
        except retry_on as exc:
            last_exc = exc
            if attempt + 1 >= max_attempts:
                logger.warning(
                    "%s: %d/%d attempts exhausted, giving up: %s",
                    label,
                    attempt + 1,
                    max_attempts,
                    exc,
                )
                raise
            delay = base_delay_s * (backoff_factor**attempt)
            logger.info(
                "%s: attempt %d/%d failed (%s), retrying in %.2fs",
                label,
                attempt + 1,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    # Unreachable; mypy guard
    assert last_exc is not None
    raise last_exc


__all__ = ["with_async_retry", "DEFAULT_RETRYABLE_EXCEPTIONS"]
