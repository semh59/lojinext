"""Executive + Coaching endpoint Redis singleton testleri.

Geçmiş bug: _get_redis() her çağrıda aioredis.from_url(...) ile yeni
bir ConnectionPool yaratıyordu (executive.py 6 endpoint, coaching.py 1
endpoint). Yük altında Redis max_connections'a takılabiliyordu.

Bu test: module-level cache ile aynı instance döndüğünü doğrular.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


class _FakeRedis:
    """aioredis.Redis stub'ı — sadece identity için."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _install_fake_redis(monkeypatch):
    """sys.modules + redis pkg'ye fake aioredis.from_url enjekte eder."""
    import redis  # already imported by aioredis dependency

    fake_mod = types.ModuleType("redis.asyncio")
    fake_mod.from_url = MagicMock(side_effect=lambda *a, **kw: _FakeRedis(**kw))
    monkeypatch.setitem(sys.modules, "redis.asyncio", fake_mod)
    # `import redis.asyncio as aioredis` Python'da redis pkg attribute
    # lookup'una da girer — ikisini birden patch et.
    monkeypatch.setattr(redis, "asyncio", fake_mod, raising=False)
    return fake_mod


@pytest.mark.asyncio
async def test_executive_get_redis_singleton(monkeypatch):
    """executive._get_redis 3 ardışık çağrıda aynı instance dönmeli +
    from_url sadece 1 kez çağrılmalı."""
    from app.api.v1.endpoints import executive as mod

    fake_mod = _install_fake_redis(monkeypatch)
    # Test izolasyonu: önceki test'ten kalan cache'i sıfırla
    monkeypatch.setattr(mod, "_exec_redis", None, raising=False)

    r1 = await mod._get_redis()
    r2 = await mod._get_redis()
    r3 = await mod._get_redis()

    assert r1 is not None, "Fake redis instance dönmedi"
    assert r1 is r2, "İkinci çağrı yeni instance üretti (singleton bozuk)"
    assert r2 is r3
    assert fake_mod.from_url.call_count == 1


@pytest.mark.asyncio
async def test_coaching_get_redis_singleton(monkeypatch):
    """coaching._get_redis 3 ardışık çağrıda aynı instance dönmeli."""
    from v2.modules.driver.api import coaching_routes as mod

    fake_mod = _install_fake_redis(monkeypatch)
    monkeypatch.setattr(mod, "_coaching_redis", None, raising=False)

    r1 = await mod._get_redis()
    r2 = await mod._get_redis()
    r3 = await mod._get_redis()

    assert r1 is not None
    assert r1 is r2
    assert r2 is r3
    assert fake_mod.from_url.call_count == 1


@pytest.mark.asyncio
async def test_executive_redis_none_on_import_error(monkeypatch):
    """redis.asyncio import edilemezse None döner (cache-miss davranışı)."""
    from app.api.v1.endpoints import executive as mod

    monkeypatch.setattr(mod, "_exec_redis", None, raising=False)
    # redis.asyncio modülünü sys.modules'ten çıkar — None bırakırsa
    # `import redis.asyncio` ImportError fırlatır.
    monkeypatch.setitem(sys.modules, "redis.asyncio", None)

    result = await mod._get_redis()
    assert result is None
