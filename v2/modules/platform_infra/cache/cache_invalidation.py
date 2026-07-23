"""
TIR Yakıt Takip - Cache Invalidation Module
EventBus listener'ları ile otomatik cache temizleme.
"""

from v2.modules.platform_infra.cache.cache_manager import get_cache_manager
from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager
from v2.modules.platform_infra.events.event_bus import Event, EventType, get_event_bus
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


async def trigger_dashboard_update():
    """EventBus trigger sonrası Redis üzerinden Dashboard Worker'larına Update emri ver"""
    try:
        pubsub = get_pubsub_manager()
        await pubsub.publish("dashboard_updates", {"action": "update"})
        logger.debug("Dashboard update trigger published via Pub/Sub")
    except Exception as e:
        logger.warning(f"Failed to publish dashboard update trigger: {e}")


def setup_cache_invalidation():
    """
    Cache invalidation event listener'larını kur.

    Bu fonksiyon uygulama başlangıcında (lifespan) çağrılmalıdır.
    """
    event_bus = get_event_bus()
    cache = get_cache_manager()

    # === SEFER EVENT HANDLERS ===
    async def on_sefer_change(event: Event):
        """Sefer değiştiğinde ilgili cache'leri temizle"""
        cache.delete_pattern("stats:*")
        cache.delete_pattern("report:*")
        cache.delete_pattern("dashboard:*")
        cache.delete_pattern("trend:*")

        # Araç spesifik cache
        arac_id = (
            event.data.get("result", {}).get("arac_id")
            if isinstance(event.data.get("result"), dict)
            else None
        )
        if arac_id:
            cache.delete_pattern(f"arac:{arac_id}:*")

        logger.debug(f"Cache invalidated for sefer event: {event.type.value}")
        await trigger_dashboard_update()

    event_bus.subscribe(EventType.SEFER_ADDED, on_sefer_change)
    event_bus.subscribe(EventType.SEFER_UPDATED, on_sefer_change)
    event_bus.subscribe(EventType.SEFER_DELETED, on_sefer_change)

    # === YAKIT EVENT HANDLERS ===
    async def on_yakit_change(event: Event):
        """Yakıt değiştiğinde ilgili cache'leri temizle"""
        cache.delete_pattern("stats:*")
        cache.delete_pattern("yakit:*")
        cache.delete_pattern("periyot:*")
        cache.delete_pattern("anomali:*")

        logger.debug(f"Cache invalidated for yakit event: {event.type.value}")
        await trigger_dashboard_update()

    event_bus.subscribe(EventType.YAKIT_ADDED, on_yakit_change)
    event_bus.subscribe(EventType.YAKIT_UPDATED, on_yakit_change)
    event_bus.subscribe(EventType.YAKIT_DELETED, on_yakit_change)

    # === ARAC EVENT HANDLERS ===
    async def on_arac_change(event: Event):
        """Araç değiştiğinde ilgili cache'leri temizle"""
        cache.delete_pattern("arac:*")
        cache.delete_pattern("stats:filo*")

        logger.debug(f"Cache invalidated for arac event: {event.type.value}")
        await trigger_dashboard_update()

    event_bus.subscribe(EventType.ARAC_ADDED, on_arac_change)
    event_bus.subscribe(EventType.ARAC_UPDATED, on_arac_change)
    event_bus.subscribe(EventType.ARAC_DELETED, on_arac_change)

    # === SOFOR EVENT HANDLERS ===
    async def on_sofor_change(event: Event):
        """Şoför değiştiğinde ilgili cache'leri temizle"""
        cache.delete_pattern("sofor:*")
        cache.delete_pattern("stats:sofor*")

        logger.debug(f"Cache invalidated for sofor event: {event.type.value}")
        await trigger_dashboard_update()

    event_bus.subscribe(EventType.SOFOR_ADDED, on_sofor_change)
    event_bus.subscribe(EventType.SOFOR_UPDATED, on_sofor_change)
    event_bus.subscribe(EventType.SOFOR_DELETED, on_sofor_change)

    # === HESAPLAMA EVENT HANDLERS ===
    async def on_calculation_complete(event: Event):
        """Hesaplama tamamlandığında cache'i güncelle"""
        cache.delete_pattern("periyot:*")
        cache.delete_pattern("regression:*")

        logger.debug(f"Cache invalidated for calculation event: {event.type.value}")
        await trigger_dashboard_update()

    event_bus.subscribe(EventType.PERIYOT_CREATED, on_calculation_complete)
    event_bus.subscribe(EventType.YAKIT_DISTRIBUTED, on_calculation_complete)

    # === SETTINGS EVENT HANDLERS ===
    async def on_settings_change(event: Event):
        """Ayarlar değiştiğinde tüm cache'i temizle"""
        cache.clear()
        logger.info("All cache cleared due to settings change")

    event_bus.subscribe(EventType.SETTINGS_CHANGED, on_settings_change)

    logger.info("Cache invalidation listeners registered successfully")
