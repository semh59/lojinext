from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import blake2b
from typing import Any


class ErrorLayer(str, Enum):
    DB = "db"
    CELERY = "celery"
    API = "api"
    SERVICE = "service"
    FRONTEND = "frontend"
    EXTERNAL = "external"
    SECURITY = "security"
    ML = "ml"


class ErrorSeverity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_NUMBER_RE = re.compile(r"\d+")
_STRING_RE = re.compile(r"'[^']*'")
_UUID_PATTERN = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
_UUID_RE = re.compile(_UUID_PATTERN, re.I)


def make_fingerprint(layer: str, category: str, message: str) -> str:
    """Blake2b-64bit fingerprint. Normalizes numbers, strings, UUIDs."""
    normalized = _UUID_RE.sub("UUID", message)
    normalized = _STRING_RE.sub("'S'", normalized)  # single quotes
    normalized = normalized.replace('"', "'")  # normalize double to single
    normalized = _STRING_RE.sub("'S'", normalized)  # then normalize single strings
    normalized = _NUMBER_RE.sub("N", normalized)  # numbers second
    raw = f"{layer}:{category}:{normalized}".encode()
    return blake2b(raw, digest_size=8).hexdigest()


@dataclass
class ErrorEvent:
    layer: ErrorLayer
    category: str
    severity: ErrorSeverity
    message: str
    trace_id: str = ""
    path: str = ""
    stack_trace: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = field(init=False)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.layer, str):
            self.layer = ErrorLayer(self.layer)
        if isinstance(self.severity, str):
            self.severity = ErrorSeverity(self.severity)
        self.fingerprint = make_fingerprint(
            self.layer.value, self.category, self.message
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer.value,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "fingerprint": self.fingerprint,
            "trace_id": self.trace_id,
            "path": self.path,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata,
            "occurred_at": self.occurred_at.isoformat(),
        }
