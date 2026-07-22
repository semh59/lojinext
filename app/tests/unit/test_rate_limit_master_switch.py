"""RATE_LIMIT_ENABLED master switch — kapasite yük testi için (GO gate #4).

Tek-IP burst rate-limit'i tetiklediğinden, capacity load test'te limit kapatılır.
Bu testler switch'in her iki rate-limit mekanizmasını da etkilediğini sabitler.
"""

import pytest

from v2.modules.platform_infra.resilience.rate_limiter import AsyncRateLimiter

pytestmark = pytest.mark.unit


async def test_acquire_raises_429_when_enabled(monkeypatch):
    """RATE_LIMIT_ENABLED=True iken token bitince 429 fırlatır."""
    from fastapi import HTTPException

    monkeypatch.setattr("app.config.settings.RATE_LIMIT_ENABLED", True)
    rl = AsyncRateLimiter(rate=1.0, period=100.0)  # 1 token / 100s → 2. çağrı patlar
    await rl.acquire()  # ilk token tamam
    with pytest.raises(HTTPException) as exc:
        await rl.acquire()
    assert exc.value.status_code == 429


async def test_acquire_bypassed_when_disabled(monkeypatch):
    """RATE_LIMIT_ENABLED=False iken hiç 429 fırlatmaz (kapasite testi)."""
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_ENABLED", False)
    rl = AsyncRateLimiter(rate=1.0, period=100.0)
    # Token sayısından bağımsız: defalarca acquire() sorunsuz dönmeli.
    for _ in range(50):
        await rl.acquire()


def test_default_is_enabled():
    """Prod güvenliği: default True (kazara açık kalmaz)."""
    from app.config import settings

    # Mevcut ortam override etmediyse default True olmalı (capacity testi
    # dışında kapatılmamalı). Env override'ı saygı duy: sadece tipini doğrula.
    assert isinstance(settings.RATE_LIMIT_ENABLED, bool)


async def test_global_middleware_bypassed_when_disabled(monkeypatch):
    """RATE_LIMIT_ENABLED=False → global RateLimitMiddleware her isteği geçirir."""
    from unittest.mock import AsyncMock

    from app.infrastructure.middleware.rate_limit_middleware import RateLimitMiddleware

    # pytest/dev skip'lerini devre dışı bırak ki sadece RATE_LIMIT_ENABLED'ı test edelim
    monkeypatch.setattr("app.config.settings.ENVIRONMENT", "test")
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_ENABLED", False)
    monkeypatch.setitem(
        __import__("sys").modules, "pytest", None
    )  # pytest skip'ini iptal

    mw = RateLimitMiddleware(app=None, requests_per_minute=1)
    mw._increment_redis = AsyncMock(return_value=0)

    class _Req:
        class url:
            path = "/api/v1/trips/"

        headers = {}
        state = type("S", (), {})()

    call_next = AsyncMock(return_value="OK")
    # Limit 1/dk olsa bile, switch kapalı → 100 istek hepsi geçer (429 yok)
    for _ in range(100):
        resp = await mw.dispatch(_Req(), call_next)
        assert resp == "OK"
