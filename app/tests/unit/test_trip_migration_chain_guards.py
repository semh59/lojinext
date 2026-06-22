from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _migration_path(root: Path, filename: str) -> Path:
    active = root / "alembic" / "versions" / filename
    if active.exists():
        return active

    archived = root / "alembic" / "legacy_versions_archive" / filename
    return archived


def test_trip_migration_chain_order():
    root = Path(__file__).resolve().parents[3]
    tahmin_meta = _read(
        _migration_path(root, "b3c2d1e7f890_add_tahmin_meta_to_seferler.py")
    )
    rbac_align = _read(
        _migration_path(root, "e4b6a9c7d201_align_trip_permissions_with_rbac.py")
    )
    sefer_log_fk = _read(
        _migration_path(root, "f1a2b3c4d5e6_add_fk_to_seferler_log.py")
    )

    assert (
        'down_revision: Union[str, Sequence[str], None] = "0727e4e88432"' in tahmin_meta
    )
    assert (
        'down_revision: Union[str, Sequence[str], None] = "b3c2d1e7f890"' in rbac_align
    )
    assert (
        'down_revision: Union[str, Sequence[str], None] = "e4b6a9c7d201"'
        in sefer_log_fk
    )


def test_sefer_log_fk_migration_has_orphan_cleanup_and_safe_downgrade():
    root = Path(__file__).resolve().parents[3]
    migration = _read(_migration_path(root, "f1a2b3c4d5e6_add_fk_to_seferler_log.py"))

    assert "DELETE FROM seferler_log" in migration
    assert "NOT IN (SELECT id FROM seferler)" in migration
    assert "op.create_foreign_key(" in migration
    assert 'ondelete="CASCADE"' in migration
    assert "op.drop_constraint(" in migration
