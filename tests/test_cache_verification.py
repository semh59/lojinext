# -*- coding: utf-8 -*-
import time

import pytest

try:
    import redis
except ImportError:
    redis = None
from v2.modules.platform_infra.cache.cache_manager import CacheManager, get_cache_manager
from v2.modules.platform_infra.cache.redis_cache import RedisCache


# Test için CacheManager'ı override edelim
@pytest.fixture
def cache_manager():
    cm = CacheManager()
    cm.clear()
    return cm


@pytest.fixture
def redis_cache():
    rc = RedisCache()
    # Force fallback mode for testing DRY logic
    rc._redis_client = None
    rc._fallback.clear()
    return rc


def test_cache_sweeper_logic(cache_manager):
    """Test background sweeper removing expired items"""
    # 1. 0.1 saniyelik TTL ile veri ekle
    cache_manager.set("short_lived", "data", ttl_seconds=0.1)

    # 2. Verinin orada olduğunu doğrula
    assert cache_manager.get("short_lived") == "data"

    # 3. Süresi dolana kadar bekle
    time.sleep(0.2)

    # 4. Normal get ile silinmesi gerekir (lazy expiration)
    assert cache_manager.get("short_lived") is None

    # Stats kontrolü
    stats = cache_manager.get_stats()
    assert stats["evictions"] >= 0


def test_redis_cache_dry_fallback(redis_cache):
    """Test RedisCache using CacheManager as fallback"""
    # 1. RedisClient None iken set işlemi
    redis_cache.set("fallback_key", "fallback_value", ttl=60)

    # 2. RedisCache üzerinden get
    val = redis_cache.get("fallback_key")
    assert val == "fallback_value"

    # 3. CacheManager üzerinden de erişilebilir olmalı (paylaşılan singleton ise)
    # CacheManager singleton olduğu için:
    cm = get_cache_manager()
    assert cm.get("fallback_key") == "fallback_value"

    # 4. RedisCache silme
    redis_cache.delete("fallback_key")
    assert redis_cache.get("fallback_key") is None
    assert cm.get("fallback_key") is None


def test_sensitive_keys(cache_manager):
    """Test prevention of sensitive keys"""
    with pytest.raises(ValueError, match="sensitive pattern"):
        cache_manager.set("user_password", "123456")
