"""
Model Training Handler
Listens to domain events and triggers background operations.
"""

import asyncio

from app.infrastructure.cache.cache_manager import get_cache_manager
from app.infrastructure.events.event_bus import Event, EventType, get_event_bus
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Counter TTL — restart'larda kalır; 90 gün boyunca yeni veri almayan bir
# araç için sayaç düşer (zaten yarıda kalmış training tetiği gereksiz).
_COUNTER_TTL_S = 90 * 24 * 3600


class ModelTrainingHandler:
    """
    EventBus üzerinden gelen YAKIT_ADDED ve SEFER_ADDED event'larını dinleyip,
    belirli bir limite ulaştığında ilgili aracın ML modelini otomatik eğiten sınıf.
    """

    def __init__(self):
        self.event_bus = get_event_bus()
        self._cache = get_cache_manager()
        self.TRIGGER_THRESHOLD = 5  # Her 5 yeni yakıt/sefer kaydında retrain tetikle
        self._is_subscribed = False
        self._bg_tasks: set = set()  # prevent GC of in-flight tasks (AUDIT-130)

    @staticmethod
    def _counter_key(vehicle_id: int) -> str:
        return f"train_trigger:{vehicle_id}"

    def setup(self):
        """Abonelikleri başlat."""
        if self._is_subscribed:
            return

        self.event_bus.subscribe(EventType.YAKIT_ADDED, self.on_data_added)
        self.event_bus.subscribe(EventType.SEFER_ADDED, self.on_data_added)
        self._is_subscribed = True
        logger.info("ModelTrainingHandler subscribed to YAKIT_ADDED and SEFER_ADDED")

    async def on_data_added(self, event: Event):
        """Yeni veri geldiğinde counter update."""
        vehicle_id = event.data.get("arac_id")

        if not vehicle_id:
            logger.debug(
                f"ModelTrainingHandler: Event {event.type.value} does not have arac_id"
            )
            return

        key = self._counter_key(vehicle_id)
        # Redis-backed counter; restart'ta sıfırlanmaz.
        current_count = (self._cache.get(key) or 0) + 1

        logger.debug(
            f"ModelTrainingHandler | arac_id: {vehicle_id} | event: {event.type.value} | "
            f"count: {current_count}/{self.TRIGGER_THRESHOLD}"
        )

        # Threshold aşıldıysa eğitimi tetikle
        if current_count >= self.TRIGGER_THRESHOLD:
            self._cache.delete(key)
            logger.info(
                f"ModelTrainingHandler: Auto-training triggered for vehicle_id: {vehicle_id}"
            )

            try:
                # Circular dependency'i engellemek için fonksiyon içinde import alıyoruz
                from v2.modules.prediction_ml.application.ensemble_service import (
                    get_ensemble_service,
                )

                svc = get_ensemble_service()

                # Asenkron bir eğitimi arka planda başlat (task olarak)
                loop = asyncio.get_running_loop()
                if loop and loop.is_running():
                    task = loop.create_task(svc.train_for_vehicle(vehicle_id))
                    self._bg_tasks.add(task)
                    task.add_done_callback(self._bg_tasks.discard)

                    # RAG/cache invalidation event'ini yayınla
                    await self.event_bus.publish_simple_async(
                        EventType.CACHE_INVALIDATED, entity="model", arac_id=vehicle_id
                    )

            except Exception as e:
                logger.error(
                    f"Error triggering auto-train for vehicle {vehicle_id}: {e}"
                )
        else:
            # Henüz threshold'a ulaşmadı — sayaç Redis'te tutulsun.
            self._cache.set(key, current_count, ttl_seconds=_COUNTER_TTL_S)


# Singleton Instance
_model_training_handler = None


def get_model_training_handler() -> ModelTrainingHandler:
    global _model_training_handler
    if _model_training_handler is None:
        _model_training_handler = ModelTrainingHandler()
    return _model_training_handler
