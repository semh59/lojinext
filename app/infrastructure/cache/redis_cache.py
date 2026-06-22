"""
Redis Cache Service - Yakıt Yönetim Sistemi
Tekrar eden sorgular için önbellekleme
"""

import asyncio
import functools
import hashlib
import inspect
import json
import os
import re
import threading
from typing import Any, Optional

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.infrastructure.cache.cache_manager import get_cache_manager
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RedisCache:
    """
    Redis tabanlı cache sistemi.

    Redis yoksa veya bağlantı başarısızsa,
    in-memory fallback kullanır.
    """

    _instance = None
    _lock = threading.Lock()  # Thread-safe singleton için

    # Key'de izin verilmeyen karakterler
    _KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_:.\-]+$")

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._redis_client = None
        self._fallback = get_cache_manager()
        self._default_ttl = 3600  # 1 saat

        # Redis bağlantısını dene
        self._connect()

    def _connect(self):
        """Redis bağlantısı kur"""
        if not REDIS_AVAILABLE:
            logger.warning(
                "Redis kütüphanesi yüklü değil. In-memory cache kullanılacak."
            )
            return

        import sys

        is_testing = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")

        if is_testing and not os.getenv("REDIS_HOST"):
            logger.info("Test environment detected, bypassing Redis connection.")
            return

        from app.config import settings as _s

        redis_host = _s.REDIS_HOST
        redis_port = _s.REDIS_PORT
        redis_db = _s.REDIS_DB
        redis_password = os.getenv("REDIS_PASSWORD", None)
        redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

        import sys

        is_testing = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST")
        # Test ortamında timeout'u çok düşük tut
        connect_timeout = 0.1 if is_testing else 2.0

        try:
            self._redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=connect_timeout,
                socket_timeout=connect_timeout,
                ssl=redis_ssl,  # SSL/TLS desteği
                ssl_cert_reqs="required" if redis_ssl else None,
            )
            # Bağlantı testi
            self._redis_client.ping()
            ssl_status = " (SSL)" if redis_ssl else ""
            logger.info(
                f"Redis bağlantısı kuruldu: {redis_host}:{redis_port}{ssl_status}"
            )
        except Exception as e:
            logger.warning(
                f"Redis bağlantısı kurulamadı: {e}. In-memory cache kullanılacak."
            )
            self._redis_client = None

    @property
    def is_redis_available(self) -> bool:
        """Redis kullanılabilir mi?"""
        return self._redis_client is not None

    def _validate_key(self, key: str):
        """Cache key güvenliği kontrolü"""
        # Redis key length limit is 512MB technically but we want sane limits
        if not key or len(key) > 512:
            raise ValueError("Cache key too long (max 512 chars)")

        # Karakter kontrolü - sadece güvenli karakterler
        if not self._KEY_PATTERN.match(key):
            raise ValueError(f"Invalid cache key characters: {key[:50]}")

        # Directory traversal koruması
        if "../" in key or "..\\" in key:
            raise ValueError("Invalid cache key: Directory traversal attempt")

    def _generate_key(self, query: str, prefix: str = "qc") -> str:
        """Sorgu için unique cache key oluştur"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{prefix}:{query_hash}"

    def get(self, key: str) -> Optional[Any]:
        """
        Cache'den değer al.

        Args:
            key: Cache anahtarı

        Returns:
            Cache değeri veya None
        """
        self._validate_key(key)

        try:
            if self._redis_client:
                cached = self._redis_client.get(key)
                if cached:
                    logger.debug(f"✅ Redis cache hit: {key[:20]}...")
                    return json.loads(cached)
            else:
                # Use central CacheManager as fallback
                logger.debug(f"✅ Fallback to Memory cache: {key[:20]}...")
                return self._fallback.get(key)
        except Exception as e:
            logger.warning(f"Cache get hatası: {e}")

        return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Cache'e değer yaz.

        Args:
            key: Cache anahtarı
            value: Saklanacak değer
            ttl: Time-to-live (saniye)

        Returns:
            Başarılı mı
        """
        self._validate_key(key)
        ttl = ttl or self._default_ttl

        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)

            if self._redis_client:
                self._redis_client.setex(key, ttl, serialized)
                logger.debug(f"Redis cache set: {key[:20]}... (TTL: {ttl}s)")
            else:
                # Use central CacheManager as fallback
                self._fallback.set(key, value, ttl)
                logger.debug(f"Fallback Memory cache set: {key[:20]}... (TTL: {ttl}s)")

            return True
        except Exception as e:
            logger.warning(f"Cache set hatası: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Cache'den sil"""
        try:
            if self._redis_client:
                self._redis_client.delete(key)
            else:
                self._fallback.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete hatası: {e}")
            return False

    # Key prefixes owned by RedisCache (used for targeted clear_all)
    _OWNED_PREFIXES = ("qc:", "configs:", "config:")

    def clear_all(self) -> bool:
        """Cache'i temizle — yalnız bu servise ait anahtarlar (flushdb değil)."""
        try:
            if self._redis_client:
                deleted = 0
                for prefix in self._OWNED_PREFIXES:
                    cursor = 0
                    while True:
                        cursor, keys = self._redis_client.scan(
                            cursor, match=f"{prefix}*", count=100
                        )
                        if keys:
                            self._redis_client.delete(*keys)
                            deleted += len(keys)
                        if cursor == 0:
                            break
                logger.info("Cache temizlendi (%d anahtar silindi)", deleted)
            else:
                self._fallback.clear()
            return True
        except Exception as e:
            logger.warning(f"Cache clear hatası: {e}")
            return False

    def get_cached_response(self, query: str) -> Optional[str]:
        """Sorgu için cache'lenmiş yanıt al"""
        key = self._generate_key(query)
        return self.get(key)

    def cache_response(self, query: str, response: str, ttl: int = None) -> bool:
        """Sorgu yanıtını cache'le"""
        key = self._generate_key(query)
        return self.set(key, response, ttl)

    def get_stats(self) -> dict:
        """Cache istatistikleri"""
        stats = {
            "backend": "redis" if self._redis_client else "memory",
            "connected": self.is_redis_available,
        }

        if self._redis_client:
            try:
                info = self._redis_client.info("memory")
                stats["used_memory"] = info.get("used_memory_human", "N/A")
                stats["keys"] = self._redis_client.dbsize()
            except Exception:
                pass
        else:
            # Memory backend: fallback bir CacheManager — kendi istatistiğini ver.
            stats["fallback"] = self._fallback.get_stats()

        return stats


# Singleton accessor
def get_redis_cache() -> RedisCache:
    """Redis cache singleton'ı getir"""
    return RedisCache()


# Decorator implementation moved to top


# Decorator for caching function results
def cached(ttl: int = 3600, prefix: str = "fn"):
    """
    Fonksiyon sonuçlarını cache'leyen decorator (Sync & Async destekli).
    """

    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                cache = get_redis_cache()
                # Skip 'self'/'cls' (first arg for bound methods) — it uses the
                # memory-address repr which changes per-instance, making the key
                # unique per object and defeating the cache entirely.
                cache_args = args[1:] if args and hasattr(args[0], "__dict__") else args
                key_data = f"{func.__qualname__}:{cache_args!s}:{kwargs!s}"
                key = cache._generate_key(key_data, prefix)

                cached_result = await asyncio.to_thread(cache.get, key)
                if cached_result is not None:
                    return cached_result

                result = await func(*args, **kwargs)
                await asyncio.to_thread(cache.set, key, result, ttl)
                return result
        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                cache = get_redis_cache()
                cache_args = args[1:] if args and hasattr(args[0], "__dict__") else args
                key_data = f"{func.__qualname__}:{cache_args!s}:{kwargs!s}"
                key = cache._generate_key(key_data, prefix)

                cached_result = cache.get(key)
                if cached_result is not None:
                    return cached_result

                result = func(*args, **kwargs)
                cache.set(key, result, ttl)
                return result

        return wrapper

    return decorator
