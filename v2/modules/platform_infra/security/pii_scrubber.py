"""`app/infrastructure/security/pii_scrubber.py`'den dalga 17 (platform_infra)
denetiminde taşındı — `logging/logger.py`'nin PIIFilter'ı + `audit/
audit_logger.py`'nin audit_log decorator'ı + main.py'nin Sentry hook'u
üzerinden tüm sisteme dolaylı yayılan genuinely cross-cutting altyapı."""

import re
from typing import Any

# Sensitive keys to mask (case-insensitive)
SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "auth",
    "jwt",
    "credential",
    "sifre",
    "hash",
    "telefon",
    "phone",
    "tc_no",
    "tckn",
    "tc_kimlik",
    "email",
    "e_posta",
    "adres",
    "address",
}

# Regex patterns for common sensitive formats (order matters — TCKN before phone)
PII_PATTERNS = [
    (r"[\w\.-]+@[\w\.-]+\.\w+", "<EMAIL_MASKED>"),  # Email
    (r"\b[1-9]\d{10}\b", "<TCKN_MASKED>"),  # TCKN: 11 digits, first digit 1-9
    (r"\+?\d{10,13}", "<PHONE_MASKED>"),  # Phone numbers (10-13 digits)
]


def scrub_pii(data: Any) -> Any:
    """
    Recursively masks sensitive data in dictionaries, lists, and strings.
    """
    if isinstance(data, dict):
        return {
            k: scrub_pii(v) if not _is_sensitive_key(k) else "***MASKED***"
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [scrub_pii(i) for i in data]
    elif isinstance(data, str):
        processed = data
        for pattern, mask in PII_PATTERNS:
            processed = re.sub(pattern, mask, processed)
        return processed
    return data


def _is_sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    key_lower = key.lower()
    return any(s in key_lower for s in SENSITIVE_KEYS)
