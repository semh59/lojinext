"""
Rate limiter adapter.

`app/api/middleware/rate_limiter.py`'den taşındı — main.py'nin
`app.state.limiter` wiring'i + 5 iş modülünün endpoint'lerindeki
`@limiter.limit(...)` decorator'ları, genuinely cross-cutting. Bu,
platform_infra'nın kendi Redis-backed `resilience/rate_limiter.py`'sinden
(`AsyncRateLimiter`/`RateLimiterDependency`) TAMAMEN AYRI bir mekanizma —
slowapi'nin senkron decorator-tabanlı rate limiting'i.

If `slowapi` is not installed, expose a no-op limiter so module imports do not
break in lightweight test/dev environments.

`storage_uri=settings.REDIS_URL`: slowapi's underlying `limits` library talks
to the SAME Redis instance as the rest of the app (`redis` package, already a
hard dependency — no new one added) instead of its own default in-memory
storage. This closes the last per-process counter in MEMORY §4.1's list
(bkz. `TASKS/faz2-guvenlik-state-redis.md`). If Redis is unreachable, `limits`
raises `redis.exceptions.ConnectionError` from inside the `@limiter.limit(...)`
check — main.py's `redis_unavailable_handler` turns that into a 503
(fail-closed, no silent per-worker fallback).
"""

import logging
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Type-check against the real classes; the runtime fallback below is only
    # for environments where slowapi is not installed.
    from slowapi import Limiter
    from slowapi.util import get_remote_address
else:
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
    except ImportError:
        Limiter = None
        get_remote_address = None


class _NoopLimiter:
    def limit(self, *_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator


def _build_limiter(
    environment: str, *, rate_limit_enabled: bool = True, redis_url: str = ""
) -> Any:
    """Resolve the rate limiter instance.

    2026-07-01 prod-grade denetimi P1: slowapi eksikse önceki davranış
    sessizce `_NoopLimiter`'a düşüp uygulamanın rate-limit'siz şekilde ayağa
    kalkmasına izin veriyordu (fail-open) — brute-force/DoS korumasının fark
    edilmeden kaybolması riski. Prod'da bu artık fail-closed: uygulama
    başlamayı reddeder. Dev/test'te (slowapi'nin kurulu olmayabileceği hafif
    ortamlar) eski fail-open davranışı, yüksek görünürlüklü critical log ile
    korunur. Ayrı bir fonksiyon olarak çıkarıldı ki bu dallanma modülü
    reload etmeden unit test edilebilsin.
    """
    if Limiter:
        return Limiter(
            key_func=get_remote_address,
            enabled=rate_limit_enabled,
            storage_uri=redis_url or None,
        )

    if environment == "prod":
        raise RuntimeError(
            "slowapi is not installed — refusing to start in production "
            "without rate limiting. Install slowapi or explicitly set "
            "RATE_LIMIT_ENABLED=False if this is intentional."
        )

    _log.critical(
        "slowapi is not installed — ALL RATE LIMITS ARE DISABLED. "
        "Install slowapi to enable rate limiting."
    )
    return _NoopLimiter()


def _resolve_environment() -> str:
    # 2026-07-01 derin kontrol: genel `except Exception` burada, `app.config`
    # gerçekten bozuksa (örn. bir ayar doğrulama hatası) prod'da bile sessizce
    # "dev"e düşüp yukarıdaki fail-closed niyetini baltalayabilirdi. Sadece
    # modülün hiç mevcut olmadığı (ImportError) durumunu yutuyoruz — başka
    # her hata yükselsin (zaten uygulama geneli çökerdi, burada gizlemenin
    # faydası yok).
    try:
        from app.config import settings as _settings

        return getattr(_settings, "ENVIRONMENT", "dev")
    except ImportError:
        return "dev"


def _resolve_rate_limit_enabled() -> bool:
    try:
        from app.config import settings as _settings

        return getattr(_settings, "RATE_LIMIT_ENABLED", True)
    except ImportError:
        return True


def _resolve_redis_url() -> str:
    try:
        from app.config import settings as _settings

        return getattr(_settings, "REDIS_URL", "")
    except ImportError:
        return ""


limiter: Any = _build_limiter(
    _resolve_environment(),
    rate_limit_enabled=_resolve_rate_limit_enabled(),
    redis_url=_resolve_redis_url(),
)
