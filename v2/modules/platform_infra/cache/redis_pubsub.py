"""
Redis Async Pub/Sub Service
WebSocket yayınları ve asenkron Event-Driven mesajlaşma için kullanılır.
"""

import asyncio
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisPubSubManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._memory_store: Dict[str, Any] = {}
        self._memory_expiry: Dict[str, float] = {}
        self._subscribers: Dict[str, List[Any]] = {}
        self._redis: aioredis.Redis | None = None
        self._connect()

    def _connect(self):
        if not REDIS_AVAILABLE:
            logger.warning("Redis async is not available. Using In-Memory fallback.")
            return

        from app.config import settings as _s

        redis_ssl = _s.REDIS_SSL

        from v2.modules.platform_infra.cache.redis_client_factory import (
            get_async_redis_client,
        )

        def _build_async_client(**extra):
            return get_async_redis_client(
                socket_timeout=2.0,
                socket_connect_timeout=2.0,  # Fast fail
                **extra,
            )

        try:
            if redis_ssl:
                import ssl

                ssl_ctx = ssl.create_default_context()
                if os.getenv("REDIS_SSL_INSECURE", "false").lower() == "true":
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                # default: full verification (check_hostname=True, verify_mode=CERT_REQUIRED)
                self._redis = _build_async_client(ssl=ssl_ctx)
            else:
                self._redis = _build_async_client()
            mode = (
                "sentinel"
                if _s.REDIS_USE_SENTINEL
                else f"{_s.REDIS_HOST}:{_s.REDIS_PORT}"
            )
            logger.info(f"Async Redis PubSub connected to {mode}")
        except Exception as e:
            logger.warning(
                f"Async Redis connection failed, switching to In-Memory: {e}"
            )
            self._redis = None

    async def publish(self, channel: str, message: Any) -> bool:
        """Kanal üzerinden mesaj gönder"""
        payload = json.dumps(message, ensure_ascii=False, default=str)

        if self._redis:
            try:
                await self._redis.publish(channel, payload)
                return True
            except Exception as e:
                logger.warning(f"Redis publish error (using memory fallback): {e}")
                # Fallback to memory even if redis failed

        # Memory Fallback
        if channel in self._subscribers:
            data = json.loads(payload)
            for q in self._subscribers[channel]:
                await q.put(data)
            return True
        return False

    async def subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        """Kanalı asenkron olarak dinle"""
        if self._redis:
            try:
                pubsub_conn = self._redis.pubsub()
                await pubsub_conn.subscribe(channel)
                try:
                    async for message in pubsub_conn.listen():
                        if message["type"] == "message":
                            try:
                                yield json.loads(message["data"])
                            except json.JSONDecodeError:
                                pass
                finally:
                    await pubsub_conn.unsubscribe(channel)
                    await pubsub_conn.close()
                return  # Success from Redis
            except Exception as e:
                logger.warning(f"Redis subscribe failed, using memory: {e}")

        # Memory Fallback
        q: asyncio.Queue[Any] = asyncio.Queue()
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(q)

        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            if channel in self._subscribers:
                self._subscribers[channel].remove(q)

    # Key-Value Methods with Fallback
    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if self._redis:
            try:
                await self._redis.set(key, payload, ex=expire)
                return True
            except Exception as e:
                logger.warning(f"Redis set error ({key}): {e}")

        # Memory Fallback
        self._memory_store[key] = payload
        if expire:
            self._memory_expiry[key] = time.time() + expire
        elif key in self._memory_expiry:
            del self._memory_expiry[key]
        return True

    async def get(self, key: str) -> Any:
        if self._redis:
            try:
                data = await self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get error ({key}): {e}")

        # Memory Fallback — check TTL first
        exp = self._memory_expiry.get(key)
        if exp is not None and time.time() > exp:
            self._memory_store.pop(key, None)
            del self._memory_expiry[key]
            return None
        data = self._memory_store.get(key)
        return json.loads(data) if data else None

    async def set_nx(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Atomic SET-if-Not-eXists.  Returns True if the key was set (we won the race),
        False if it already existed (duplicate detected)."""
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if self._redis:
            try:
                result = await self._redis.set(key, payload, ex=expire, nx=True)
                return result is not None  # None means key already existed
            except Exception as e:
                logger.warning(f"Redis set_nx error ({key}): {e}")

        # Memory fallback — expire kontrolü sonra atomic setdefault (CPython GIL).
        exp = self._memory_expiry.get(key)
        if exp is not None and time.time() > exp:
            self._memory_store.pop(key, None)
            self._memory_expiry.pop(key, None)
        existing = self._memory_store.setdefault(key, payload)
        if existing == payload:  # we just inserted it
            if expire:
                self._memory_expiry[key] = time.time() + expire
            return True
        return False

    async def delete(self, key: str) -> bool:
        if self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception as e:
                logger.warning(f"Redis delete error ({key}): {e}")

        # Memory Fallback
        if key in self._memory_store:
            del self._memory_store[key]
            return True
        return False

    async def incr(self, key: str) -> int:
        """Atomic increment for Redis with memory fallback."""
        if self._redis:
            try:
                return await self._redis.incr(key)
            except Exception as e:
                logger.warning(f"Redis incr error ({key}): {e}")

        # Memory Fallback — süresi dolmuşsa sıfırdan başla
        exp = self._memory_expiry.get(key)
        if exp is not None and time.time() > exp:
            self._memory_store.pop(key, None)
            self._memory_expiry.pop(key, None)
        val = int(self._memory_store.get(key, 0)) + 1
        self._memory_store[key] = str(val)
        return val

    @property
    def redis(self) -> "aioredis.Redis | None":
        """Public accessor for the underlying async Redis client."""
        return self._redis


def get_pubsub_manager() -> RedisPubSubManager:
    return RedisPubSubManager()


async def set_redis_val(key: str, value: Any, expire: int | None = None) -> bool:
    return await get_pubsub_manager().set(key, value, expire)


async def get_redis_val(key: str) -> Any:
    return await get_pubsub_manager().get(key)


async def delete_redis_val(key: str) -> bool:
    return await get_pubsub_manager().delete(key)
