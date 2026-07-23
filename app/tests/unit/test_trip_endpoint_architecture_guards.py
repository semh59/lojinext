from pathlib import Path


def test_trip_endpoints_do_not_use_uow_or_repo_directly():
    """dalga 14'te eski `app/api/v1/endpoints/trips.py` (1017 satır, 22
    route) 4 trip route dosyasına bölündü — bkz. v2/modules/trip/CLAUDE.md
    'Router bölünmesi' bölümü."""
    root = Path(__file__).resolve().parents[3]
    trip_api_dir = root / "v2" / "modules" / "trip" / "api"
    content = "".join(
        p.read_text(encoding="utf-8") for p in trip_api_dir.glob("*.py")
    )

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
