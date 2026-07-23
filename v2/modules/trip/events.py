"""Event surface of the trip module.

Trip kendi ``EventType``'ını tanımlamaz — `v2.modules.platform_infra.events.event_bus.EventType`
üzerinden paylaşılan sabitleri kullanır (henüz `shared_kernel`'e taşınmadı).

**Yayınlar:**
- ``SEFER_ADDED`` (``add_sefer``, outbox üzerinden, payload
  ``{sefer_id, sefer_no, arac_id}``) — prediction_ml'in
  ``ModelTrainingHandler``'ı bunu dinler (her 5 yeni kayıtta otomatik
  retrain). **2026-07-23 düzeltmesi**: payload'da `arac_id` eksikti,
  `ModelTrainingHandler.on_data_added` bunu bulamayınca sessizce dönüyordu
  — sefer girişiyle büyüyen araçlarda otomatik retrain hiç tetiklenmiyordu
  (yalnız YAKIT_ADDED tarafı çalışıyordu, o payload'da `arac_id` zaten
  vardı). Bağımsız dedektif denetiminde bulundu, `add_trip.py`'ye
  `"arac_id": data.arac_id` eklenerek düzeltildi.
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

from v2.modules.platform_infra.events.event_bus import EventType

__all__ = ["EventType"]
