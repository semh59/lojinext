"""Feature D.2 — Redis cache key'leri ve tahmin cache invalidation."""

from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)

PREDICTIONS_CACHE_ALL = "maintenance:predictions:all"
PREDICTIONS_CACHE_ARAC_PREFIX = "maintenance:predictions:arac:"


async def invalidate_predictions_cache() -> None:
    """Bakım create/complete sonrası tahmin cache'lerini sil.

    `predictions:all` tek key; per-arac key'leri SCAN ile temizler.
    Redis bağlantı hatası loglanır ama caller'ı bloklamaz.
    """
    try:
        import redis.asyncio as aioredis

        from app.config import settings

        client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        await client.delete(PREDICTIONS_CACHE_ALL)
        cursor = 0
        while True:
            cursor, keys = await client.scan(
                cursor, match=f"{PREDICTIONS_CACHE_ARAC_PREFIX}*", count=100
            )
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break
        await client.aclose()
    except Exception as exc:
        logger.warning("Predictions cache invalidation failed: %s", exc)
