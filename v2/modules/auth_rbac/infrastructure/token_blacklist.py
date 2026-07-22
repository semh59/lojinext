import threading
from datetime import datetime, timezone

from app.infrastructure.logging.logger import get_logger
from v2.modules.auth_rbac.domain.jwt_handler import hash_token
from v2.modules.platform_infra.cache.redis_pubsub import get_redis_val, set_redis_val

logger = get_logger(__name__)


class TokenBlacklist:
    """
    Redis-backed blacklist for JWT tokens.
    Provides immediate revocation of tokens (e.g., on logout).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TokenBlacklist, cls).__new__(cls)
            return cls._instance

    async def add(self, token: str, expires_at: datetime):
        """Add token to blacklist until its expiration."""
        try:
            # Calculate TTL in seconds
            now = datetime.now(timezone.utc)
            ttl = int((expires_at.replace(tzinfo=timezone.utc) - now).total_seconds())

            if ttl > 0:
                key = f"blacklist:{hash_token(token)}"
                # We use value '1' as a placeholder
                await set_redis_val(key, "1", expire=ttl)
                logger.info(f"Token added to blacklist (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Failed to add token to blacklist: {e}")
            raise

    async def is_blacklisted(self, token: str) -> bool:
        """Check if token is in blacklist.

        Fail-secure (SEC-004): if Redis is unreachable we cannot prove the
        token was *not* revoked, so we treat it as blacklisted (return True)
        rather than letting logged-out tokens through. Trade-off: a Redis
        outage rejects all tokens until Redis recovers — Redis is already a
        hard dependency (cache/queue/pubsub), so an outage is a broader
        incident, not an auth-bypass window.
        """
        try:
            key = f"blacklist:{hash_token(token)}"
            val = await get_redis_val(key)
            return val is not None
        except Exception as e:
            logger.critical(
                f"Blacklist check failed (Redis unreachable) — failing secure, "
                f"treating token as revoked: {e}"
            )
            return True


blacklist = TokenBlacklist()
