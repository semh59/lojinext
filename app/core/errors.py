from typing import Any, Optional

from fastapi.responses import JSONResponse

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DiagnosticHelper:
    """
    Kullanıcı hataları için otomatik teşhis ve çözüm önerisi sunar (Phase 4).
    """

    SUGGESTED_FIXES = {
        "BUSINESS_ERROR": "İş kuralı ihlali tespit edildi. Girdiğiniz verilerin limitler dahilinde olduğundan emin olun.",  # noqa: E501
        "VALIDATION_ERROR": "Form verileri geçersiz. Lütfen kırmızı ile işaretlenen alanları kontrol edin.",
        "DB_ERROR": "Veritabanı bağlantı hatası. Lütfen bir süre sonra tekrar deneyin veya sistem yöneticisine bildirin.",  # noqa: E501
        "AUTH_ERROR": "Oturumunuzun süresi dolmuş olabilir. Lütfen tekrar giriş yapın.",
        "EMPTY_TRIP_WITH_LOAD": "Boş sefer (bos_sefer) olarak işaretlenen bir kayıtta yük (tonaj) girişi yapılamaz. Lütfen yükü 0 yapın veya bayrağı kaldırın.",  # noqa: E501
        "ANALYSIS_GAP": "Analiz için yeterli veri periyodu bulunamadı. Lütfen daha fazla yakıt veya sefer verisi ekleyin.",  # noqa: E501
    }

    @classmethod
    def get_suggestion(cls, code: str, message: str) -> Optional[str]:
        # Özel mesaj pattern eşleşmesi
        if "bos_sefer" in message.lower() and "ton" in message.lower():
            return cls.SUGGESTED_FIXES["EMPTY_TRIP_WITH_LOAD"]

        if "gap" in message.lower() or "periyot" in message.lower():
            return cls.SUGGESTED_FIXES["ANALYSIS_GAP"]

        return cls.SUGGESTED_FIXES.get(code)


class BusinessException(Exception):
    """İş mantığı hataları için base class"""

    def __init__(self, message: str, code: str = "BUSINESS_ERROR", details: Any = None):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(self.message)


def create_error_response(
    status_code: int, message: str, code: str, trace_id: str, details: Any = None
) -> JSONResponse:
    """Standart hata yanıtı. Format main.py envelope ile uyumlu: {"error": {"code","message","trace_id"}}."""
    suggestion = DiagnosticHelper.get_suggestion(code, message)
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": trace_id,
    }
    if details is not None:
        error["details"] = details
    if suggestion is not None:
        error["suggestion"] = suggestion
    return JSONResponse(status_code=status_code, content={"error": error})
