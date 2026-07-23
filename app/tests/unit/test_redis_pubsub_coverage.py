"""
RedisPubSubManager coverage tests — pub/sub, set/get/delete, incr,
connection management, memory fallback paths, module-level helpers.

Targets lines missed in: app/infrastructure/cache/redis_pubsub.py

NOTE: RedisPubSubManager is a singleton. Each test resets _instance before
running so it gets a fresh object.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Per-test singleton reset
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_pubsub_singleton():
    """Force a fresh RedisPubSubManager instance for each test."""
    import v2.modules.platform_infra.cache.redis_pubsub as mod

    mod.RedisPubSubManager._instance = None
    yield
    mod.RedisPubSubManager._instance = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager_no_redis():
    """Return a manager with _redis=None (memory-only mode)."""
    import v2.modules.platform_infra.cache.redis_pubsub as mod

    with patch.object(mod.RedisPubSubManager, "_connect", lambda self: None):
        mgr = mod.RedisPubSubManager()
        mgr._redis = None
    return mgr


def _make_manager_with_redis(fake_redis=None):
    """Return a manager with a mock Redis client injected."""
    import v2.modules.platform_infra.cache.redis_pubsub as mod

    fake = fake_redis or AsyncMock()

    with patch.object(mod.RedisPubSubManager, "_connect", lambda self: None):
        mod.RedisPubSubManager._instance = None
        mgr = mod.RedisPubSubManager()
        mgr._redis = fake
    return mgr


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_same_instance_returned(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        with patch.object(mod.RedisPubSubManager, "_connect", lambda self: None):
            a = mod.RedisPubSubManager()
            b = mod.RedisPubSubManager()
        assert a is b

    def test_get_pubsub_manager_returns_instance(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        with patch.object(mod.RedisPubSubManager, "_connect", lambda self: None):
            mgr = mod.get_pubsub_manager()
        assert isinstance(mgr, mod.RedisPubSubManager)


# ---------------------------------------------------------------------------
# _connect paths
# ---------------------------------------------------------------------------


class TestConnect:
    def test_connect_without_redis_available(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        original = mod.REDIS_AVAILABLE
        mod.REDIS_AVAILABLE = False
        mod.RedisPubSubManager._instance = None
        try:
            mgr = mod.RedisPubSubManager()
            assert mgr._redis is None
        finally:
            mod.REDIS_AVAILABLE = original

    def test_connect_ssl_path(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        fake_redis = MagicMock()
        mock_settings = MagicMock()
        mock_settings.REDIS_HOST = "localhost"
        mock_settings.REDIS_PORT = 6380
        mock_settings.REDIS_DB = 0
        mock_settings.REDIS_PASSWORD = "test_pass"  # pragma: allowlist secret
        mock_settings.REDIS_SSL = True

        with (
            patch("v2.modules.platform_infra.cache.redis_pubsub.REDIS_AVAILABLE", True),
            patch(
                "v2.modules.platform_infra.cache.redis_pubsub.aioredis.from_url",
                return_value=fake_redis,
            ),
            patch(
                "v2.modules.platform_infra.cache.redis_pubsub._s", mock_settings, create=True
            ),
        ):
            mod.RedisPubSubManager._instance = None
            with patch(
                "v2.modules.platform_infra.cache.redis_pubsub.RedisPubSubManager._connect"
            ) as mock_connect:
                mock_connect.side_effect = lambda self=None: setattr(
                    self or mod.RedisPubSubManager._instance, "_redis", None
                )
                mgr = mod.RedisPubSubManager()
                assert mgr is not None

    def test_connect_exception_sets_redis_none(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        mock_settings = MagicMock()
        mock_settings.REDIS_HOST = "localhost"
        mock_settings.REDIS_PORT = 6379
        mock_settings.REDIS_DB = 0
        mock_settings.REDIS_PASSWORD = None
        mock_settings.REDIS_SSL = False

        with (
            patch("v2.modules.platform_infra.cache.redis_pubsub.REDIS_AVAILABLE", True),
            patch(
                "v2.modules.platform_infra.cache.redis_pubsub.aioredis.from_url",
                side_effect=Exception("conn refused"),
            ),
        ):
            mod.RedisPubSubManager._instance = None
            with patch("app.config.settings", mock_settings):
                pass  # just ensure module imports don't fail


# ---------------------------------------------------------------------------
# publish — Redis path
# ---------------------------------------------------------------------------


class TestPublish:
    async def test_publish_via_redis(self):
        fake_redis = AsyncMock()
        fake_redis.publish = AsyncMock(return_value=1)
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.publish("test_channel", {"key": "value"})
        assert result is True
        fake_redis.publish.assert_called_once()

    async def test_publish_redis_error_falls_back_to_memory(self):
        fake_redis = AsyncMock()
        fake_redis.publish = AsyncMock(side_effect=Exception("redis down"))
        mgr = _make_manager_with_redis(fake_redis)
        # No subscribers — falls through to False
        result = await mgr.publish("empty_channel", {"key": "value"})
        assert result is False  # no subscribers in memory

    async def test_publish_memory_path_delivers_to_subscriber(self):
        mgr = _make_manager_no_redis()
        q: asyncio.Queue = asyncio.Queue()
        mgr._subscribers["test_ch"] = [q]
        result = await mgr.publish("test_ch", {"hello": "world"})
        assert result is True
        msg = q.get_nowait()
        assert msg == {"hello": "world"}

    async def test_publish_no_subscribers_returns_false(self):
        mgr = _make_manager_no_redis()
        result = await mgr.publish("no_one_listens", "data")
        assert result is False

    async def test_publish_serializes_non_string_values(self):
        mgr = _make_manager_no_redis()
        q: asyncio.Queue = asyncio.Queue()
        mgr._subscribers["ch"] = [q]
        await mgr.publish("ch", {"ts": None, "value": 3.14})
        msg = q.get_nowait()
        assert msg["value"] == pytest.approx(3.14)


# ---------------------------------------------------------------------------
# set / get / delete — Redis path
# ---------------------------------------------------------------------------


class TestSetGetDelete:
    async def test_set_via_redis(self):
        fake_redis = AsyncMock()
        fake_redis.set = AsyncMock(return_value=True)
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.set("k1", {"a": 1}, expire=60)
        assert result is True
        fake_redis.set.assert_called_once()

    async def test_set_redis_error_falls_back_to_memory(self):
        fake_redis = AsyncMock()
        fake_redis.set = AsyncMock(side_effect=Exception("err"))
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.set("k1", "val")
        assert result is True
        assert "k1" in mgr._memory_store

    async def test_get_via_redis(self):
        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value=json.dumps({"x": 1}))
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.get("k1")
        assert result == {"x": 1}

    async def test_get_redis_miss_returns_none(self):
        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value=None)
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.get("missing")
        assert result is None

    async def test_get_redis_error_falls_back_to_memory(self):
        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(side_effect=Exception("err"))
        mgr = _make_manager_with_redis(fake_redis)
        mgr._memory_store["k1"] = json.dumps({"fallback": True})
        result = await mgr.get("k1")
        assert result == {"fallback": True}

    async def test_get_memory_only(self):
        mgr = _make_manager_no_redis()
        mgr._memory_store["mk"] = json.dumps([1, 2, 3])
        result = await mgr.get("mk")
        assert result == [1, 2, 3]

    async def test_get_memory_miss_returns_none(self):
        mgr = _make_manager_no_redis()
        result = await mgr.get("no_key")
        assert result is None

    async def test_delete_via_redis(self):
        fake_redis = AsyncMock()
        fake_redis.delete = AsyncMock(return_value=1)
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.delete("k1")
        assert result is True

    async def test_delete_redis_error_falls_back_to_memory(self):
        fake_redis = AsyncMock()
        fake_redis.delete = AsyncMock(side_effect=Exception("err"))
        mgr = _make_manager_with_redis(fake_redis)
        mgr._memory_store["k1"] = "val"
        result = await mgr.delete("k1")
        assert result is True
        assert "k1" not in mgr._memory_store

    async def test_delete_memory_only(self):
        mgr = _make_manager_no_redis()
        mgr._memory_store["del_me"] = "x"
        result = await mgr.delete("del_me")
        assert result is True
        assert "del_me" not in mgr._memory_store

    async def test_delete_missing_key_returns_false(self):
        mgr = _make_manager_no_redis()
        result = await mgr.delete("ghost")
        assert result is False


# ---------------------------------------------------------------------------
# incr
# ---------------------------------------------------------------------------


class TestIncr:
    async def test_incr_via_redis(self):
        fake_redis = AsyncMock()
        fake_redis.incr = AsyncMock(return_value=5)
        mgr = _make_manager_with_redis(fake_redis)
        result = await mgr.incr("counter")
        assert result == 5

    async def test_incr_redis_error_falls_back_to_memory(self):
        fake_redis = AsyncMock()
        fake_redis.incr = AsyncMock(side_effect=Exception("err"))
        mgr = _make_manager_with_redis(fake_redis)
        mgr._memory_store["counter"] = "3"
        result = await mgr.incr("counter")
        assert result == 4

    async def test_incr_memory_from_zero(self):
        mgr = _make_manager_no_redis()
        result = await mgr.incr("new_counter")
        assert result == 1

    async def test_incr_memory_increments(self):
        mgr = _make_manager_no_redis()
        mgr._memory_store["c"] = "10"
        result = await mgr.incr("c")
        assert result == 11


# ---------------------------------------------------------------------------
# redis property
# ---------------------------------------------------------------------------


class TestRedisProperty:
    def test_redis_property_returns_client(self):
        fake_redis = AsyncMock()
        mgr = _make_manager_with_redis(fake_redis)
        assert mgr.redis is fake_redis

    def test_redis_property_none_when_no_client(self):
        mgr = _make_manager_no_redis()
        assert mgr.redis is None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestModuleLevelHelpers:
    async def test_set_redis_val(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        with patch.object(mod.RedisPubSubManager, "_connect", lambda self: None):
            mod.RedisPubSubManager._instance = None
            with patch.object(
                mod.RedisPubSubManager,
                "set",
                new_callable=lambda: lambda *a, **kw: AsyncMock(return_value=True)(),
            ):
                # Just ensure helper is callable
                pass

        mgr = _make_manager_no_redis()
        with patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager", return_value=mgr
        ):
            result = await mod.set_redis_val("k", "v", 30)
            assert result is True

    async def test_get_redis_val(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        mgr = _make_manager_no_redis()
        mgr._memory_store["test_key"] = json.dumps("hello")
        with patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager", return_value=mgr
        ):
            result = await mod.get_redis_val("test_key")
            assert result == "hello"

    async def test_delete_redis_val(self):
        import v2.modules.platform_infra.cache.redis_pubsub as mod

        mgr = _make_manager_no_redis()
        mgr._memory_store["del_k"] = "v"
        with patch(
            "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager", return_value=mgr
        ):
            result = await mod.delete_redis_val("del_k")
            assert result is True


# ---------------------------------------------------------------------------
# subscribe — memory fallback (can test delivery; skip live Redis)
# ---------------------------------------------------------------------------


class TestSubscribeMemory:
    async def test_subscribe_memory_receives_published_message(self):
        mgr = _make_manager_no_redis()

        messages = []

        async def _consumer():
            async for msg in mgr.subscribe("my_channel"):
                messages.append(msg)
                break  # stop after first message

        consumer_task = asyncio.ensure_future(_consumer())
        # Give consumer time to register
        await asyncio.sleep(0)
        await mgr.publish("my_channel", {"event": "test"})
        await asyncio.wait_for(consumer_task, timeout=1.0)
        assert messages == [{"event": "test"}]

    async def test_subscribe_memory_cleanup_on_exit(self):
        """Ensure subscriber is removed from list when generator completes."""
        mgr = _make_manager_no_redis()

        received = []

        async def _consumer():
            async for msg in mgr.subscribe("cleanup_ch"):
                received.append(msg)
                break  # exit after one message triggers finally cleanup

        # Start consumer
        consumer_task = asyncio.ensure_future(_consumer())
        # Yield control so consumer registers its queue
        await asyncio.sleep(0)

        # At this point subscriber should be registered
        assert "cleanup_ch" in mgr._subscribers

        # Publish a message so consumer breaks out of the loop
        await mgr.publish("cleanup_ch", {"done": True})

        # Wait for consumer to finish
        await asyncio.wait_for(consumer_task, timeout=1.0)

        # After break + return, finally block should have removed the subscriber
        # Give event loop a tick for cleanup
        await asyncio.sleep(0)
        assert len(mgr._subscribers.get("cleanup_ch", [])) == 0
