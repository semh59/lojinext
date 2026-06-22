"""
Unit tests for CacheManager.

0-mock: the autouse fixture `mock_redis_for_cache_manager` in app/tests/conftest.py
now binds CacheManager to a REAL Redis (isolated logical DB, flushed per test) and
resets CacheManager._instance, so every test exercises real set/get/delete round-trips
rather than asserting on a MagicMock.
"""

import pytest

from app.infrastructure.cache.cache_manager import (
    CacheManager,
    get_cache_manager,
)

pytestmark = pytest.mark.unit


class TestCacheManager:
    async def test_basic_initialization(self):
        """CacheManager is a singleton and initialises stats to zero."""
        cm = CacheManager()

        assert cm is not None
        stats = cm.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["sets"] == 0

    async def test_happy_path(self):
        """set() stores the value in real Redis; get() round-trips it back."""
        cm = CacheManager()
        stored_value = {"name": "Ahmet", "km": 500}

        cm.set("vehicle:1", stored_value, ttl_seconds=300)
        result = cm.get("vehicle:1")

        assert result == stored_value

    async def test_error_handling(self):
        """get() on missing key returns None and increments miss counter."""
        cm = CacheManager()
        # mock_redis_for_cache_manager default: get returns None

        result = cm.get("nonexistent:key")

        assert result is None
        stats = cm.get_stats()
        assert stats["misses"] == 1

    async def test_edge_case_empty(self):
        """_validate_key raises ValueError for empty string key."""
        cm = CacheManager()

        with pytest.raises(ValueError, match="non-empty string"):
            cm.get("")

    async def test_edge_case_none(self):
        """_validate_key raises ValueError for None key."""
        cm = CacheManager()

        with pytest.raises((ValueError, TypeError)):
            cm.get(None)  # type: ignore[arg-type]

    async def test_delete_removes_key(self):
        """delete() removes a previously stored key and returns True (real Redis)."""
        cm = CacheManager()
        cm.set("mykey", "v", ttl_seconds=60)

        result = cm.delete("mykey")

        assert result is True
        assert cm.get("mykey") is None

    async def test_return_type_validation(self):
        """get_stats() returns dict with hit_rate_pct key after a real hit."""
        cm = CacheManager()

        # Record one real hit
        cm.set("somekey", "value", ttl_seconds=60)
        cm.get("somekey")

        stats = cm.get_stats()

        assert isinstance(stats, dict)
        assert "hit_rate_pct" in stats
        assert isinstance(stats["hit_rate_pct"], float)

    def test_service_exists(self):
        """get_cache_manager() returns a CacheManager instance."""
        cm = get_cache_manager()

        assert isinstance(cm, CacheManager)

    async def test_singleton_pattern(self):
        """Two instantiations return the same object."""
        cm1 = CacheManager()
        cm2 = CacheManager()

        assert cm1 is cm2

    async def test_validate_key_sensitive_pattern_rejected(self):
        """Keys matching sensitive patterns (password, token, secret) are rejected."""
        cm = CacheManager()

        with pytest.raises(ValueError, match="sensitive"):
            cm.get("user_password_hash")

        with pytest.raises(ValueError, match="sensitive"):
            cm.set("auth_token", "val")

    async def test_validate_key_directory_traversal_rejected(self):
        """Keys containing ../ are rejected."""
        cm = CacheManager()

        with pytest.raises(ValueError, match="traversal"):
            cm.get("../../etc/passwd")

    async def test_validate_key_too_long_rejected(self):
        """Keys longer than 256 chars are rejected."""
        cm = CacheManager()
        long_key = "k" * 257

        with pytest.raises(ValueError, match="256"):
            cm.get(long_key)

    async def test_set_increments_sets_stat(self, mock_redis_for_cache_manager):
        """set() increments the 'sets' counter in stats."""
        cm = CacheManager()

        cm.set("stat_key", 123, ttl_seconds=60)

        stats = cm.get_stats()
        assert stats["sets"] == 1

    async def test_delete_pattern_calls_scan_and_delete(self):
        """delete_pattern() SCANs and deletes all matching keys (real Redis)."""
        cm = CacheManager()

        cm.set("arac:1", "a", ttl_seconds=60)
        cm.set("arac:2", "b", ttl_seconds=60)

        count = cm.delete_pattern("arac:*")

        assert count == 2
        assert cm.get("arac:1") is None
        assert cm.get("arac:2") is None

    async def test_delete_pattern_blocks_directory_traversal(self):
        """delete_pattern() raises ValueError on traversal patterns."""
        cm = CacheManager()

        with pytest.raises(ValueError, match="traversal"):
            cm.delete_pattern("../secret*")

    async def test_hit_rate_calculation(self):
        """hit_rate_pct from real hits/misses: 2 stored+read hits + 2 misses → 50%."""
        cm = CacheManager()
        # Autouse fixture resets _instance but guard against any residual stats.
        with cm._lock:
            cm._stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

        cm.set("k1", "v", ttl_seconds=60)
        cm.set("k3", "v", ttl_seconds=60)

        cm.get("k1")  # hit
        cm.get("k2")  # miss (never set)
        cm.get("k3")  # hit
        cm.get("k4")  # miss (never set)

        stats = cm.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["hit_rate_pct"] == 50.0
