from pathlib import Path


def test_trip_endpoints_do_not_use_uow_or_repo_directly():
    root = Path(__file__).resolve().parents[3]
    endpoint_file = root / "app" / "api" / "v1" / "endpoints" / "trips.py"
    content = endpoint_file.read_text(encoding="utf-8")

    forbidden_patterns = [
        "UnitOfWork",
        "uow.",
        ".sefer_repo",
        ".audit_repo",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in content, (
            f"Direct data-layer access detected in trips endpoint: {pattern}"
        )
