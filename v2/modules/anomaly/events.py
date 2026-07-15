"""Events ilgili anomaly modülüne.

Bu modülün kendi CRUD event'i YOK (diğer modüllerdeki ANOMALY_ADDED/
UPDATED/DELETED tipi decorator-only ölü-kod deseninden FARKLI olarak burada
o desen bile yok — ``AnomalyDetector.save_anomalies``/``acknowledge``/
``resolve`` hiçbir ``@publishes``/``event_bus.publish`` çağrısı içermiyor,
taşımadan önce de böyleydi).

``EventType.ANOMALY_DETECTED`` var ama bu modülün SAHİBİ OLMADIĞI bir
event — fuel modülü (``v2/modules/fuel/application/add_yakit.py``) ve
henüz taşınmamış trip modülü (``app/core/services/sefer_analiz_service.py``)
tarafından publish edilir, notification modülü
(``v2/modules/notification/application/handle_trip_events.py``) tarafından
consume edilir. anomaly modülü ne publisher ne subscriber'dır — sadece adı
geçer (fuel/trip'in kendi tespit ettiği aykırı tüketimi anomali olarak
etiketlemesi, bu modülün ``anomalies`` tablosuna DEĞİL).
"""

__all__: list = []
