"""
Orkestrasyon servisleri — ML pipeline, dış API entegrasyonu, yüksek seviye iş akışları.

app/core/services'i tüketir; endpoint'lere hazır, soyutlanmış API sunar.
Örnekler: PredictionService, RouteService, SmartAIService

Yeni servis nereye gider?
  DB + iş kuralı            → app/core/services/
  ML/AI orkestrasyonu       → app/services/
  Dış API entegrasyonu      → app/services/
"""
