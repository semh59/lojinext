"""Tests for Redis-backed CacheManager."""

import pickle
from unittest.mock import MagicMock, patch

import pytest

import app.infrastructure.cache.cache_manager as cm_mod

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_redis():
    r = MagicMock()
    r.get.return_value = None
    r.scan_iter.return_value = iter([])
    return r


@pytest.fixture
def cm(mock_redis):
    with patch("redis.from_url", return_value=mock_redis):
        # Reset singleton so we get a fresh instance
        import app.infrastructure.cache.cache_manager as cm_mod

        cm_mod.CacheManager._instance = None
        manager = cm_mod.CacheManager()
    manager._redis = mock_redis
    yield manager, mock_redis
    # Cleanup singleton
    cm_mod.CacheManager._instance = None


def _signed(value: object) -> bytes:
    """Helper: pickle + HMAC-sign, matches what CacheManager.set() stores."""
    return cm_mod._sign(pickle.dumps(value))


def test_set_calls_psetex_with_prefix(cm):
    manager, mock_redis = cm
    manager.set("mykey", {"x": 1}, ttl_seconds=120)
    mock_redis.psetex.assert_called_once()
    args = mock_redis.psetex.call_args[0]
    assert args[0] == "cm:mykey"
    assert args[1] == 120_000  # milliseconds
    # Strip HMAC prefix before checking
    assert pickle.loads(cm_mod._verify_and_strip(args[2])) == {"x": 1}


def test_get_miss_returns_none(cm):
    manager, mock_redis = cm
    mock_redis.get.return_value = None
    assert manager.get("nokey") is None


def test_get_hit_returns_value(cm):
    manager, mock_redis = cm
    mock_redis.get.return_value = _signed({"y": 2})
    assert manager.get("mykey") == {"y": 2}


def test_delete_calls_redis_delete(cm):
    manager, mock_redis = cm
    mock_redis.delete.return_value = 1
    assert manager.delete("mykey") is True


def test_delete_missing_key_returns_false(cm):
    manager, mock_redis = cm
    mock_redis.delete.return_value = 0
    assert manager.delete("nokey") is False


def test_stats_tracks_hits_and_misses(cm):
    manager, mock_redis = cm
    mock_redis.get.return_value = None
    manager.get("miss")
    mock_redis.get.return_value = _signed("val")
    manager.get("hit")
    stats = manager.get_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 1


def test_get_rejects_unsigned_payload(cm):
    """Unsigned (legacy) or tampered payloads return None instead of executing code."""
    manager, mock_redis = cm
    mock_redis.get.return_value = pickle.dumps({"z": 3})  # no HMAC prefix
    assert manager.get("unsigned") is None
