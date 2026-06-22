"""
Backward-compatible audit logger shim.

Use app.infrastructure.audit.audit_logger as the canonical implementation.
"""

from app.infrastructure.audit.audit_logger import (
    _mask_sensitive_data,
    audit_log,
    get_correlation_id,
    set_correlation_id,
)
from app.infrastructure.logging.logger import get_logger

logger = get_logger("audit")

__all__ = [
    "audit_log",
    "_mask_sensitive_data",
    "get_correlation_id",
    "set_correlation_id",
    "logger",
]
