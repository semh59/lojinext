"""Events ait reports modülüne.

Bu modülün kendi CRUD/lifecycle event'i YOK — read-only rapor/analiz
üretimi yapar, hiçbir varlığı yaratmaz/değiştirmez. Kaynak dosyalarda
(`report_service.py`/`report_generator.py`/`triage_aggregator.py`/
`fleet_comparison.py`) `@publishes`/`event_bus.publish(...)` çağrısı yoktu
(grep ile doğrulandı) — taşıma bu boşluğu değiştirmedi.
"""

__all__: list = []
