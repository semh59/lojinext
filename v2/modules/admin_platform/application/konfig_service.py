"""Sistem konfigürasyonu yönetimi — validasyon + cache/pubsub orkestrasyonu.

Eski ``KonfigService`` sınıfının B.1 gereği dissolve edilmiş hali: tek
alanı (``self.repo``) her çağrıda ``get_admin_config_repo(session)`` ile
trivially yeniden kurulabiliyordu, gerçek mutable state yoktu.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.cache.redis_cache import get_redis_cache
from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
from app.infrastructure.logging.logger import get_logger
from v2.modules.admin_platform.infrastructure.repository import get_admin_config_repo

logger = get_logger(__name__)


async def get_all_by_group(
    session: Optional[AsyncSession], group: str
) -> List[Dict[str, Any]]:
    """Get all configs in a group as dicts (Cached)."""
    cache = get_redis_cache()
    cache_key = f"configs:group:{group}"

    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    repo = get_admin_config_repo(session)
    data = await repo.get_by_group(group)
    cache.set(cache_key, data, ttl=3600)  # 1 hour
    return data


async def get_all_configs(session: Optional[AsyncSession]) -> List[Dict[str, Any]]:
    """Get every config as dicts (Cached)."""
    cache = get_redis_cache()
    cache_key = "configs:all"

    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    repo = get_admin_config_repo(session)
    data = await repo.get_all_configs()
    cache.set(cache_key, data, ttl=3600)  # 1 hour
    return data


async def get_config_value(
    session: Optional[AsyncSession], key: str, default: Any = None
) -> Any:
    """Get config value (Cached)."""
    cache = get_redis_cache()
    cache_key = f"config:val:{key}"

    cached_val = cache.get(cache_key)
    if cached_val is not None:
        return cached_val

    repo = get_admin_config_repo(session)
    val = await repo.get_value(key, default)
    if val is not None:
        cache.set(cache_key, val, ttl=3600)
    return val if val is not None else default


async def update_config(
    session: Optional[AsyncSession],
    key: str,
    value: Any,
    user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Update a configuration with validation. Returns dict."""
    repo = get_admin_config_repo(session)
    config = await repo.get_config(key)
    if not config:
        raise ValueError(f"Konfigrasyon bulunamadı: {key}")

    # Basic Validation based on type
    if config["tip"] == "number":
        try:
            num_val = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"{key} sayısal bir değer olmalıdır.")

        if config["min_deger"] is not None and num_val < config["min_deger"]:
            raise ValueError(f"{key} için minimum değer: {config['min_deger']}")
        if config["max_deger"] is not None and num_val > config["max_deger"]:
            raise ValueError(f"{key} için maksimum değer: {config['max_deger']}")

    elif config["tip"] == "boolean":
        if not isinstance(value, bool):
            if str(value).lower() in ("true", "1", "yes"):
                value = True
            elif str(value).lower() in ("false", "0", "no"):
                value = False
            else:
                raise ValueError(f"{key} boolean bir değer olmalıdır.")

    # Update via repo
    updated_config = await repo.update_value(
        key=key, new_value=value, updated_by_id=user_id, reason=reason
    )

    # Commit before cache invalidation — prevents stale reads in the window
    # between cache clear and DB commit, and ensures multi-worker pubsub
    # subscribers see the new value immediately.
    await repo.session.commit()

    logger.info(f"Config updated: {key} -> {value} by user {user_id}")

    if updated_config["yeniden_baslat"]:
        logger.warning(f"Config {key} requires restart to take effect.")

    # Invalidate cache
    cache = get_redis_cache()
    cache.delete(f"config:val:{key}")
    cache.delete(f"configs:group:{config['grup']}")
    cache.delete("configs:all")

    # Publish event for distributed workers
    pubsub = get_pubsub_manager()
    await pubsub.publish(
        "config_updates", {"key": key, "group": config["grup"], "value": value}
    )

    return updated_config


async def get_config_history(
    session: Optional[AsyncSession], key: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Get change history as dicts."""
    repo = get_admin_config_repo(session)
    return await repo.get_history(key, limit)
