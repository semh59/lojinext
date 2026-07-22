from pathlib import Path

import pytest

from app.infrastructure.audit.audit_logger import audit_log as canonical_audit_log
from app.infrastructure.logging.audit_logger import (
    _mask_sensitive_data,
)
from app.infrastructure.logging.audit_logger import (
    audit_log as compat_audit_log,
)
from v2.modules.platform_infra.events.event_bus import EventType as BusEventType
from v2.modules.platform_infra.events.event_types import EventType as CanonicalEventType


def test_event_type_uses_single_canonical_source():
    assert CanonicalEventType is BusEventType


def test_audit_logger_shim_points_to_canonical_source():
    assert compat_audit_log is canonical_audit_log
    masked = _mask_sensitive_data(
        {"password": "secret", "token": "abc", "name": "visible"}
    )
    assert masked["password"] == "***MASKED***"
    assert masked["token"] == "***MASKED***"
    assert masked["name"] == "visible"


@pytest.mark.parametrize(
    "relative_path",
    [
        "app/services/smart_ai_service.py",
        "app/infrastructure/logging/audit_logger.py",
    ],
)
def test_phase11_target_files_are_mojibake_free(relative_path):
    repo_root = Path(__file__).resolve().parents[3]
    content = (repo_root / relative_path).read_text(encoding="utf-8")
    bad_tokens = ("\u00c3", "\u00c2", "\u00c5", "\ufffd")
    for token in bad_tokens:
        assert token not in content
