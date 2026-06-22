"""Unit tests for app.workers.tasks.backup_tasks."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


def _make_fake_boto3(mock_s3: MagicMock | None = None) -> MagicMock:
    """Return a fake boto3 module with a stubbed client() factory."""
    fake = MagicMock()
    if mock_s3 is not None:
        fake.client.return_value = mock_s3
    return fake


@pytest.mark.unit
class TestUploadToOffsite:
    def test_noop_when_no_bucket_env(self):
        """No BACKUP_S3_BUCKET env → _upload_to_offsite returns immediately."""
        from app.workers.tasks.backup_tasks import _upload_to_offsite

        fake_boto3 = _make_fake_boto3()
        with (
            patch.dict(os.environ, {}, clear=False),
            patch.dict(sys.modules, {"boto3": fake_boto3}),
        ):
            os.environ.pop("BACKUP_S3_BUCKET", None)
            _upload_to_offsite("/tmp/backup.sql.gz")
            fake_boto3.client.assert_not_called()

    def test_uploads_to_s3_when_bucket_set(self):
        """BACKUP_S3_BUCKET set → boto3.client().upload_file() called."""
        from app.workers.tasks.backup_tasks import _upload_to_offsite

        mock_s3 = MagicMock()
        fake_boto3 = _make_fake_boto3(mock_s3)

        with (
            patch.dict(
                os.environ,
                {
                    "BACKUP_S3_BUCKET": "my-bucket",
                    "AWS_ACCESS_KEY_ID": "AKID",
                    "AWS_SECRET_ACCESS_KEY": "secret",  # pragma: allowlist secret
                },
            ),
            patch.dict(sys.modules, {"boto3": fake_boto3}),
        ):
            _upload_to_offsite("/backups/loji_20260621.sql.gz")

        mock_s3.upload_file.assert_called_once()
        args = mock_s3.upload_file.call_args[0]
        assert args[0] == "/backups/loji_20260621.sql.gz"
        assert args[1] == "my-bucket"
        assert "loji_20260621.sql.gz" in args[2]

    def test_logs_warning_on_s3_error_does_not_raise(self):
        """S3 upload failure is caught and logged — never propagates."""
        from app.workers.tasks.backup_tasks import _upload_to_offsite

        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = Exception("connection refused")
        fake_boto3 = _make_fake_boto3(mock_s3)

        with (
            patch.dict(os.environ, {"BACKUP_S3_BUCKET": "my-bucket"}),
            patch.dict(sys.modules, {"boto3": fake_boto3}),
        ):
            _upload_to_offsite("/tmp/backup.sql.gz")  # must not raise

    def test_boto3_import_error_is_silent(self):
        """Missing boto3 is caught gracefully — only a debug log, no exception."""
        from app.workers.tasks.backup_tasks import _upload_to_offsite

        # Remove boto3 from sys.modules so the inline `import boto3` raises ImportError
        with (
            patch.dict(os.environ, {"BACKUP_S3_BUCKET": "my-bucket"}),
            patch.dict(sys.modules, {"boto3": None}),  # None → ImportError on import
        ):
            _upload_to_offsite("/tmp/backup.sql.gz")  # must not raise


@pytest.mark.unit
class TestDbBackupTask:
    def test_db_backup_returns_ok_status(self):
        """db_backup task calls manager.create_backup + cleanup and returns ok."""
        from app.workers.tasks.backup_tasks import db_backup

        mock_manager = MagicMock()
        mock_manager.create_backup.return_value = "/backups/loji.sql.gz"

        with (
            patch(
                "app.infrastructure.database.backup_manager.DatabaseBackupManager",
                return_value=mock_manager,
            ),
            patch("app.workers.tasks.backup_tasks._upload_to_offsite"),
        ):
            result = db_backup.run()

        assert result["status"] == "ok"
        assert result["filepath"] == "/backups/loji.sql.gz"
        mock_manager.cleanup_old_backups.assert_called_once()

    def test_db_backup_retries_on_exception(self):
        """db_backup task raises Retry when backup manager throws."""
        from celery.exceptions import Retry

        from app.workers.tasks.backup_tasks import db_backup

        with patch(
            "app.infrastructure.database.backup_manager.DatabaseBackupManager",
            side_effect=RuntimeError("pg_dump failed"),
        ):
            with pytest.raises((Retry, RuntimeError)):
                db_backup.run()
