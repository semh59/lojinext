"""`app/infrastructure/logging/logger.py`'den dalga 17 (platform_infra)
denetiminde taşındı — projenin en yaygın kullanılan dosyası (tüm 15 iş
modülü + shared_kernel + platform_infra'nın kendisi `get_logger()`'ı
kullanıyor)."""

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

# Log dizini
# Log dizini (Proje Kök Dizini) — dalga 17 taşımasıyla dosya bir kademe
# derinleşti (app/infrastructure/logging/ -> v2/modules/platform_infra/logging/),
# bu yüzden kök dizine çıkmak için 5. .parent gerekiyor (4 değil).
LOG_DIR = Path(__file__).parent.parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

from app.config import settings  # noqa: E402


class PIIFilter(logging.Filter):
    """
    Log kayıtlarındaki hassas verileri (PII) maskeler.
    Ayrıca log injection koruması sağlar.
    """

    def __init__(self, name=""):
        super().__init__(name)
        self.patterns = [
            (settings.LOG_PII_MASK_EMAIL, "<EMAIL_MASKED>"),
            (settings.LOG_PII_MASK_PHONE, "<PHONE_MASKED>"),
            (settings.LOG_PII_MASK_TCKN, "<TCKN_MASKED>"),
            # Key-Value masking (password: 123, token="abc")
            (
                r"(?i)("
                + "|".join(settings.LOG_PII_SENSITIVE_KEYS)
                + r')\s*[:=]\s*["\']?([^"\'\s,{}]+)["\']?',
                r"\1: ***MASKED***",
            ),
        ]

    def filter(self, record):
        try:
            if not hasattr(record, "msg"):
                return True

            from v2.modules.platform_infra.security.pii_scrubber import scrub_pii

            # Log injection protection
            msg = str(record.msg).replace("\n", "\\n").replace("\r", "\\r")
            record.msg = scrub_pii(msg)

            # Mask extra args
            if hasattr(record, "args") and record.args:
                if isinstance(record.args, tuple):
                    record.args = tuple(scrub_pii(arg) for arg in record.args)
                elif isinstance(record.args, dict):
                    record.args = scrub_pii(record.args)
        except Exception:
            pass
        return True

    def _is_sensitive_key(self, key: Any) -> bool:
        if not isinstance(key, str):
            return False
        sensitive = {
            "password",
            "token",
            "secret",
            "api_key",
            "apikey",
            "auth",
            "jwt",
            "credential",
            "sifre",
        }
        return any(s in key.lower() for s in sensitive)


class JSONFormatter(logging.Formatter):
    """Log kayıtlarını JSON formatına çeviren formatter"""

    # Standart LogRecord attribute'ları (bunlar extra'dan hariç tutulacak)
    _RESERVED_ATTRS = frozenset(
        [
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "message",
        ]
    )

    def format(self, record: logging.LogRecord) -> str:
        # Correlation ID'yi context'ten al
        correlation_id = ""
        try:
            from v2.modules.platform_infra.context.request_context import (
                get_correlation_id,
            )

            correlation_id = get_correlation_id()
        except Exception:
            pass

        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
            "line_no": record.lineno,
        }

        # Correlation ID ekle
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Extra veriler: record'a eklenen tüm custom attribute'lar
        for key, value in record.__dict__.items():
            if key not in self._RESERVED_ATTRS and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logging(
    app_name: str = "tir_yakit", level: int = logging.INFO
) -> logging.Logger:
    """
    Enterprise-grade logging setup

    Features:
    - Rotating file handler (JSON format, 10MB max, 7 backup)
    - Console handler (Readable text format)
    - UTF-8 encoding for Turkish characters
    """

    # Konsol için okunabilir format
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Dosya için JSON format
    json_formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    # File handler - Rotating (Daily is implied by name in old code, here we use size rotation)
    log_file = LOG_DIR / f"{app_name}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(PIIFilter())

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)
    console_handler.addFilter(PIIFilter())

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Cleanup old handlers
    root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger(app_name)
    logger.info(
        "Logging initialized", extra={"event": "startup", "log_file": str(log_file)}
    )

    return logger


class AuditLogger:
    """Security ve Audit olayları için özel logger"""

    def __init__(self):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        # Ayrı dosya: logs/audit.log
        audit_file = LOG_DIR / "audit.log"
        # Temizle ve ekle
        self.logger.handlers.clear()

        handler = RotatingFileHandler(
            audit_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=30,  # 1 ay sakla
            encoding="utf-8",
        )
        handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
        handler.addFilter(PIIFilter())
        self.logger.addHandler(handler)
        self.logger.propagate = False  # Ana loga düşmesin

    def log(
        self, event: str, user: str, details: Dict[str, Any], status: str = "SUCCESS"
    ):
        """
        Audit kaydı oluştur.

        Args:
            event: Olay türü (LOGIN, DELETE_USER, etc.)
            user: İşlemi yapan kullanıcı
            details: Olay detayları
            status: SUCCESS / FAILURE
        """
        log_data = {
            "audit_event": event,
            "actor": user,
            "status": status,
            "details": details,
        }
        self.logger.info(f"AUDIT | {event} | {user} | {status}", extra=log_data)


# Singleton Audit Logger
_audit_logger = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_logger(name: str) -> logging.Logger:
    """Module bazlı logger instance getirir"""
    return logging.getLogger(name)
