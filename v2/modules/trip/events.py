"""Event surface of the trip module.

Trip kendi ``EventType``'ını tanımlamaz — `app.infrastructure.events.event_bus.EventType`
üzerinden paylaşılan sabitleri kullanır (henüz `shared_kernel`'e taşınmadı).

**Yayınlar:**
- ``SEFER_ADDED`` (``add_sefer``, outbox üzerinden) — prediction_ml'in
  ``ModelTrainingHandler``'ı bunu dinler (her 5 yeni kayıtta otomatik retrain).
- ``SEFER_DELETED`` (``delete_sefer``)
- ``SEFER_UPDATED`` (``reconcile_costs`` — maliyet dağıtımı sonrası her
  sefer için) — prediction_ml'in ``PhysicsRecalculationHandler``'ı bunu
  dinler (manuel override sonrası fizik tabanlı tüketimi yeniden hesaplar).
- ``ROUTE_COMPLETED`` (``update_trip.py::update_sefer_uow`` — durum
  Completed'e geçtiğinde)
- ``SLA_DELAY`` (``application/sla.py::check_sla_delay`` — tamamlanan
  seferin planlanan süreyi aşması durumunda, outbox üzerinden)
- ``ANOMALY_DETECTED`` (``reconcile_costs`` — dağıtılan tüketim eşiği
  aştığında, ``type="HIGH_CONSUMPTION"``)

**Dinlemez:** trip kendi event handler'ı yok — event akışı tek yönlü
(trip → diğer modüller).
"""

from app.infrastructure.events.event_bus import EventType

__all__ = ["EventType"]
