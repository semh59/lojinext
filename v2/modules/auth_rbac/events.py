"""Events published by the auth_rbac module.

STATUS: farklı olarak diğer taşınan modüllerden (location/notification/
fleet/fuel/driver — hepsinin ölü `@publishes` decorator'lı KULLANICI_*/
YAKIT_*/ARAC_* event tipleri vardı), ``app/infrastructure/events/
event_bus.py::EventType`` içinde KULLANICI_ADDED/UPDATED/DELETED veya
ROL_ADDED/UPDATED gibi bir enum değeri YOK — bu modül hiçbir zaman
event-bus'a bağlanmadı (taşımadan önce de böyleydi, regresyon değil,
`grep -rn "KULLANICI_\\|ROL_ADDED" app/ v2/` ile doğrulandı).
"""

__all__: list[str] = []
