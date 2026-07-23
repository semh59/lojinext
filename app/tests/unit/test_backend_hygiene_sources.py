from pathlib import Path

import pytest

from v2.modules.platform_infra.events.event_bus import EventType as BusEventType
from v2.modules.platform_infra.events.event_types import EventType as CanonicalEventType


def test_event_type_uses_single_canonical_source():
    assert CanonicalEventType is BusEventType


@pytest.mark.parametrize(
    "relative_path",
    [
        "v2/modules/ai_assistant/application/knowledge_base.py",
    ],
)
def test_phase11_target_files_are_mojibake_free(relative_path):
    repo_root = Path(__file__).resolve().parents[3]
    content = (repo_root / relative_path).read_text(encoding="utf-8")
    bad_tokens = ("\u00c3", "\u00c2", "\u00c5", "\ufffd")
    for token in bad_tokens:
        assert token not in content
