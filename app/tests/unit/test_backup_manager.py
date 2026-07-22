"""Unit tests for DatabaseBackupManager.get_latest_backup / verify_backup_restorable
(Tier E madde 27 — automated backup restore-test)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_manager(tmp_path):
    with patch("v2.modules.platform_infra.database.backup_manager.settings") as mock_settings:
        mock_settings.DATABASE_URL = "postgresql+asyncpg://u:pw@db:5432/lojinext_db"  # noqa: E501  # pragma: allowlist secret
        mock_settings.BACKUP_RETENTION_DAYS = 30
        from v2.modules.platform_infra.database.backup_manager import (
            DatabaseBackupManager,
        )

        manager = DatabaseBackupManager.__new__(DatabaseBackupManager)
        manager.backup_dir = str(tmp_path)
        manager.drivername = "postgresql+asyncpg"
        manager.db_host = "db"
        manager.db_port = 5432
        manager.db_user = "lojinext_user"
        manager.db_password = "pw"  # pragma: allowlist secret
        manager.db_name = "lojinext_db"
        manager.retention_days = 30
        return manager


class TestGetLatestBackup:
    def test_returns_none_when_no_backups(self, tmp_path):
        manager = _make_manager(tmp_path)
        assert manager.get_latest_backup() is None

    def test_returns_most_recent_by_mtime(self, tmp_path):
        manager = _make_manager(tmp_path)
        older = tmp_path / "lojinext_db_20260101_000000.sql.gz"
        newer = tmp_path / "lojinext_db_20260102_000000.sql.gz"
        older.write_bytes(b"old")
        newer.write_bytes(b"new")
        import os
        import time

        os.utime(older, (time.time() - 100, time.time() - 100))

        assert manager.get_latest_backup() == str(newer)

    def test_ignores_non_backup_files(self, tmp_path):
        manager = _make_manager(tmp_path)
        (tmp_path / "readme.txt").write_text("not a backup")
        assert manager.get_latest_backup() is None


class TestVerifyBackupRestorable:
    def test_non_postgresql_driver_returns_not_ok(self, tmp_path):
        manager = _make_manager(tmp_path)
        manager.drivername = "sqlite"
        result = manager.verify_backup_restorable("/tmp/x.sqlite3")
        assert result["ok"] is False

    def test_no_backup_file_found_returns_not_ok(self, tmp_path):
        manager = _make_manager(tmp_path)
        result = manager.verify_backup_restorable()
        assert result["ok"] is False
        assert "No PostgreSQL backup file" in result["error"]

    def test_successful_restore_reports_table_count(self, tmp_path):
        """createdb + pg_restore (exit 0) + table-count query (48) -> ok=True."""
        manager = _make_manager(tmp_path)
        backup_file = tmp_path / "lojinext_db_20260702_000000.sql.gz"
        backup_file.write_bytes(b"fake dump")

        createdb_result = MagicMock(returncode=0)
        restore_result = MagicMock(returncode=0, stderr=b"")
        psql_result = MagicMock(returncode=0, stdout="48\n")
        dropdb_result = MagicMock(returncode=0)

        with patch(
            "subprocess.run",
            side_effect=[createdb_result, restore_result, psql_result, dropdb_result],
        ) as mock_run:
            result = manager.verify_backup_restorable(str(backup_file))

        assert result == {
            "ok": True,
            "table_count": 48,
            "filepath": str(backup_file),
        }
        # dropdb must always run (cleanup), even on the success path.
        assert mock_run.call_args_list[-1].args[0][0] == "dropdb"

    def test_pg_restore_nonzero_exit_still_passes_if_tables_landed(self, tmp_path):
        """pg_restore exit 1 (e.g. a client/server GUC-version mismatch warning
        pg_restore itself already logged as 'errors ignored') must NOT fail the
        test on its own — table_count is the real signal (regression guard for
        the real pg17-client/pg16-server 'transaction_timeout' bug found while
        building this feature)."""
        manager = _make_manager(tmp_path)
        backup_file = tmp_path / "lojinext_db_20260702_000000.sql.gz"
        backup_file.write_bytes(b"fake dump")

        createdb_result = MagicMock(returncode=0)
        restore_result = MagicMock(
            returncode=1,
            stderr=b"pg_restore: warning: errors ignored on restore: 1",
        )
        psql_result = MagicMock(returncode=0, stdout="48\n")
        dropdb_result = MagicMock(returncode=0)

        with patch(
            "subprocess.run",
            side_effect=[createdb_result, restore_result, psql_result, dropdb_result],
        ):
            result = manager.verify_backup_restorable(str(backup_file))

        assert result["ok"] is True
        assert result["table_count"] == 48

    def test_empty_schema_after_restore_fails(self, tmp_path):
        """table_count == 0 means the restore produced an empty shell -> ok=False."""
        manager = _make_manager(tmp_path)
        backup_file = tmp_path / "lojinext_db_20260702_000000.sql.gz"
        backup_file.write_bytes(b"fake dump")

        createdb_result = MagicMock(returncode=0)
        restore_result = MagicMock(returncode=0, stderr=b"")
        psql_result = MagicMock(returncode=0, stdout="0\n")
        dropdb_result = MagicMock(returncode=0)

        with patch(
            "subprocess.run",
            side_effect=[createdb_result, restore_result, psql_result, dropdb_result],
        ):
            result = manager.verify_backup_restorable(str(backup_file))

        assert result["ok"] is False
        assert result["table_count"] == 0

    def test_createdb_failure_returns_error_and_still_drops(self, tmp_path):
        manager = _make_manager(tmp_path)
        backup_file = tmp_path / "lojinext_db_20260702_000000.sql.gz"
        backup_file.write_bytes(b"fake dump")

        createdb_error = subprocess.CalledProcessError(
            1, ["createdb"], stderr=b"database already exists"
        )
        dropdb_result = MagicMock(returncode=0)

        with patch(
            "subprocess.run", side_effect=[createdb_error, dropdb_result]
        ) as mock_run:
            result = manager.verify_backup_restorable(str(backup_file))

        assert result["ok"] is False
        assert "database already exists" in result["error"]
        # Cleanup (dropdb) still attempted despite the createdb failure.
        assert mock_run.call_args_list[-1].args[0][0] == "dropdb"
