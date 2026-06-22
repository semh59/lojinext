from pathlib import Path

import pytest

from app.infrastructure.audit.audit_logger import audit_log as canonical_audit_log
from app.infrastructure.events.contracts import EventType as ContractEventType
from app.infrastructure.events.contracts import TripCreatedEvent
from app.infrastructure.events.event_bus import EventBus
from app.infrastructure.events.event_bus import EventType as BusEventType
from app.infrastructure.events.event_types import EventType as CanonicalEventType
from app.infrastructure.logging.audit_logger import (
    _mask_sensitive_data,
)
from app.infrastructure.logging.audit_logger import (
    audit_log as compat_audit_log,
)


def test_event_type_uses_single_canonical_source():
    assert CanonicalEventType is ContractEventType
    assert CanonicalEventType is BusEventType


def test_publish_typed_uses_canonical_event_type():
    bus = EventBus()
    bus.reset_all_for_tests()
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe(CanonicalEventType.TRIP_CREATED, handler)
    bus.publish_typed(
        TripCreatedEvent(
            event_id="typed-trip-1",
            event_type=CanonicalEventType.TRIP_CREATED,
            payload={"trip_id": 7},
        )
    )

    assert len(received) == 1
    assert received[0].type is CanonicalEventType.TRIP_CREATED
    assert received[0].data == {"trip_id": 7}


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
        "app/infrastructure/events/contracts.py",
        "app/infrastructure/logging/audit_logger.py",
    ],
)
def test_phase11_target_files_are_mojibake_free(relative_path):
    repo_root = Path(__file__).resolve().parents[3]
    content = (repo_root / relative_path).read_text(encoding="utf-8")
    bad_tokens = ("\u00c3", "\u00c2", "\u00c5", "\ufffd")
    for token in bad_tokens:
        assert token not in content
