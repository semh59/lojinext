"""Events consumed/published by prediction_ml.

Bu modül kendi EventType'ını TANIMLAMAZ — sadece diğer modüllerin (fuel,
trip) yayınladığı event'lere abone olur ve genel-amaçlı cache-invalidation
event'i yayınlar:

- **Dinler**: ``YAKIT_ADDED``/``SEFER_ADDED`` (``ModelTrainingHandler`` —
  her 5 yeni kayıtta bir aracın ensemble modelini arka planda otomatik
  yeniden eğitir), ``SEFER_UPDATED`` (``PhysicsRecalculationHandler`` —
  manuel override sonrası fizik tabanlı tüketimi yeniden hesaplar;
  ``trigger="physics_recalculation"`` ile kendi tetiklediği güncellemeyi
  yok sayarak sonsuz döngüyü engeller).
- **Yayınlar**: ``CACHE_INVALIDATED`` (model retrain sonrası), ``SEFER_UPDATED``
  (fizik yeniden hesaplama sonrası, ``trigger="physics_recalculation"``
  etiketiyle).

Her iki handler da ``app/main.py``'nin lifespan startup'ında
``get_model_training_handler().setup()`` / ``get_physics_handler().register()``
ile bağlanır.
"""

from app.infrastructure.events.event_bus import EventType

YAKIT_ADDED = EventType.YAKIT_ADDED
SEFER_ADDED = EventType.SEFER_ADDED
SEFER_UPDATED = EventType.SEFER_UPDATED
CACHE_INVALIDATED = EventType.CACHE_INVALIDATED

__all__ = ["YAKIT_ADDED", "SEFER_ADDED", "SEFER_UPDATED", "CACHE_INVALIDATED"]
