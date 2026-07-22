"""`app/infrastructure/cache/`'den dalga 17 (platform_infra) denetiminde
taşındı — Redis-tabanlı cache/pub-sub katmanı, 3+ bağımsız modül tarafından
kullanılan genuinely cross-cutting altyapı (bkz. `TASKS/modules/
platform-infra.md`)."""

from .cache_manager import CacheManager, get_cache_manager

__all__ = ["CacheManager", "get_cache_manager"]
