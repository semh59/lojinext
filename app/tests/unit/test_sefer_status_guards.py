from pathlib import Path

from v2.modules.trip.domain.trip_validation import ALLOWED_TRANSITIONS
from v2.modules.trip.schemas import SeferDurum, TripStatus

# The full canonical status set (5-state machine as of v2.1)
EXPECTED_STATUS_SET = {s.value for s in TripStatus}


def test_status_literal_set_is_single_source_of_truth():
    """SeferDurum Literal must include all TripStatus enum values."""
    schema_values = set(SeferDurum.__args__)
    assert schema_values == EXPECTED_STATUS_SET, (
        f"SeferDurum Literal values {schema_values} don't match TripStatus enum {EXPECTED_STATUS_SET}"
    )

    # ALLOWED_TRANSITIONS keys are TripStatus enum members; their .value must equal the set
    transition_values = {k.value for k in ALLOWED_TRANSITIONS.keys()}
    assert transition_values == EXPECTED_STATUS_SET, (
        f"ALLOWED_TRANSITIONS keys {transition_values} don't match {EXPECTED_STATUS_SET}"
    )

    # Allowed target states must all be valid TripStatus values
    for source, allowed in ALLOWED_TRANSITIONS.items():
        allowed_values = {t.value for t in allowed}
        assert allowed_values.issubset(EXPECTED_STATUS_SET), (
            f"Invalid target statuses for {source}: {allowed_values - EXPECTED_STATUS_SET}"
        )


def test_runtime_contract_files_do_not_use_legacy_ascii_status_literals():
    root = Path(__file__).resolve().parents[3]
    checked_files = [
        root / "v2" / "modules" / "trip" / "schemas.py",
        root / "v2" / "modules" / "trip" / "application" / "update_trip.py",
        root / "v2" / "modules" / "trip" / "infrastructure" / "repository.py",
    ]
    legacy_ascii_statuses = [
        "Planlandi",
        "Tamamlandi",
    ]  # "Iptal" is in transition dict as comment

    for file_path in checked_files:
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        for token in legacy_ascii_statuses:
            assert token not in content, (
                f"{file_path} still contains legacy token: {token}"
            )


def test_legacy_ascii_aliases_exist_only_in_normalizer():
    """ASCII fallback aliases must live in trip_status.py (the canonical normalizer)."""
    root = Path(__file__).resolve().parents[3]
    # trip_status.py is the real normalizer; sefer_status.py just re-exports it
    normalizer_file = root / "v2" / "modules" / "trip" / "trip_status.py"
    content = normalizer_file.read_text(encoding="utf-8")

    for token in ("Iptal", "Planlandi", "Tamamlandi"):
        assert token in content, (
            f"Legacy alias '{token}' missing from normalizer {normalizer_file}"
        )
