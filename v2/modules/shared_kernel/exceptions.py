"""
LojiNext domain exception hiyerarşisi.

HTTP mapping (app/main.py handler'ları tarafından kullanılır):
- FuelCalculationError, ImportValidationError, ExcelExportError,
  RouteProcessingError → 422 Unprocessable Entity
- MLPredictionError, AnomalyDetectionError → 503 Service Unavailable
- AuditLogError → 500 Internal Server Error (kullanıcıya gizli)

Kullanım:
  raise FuelCalculationError("Depo aşımı", field_name="yakit_miktari", entity_id=sefer_id)
  raise ImportValidationError(["Plaka boş"], row=3)
"""

from typing import Optional


class DomainError(Exception):
    """Tüm domain exception'larının base sınıfı."""

    def __init__(
        self,
        message: str,
        *,
        field_name: Optional[str] = None,
        entity_id: Optional[int | str] = None,
        reason: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.entity_id = entity_id
        self.reason = reason

    def to_dict(self) -> dict:
        """Handler'lar için JSON-serializable context."""
        d: dict = {"message": str(self)}
        if self.field_name:
            d["field"] = self.field_name
        if self.entity_id is not None:
            d["entity_id"] = self.entity_id
        if self.reason:
            d["reason"] = self.reason
        return d


class FuelCalculationError(DomainError):
    """Yakıt hesaplama veya tahmin hatası. → HTTP 422"""


class ImportValidationError(DomainError):
    """Import doğrulama hatası; hata listesi taşır. → HTTP 422"""

    def __init__(
        self,
        errors: list[str],
        *,
        row: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        self.errors = errors
        self.row = row
        super().__init__(
            "; ".join(errors),
            reason=reason or "IMPORT_VALIDATION_FAILED",
            entity_id=row,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["errors"] = self.errors
        if self.row is not None:
            d["row"] = self.row
        return d


class ExcelExportError(DomainError):
    """Excel parse veya export hatası. → HTTP 422"""


class RouteProcessingError(DomainError):
    """Güzergah işleme hatası (ORS API, mesafe hesaplama). → HTTP 424 or 422"""

    def __init__(
        self,
        message: str,
        *,
        provider_status: Optional[int] = None,
        field_name: Optional[str] = None,
        entity_id: Optional[int | str] = None,
        reason: Optional[str] = None,
    ) -> None:
        self.provider_status = provider_status
        super().__init__(
            message,
            field_name=field_name,
            entity_id=entity_id,
            reason=reason,
        )

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.provider_status is not None:
            d["provider_status"] = self.provider_status
        return d


class MLPredictionError(DomainError):
    """ML modeli tahmin hatası; physics fallback yeterli olmadığında. → HTTP 503"""


class AnomalyDetectionError(DomainError):
    """Anomali tespiti pipeline hatası. → HTTP 503"""


class AuditLogError(DomainError):
    """Audit log yazım hatası — asla kullanıcıya yayılmamalı. → HTTP 500"""


class LLMProviderError(DomainError):
    """Dış LLM sağlayıcı çağrısı başarısız (Groq API hatası/timeout/geçersiz
    anahtar). → HTTP 503. GroqService/LLMClient tarafından fırlatılır —
    önceden bu hatayı sessizce yutup metnini sahte bir "asistan cevabı"
    olarak dönüyorlardı (çağıran taraftaki try/except hiç tetiklenmiyordu)."""
