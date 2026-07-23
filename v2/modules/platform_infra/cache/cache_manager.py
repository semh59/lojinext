"""
TIR Yakıt Takip - Cache Manager
Redis-backed cache with TTL, pattern-based invalidation, and stats tracking.
"""

import hashlib
import hmac
import pickle
import re
import threading
from typing import Any, Dict, List, Optional, cast

import redis as redis_lib

from app.config import settings
from v2.modules.platform_infra.cache.redis_client_factory import get_sync_redis_client
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

_HMAC_LEN = 32  # SHA-256 digest length in bytes


def _get_sign_key() -> bytes:
    # SECRET_KEY is a pydantic SecretStr → .encode() yok; önce get_secret_value().
    # (AUDIT-150 doğrulama bulgusu: SecretStr.encode() her imza/doğrulamada
    #  AttributeError veriyordu → tüm cache set/get çöküyordu.)
    raw = settings.SECRET_KEY
    secret = raw.get_secret_value() if hasattr(raw, "get_secret_value") else str(raw)
    key = secret.encode()
    # Pad/truncate to 32 bytes so the key is always a fixed length.
    return (key + b"\x00" * 32)[:32]


def _sign(data: bytes) -> bytes:
    """Prepend a 32-byte HMAC-SHA256 so injected Redis payloads are rejected."""
    sig = hmac.new(_get_sign_key(), data, hashlib.sha256).digest()
    return sig + data


def _verify_and_strip(payload: bytes) -> bytes:
    """Verify the HMAC prefix and return the raw pickle bytes.

    Raises ValueError for payloads that are too short or have a bad signature
    (legacy unsigned entries or injection attempts).
    """
    if len(payload) < _HMAC_LEN:
        raise ValueError("Cache payload too short — treating as cache miss")
    sig, data = payload[:_HMAC_LEN], payload[_HMAC_LEN:]
    expected = hmac.new(_get_sign_key(), data, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Cache HMAC mismatch — possible injection or legacy entry")
    return data


# Sensitive key pattern'leri
SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|token|secret|api_key|private_key|credential|auth)", re.IGNORECASE
)

_KEY_PREFIX = "cm:"


class CacheManager:
    """
    Redis-Backed Cache Manager.

    Features:
        - TTL (Time To Live) desteği — delegated to Redis SETEX
        - Pattern-based key silme (delete_pattern) — via SCAN
        - Cache statistics (hits/misses/sets, in-memory acceptable trade-off)
        - Thread-safe stat counters
        - Singleton instance
    """

    _instance: Optional["CacheManager"] = None
    _cls_lock = threading.Lock()

    # mypy: instance-level attributes
    _redis: redis_lib.Redis
    _lock: threading.Lock
    _stats: Dict[str, int]

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            with cls._cls_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._redis = get_sync_redis_client(
                        decode_responses=False, url=settings.REDIS_URL
                    )
                    inst._lock = threading.Lock()
                    inst._stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}
                    cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any, ttl_seconds: float = 3600) -> None:
        """Veriyi cache'e kaydet. Redis erişilemezse sessizce no-op (Tier E
        madde 31: bir cache write'ın çökmesi request'i 500'e düşürmemeli)."""
        self._validate_key(key)
        ttl_ms = max(1, int(ttl_seconds * 1000))
        try:
            self._redis.psetex(
                f"{_KEY_PREFIX}{key}", ttl_ms, _sign(pickle.dumps(value))
            )
            with self._lock:
                self._stats["sets"] += 1
        except redis_lib.exceptions.RedisError as exc:
            logger.warning("Cache set degraded (Redis unavailable): %s", exc)

    def get(self, key: str) -> Optional[Any]:
        """Cache'den veri getir; yoksa veya Redis erişilemezse None döndür
        (graceful degradation — çağıran taraf DB'ye düşer)."""
        self._validate_key(key)
        try:
            raw = self._redis.get(f"{_KEY_PREFIX}{key}")
        except redis_lib.exceptions.RedisError as exc:
            logger.warning("Cache get degraded (Redis unavailable): %s", exc)
            return None
        with self._lock:
            if raw is None:
                self._stats["misses"] += 1
                return None
            self._stats["hits"] += 1
        try:
            return pickle.loads(_verify_and_strip(cast("bytes", raw)))  # noqa: S301
        except ValueError as exc:
            logger.warning("Cache get rejected for key '%s': %s", key, exc)
            return None

    def delete(self, key: str) -> bool:
        """Belirli bir anahtarı sil. True → silindi, False → zaten yoktu
        veya Redis erişilemedi."""
        self._validate_key(key)
        try:
            return bool(self._redis.delete(f"{_KEY_PREFIX}{key}"))
        except redis_lib.exceptions.RedisError as exc:
            logger.warning("Cache delete degraded (Redis unavailable): %s", exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Pattern ile eşleşen tüm anahtarları sil.

        Args:
            pattern: Redis glob pattern (örn: "stats:*", "arac:*:details")

        Returns:
            Silinen anahtar sayısı (Redis erişilemezse 0)
        """
        if "../" in pattern:
            raise ValueError("Invalid pattern: Directory traversal attempt")

        count = 0
        try:
            for k in self._redis.scan_iter(f"{_KEY_PREFIX}{pattern}"):
                self._redis.delete(k)
                count += 1
        except redis_lib.exceptions.RedisError as exc:
            logger.warning("Cache delete_pattern degraded (Redis unavailable): %s", exc)
            return count

        if count:
            logger.debug(f"Cache pattern delete: '{pattern}' — {count} keys removed")
        return count

    def clear(self) -> None:
        """Tüm cm: namespace anahtarlarını temizle."""
        count = 0
        try:
            for k in self._redis.scan_iter(f"{_KEY_PREFIX}*"):
                self._redis.delete(k)
                count += 1
        except redis_lib.exceptions.RedisError as exc:
            logger.warning("Cache clear degraded (Redis unavailable): %s", exc)
            return
        logger.info(f"Cache cleared: {count} keys removed")

    def get_stats(self) -> Dict[str, Any]:
        """Cache istatistiklerini getir."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
            return {
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "sets": self._stats["sets"],
                "evictions": self._stats["evictions"],
                "hit_rate_pct": round(hit_rate, 1),
            }

    def get_keys(self, pattern: str = "*") -> List[str]:
        """Pattern ile eşleşen anahtarları listele (prefix stripped;
        Redis erişilemezse boş liste)."""
        result = []
        try:
            for k in self._redis.scan_iter(f"{_KEY_PREFIX}{pattern}"):
                key_str = k.decode() if isinstance(k, bytes) else k
                result.append(key_str.removeprefix(_KEY_PREFIX))
        except redis_lib.exceptions.RedisError as exc:
            logger.warning("Cache get_keys degraded (Redis unavailable): %s", exc)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_key(key: str) -> None:
        """Cache key güvenliği kontrolü."""
        if not key or not isinstance(key, str) or len(key) > 256:
            raise ValueError("Cache key must be a non-empty string ≤ 256 characters")

        if "../" in key or "..\\" in key:
            raise ValueError("Invalid cache key: Directory traversal attempt")

        if SENSITIVE_KEY_PATTERNS.search(key):
            logger.warning(
                f"Sensitive key pattern detected and rejected: {key[:30]}..."
            )
            raise ValueError(
                "Cache key contains sensitive pattern (password/token/secret)"
            )


# Singleton Provider
def get_cache_manager() -> CacheManager:
    return CacheManager()
