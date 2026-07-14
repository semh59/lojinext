"""
Domain servisleri — iş kuralları, doğrulama, UoW transaction yönetimi.

Doğrudan DB erişimi yoktur; repository'ler üzerinden çalışır.
Örnekler: SeferWriteService, AnomalyDetector

Yeni servis nereye gider?
  DB + iş kuralı            → app/core/services/
  ML/AI orkestrasyonu       → app/services/
  Dış API entegrasyonu      → app/services/
"""

from .analiz_service import AnalizService

__all__ = ["AnalizService"]
