import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """
    Handles PostgreSQL database backups and retention.
    """

    def __init__(self):
        self.backup_dir = "storage/backups"
        self.database_url = make_url(settings.DATABASE_URL)
        self.drivername = self.database_url.drivername
        self.db_host = self.database_url.host or "localhost"
        self.db_port = self.database_url.port or 5432
        self.db_user = self.database_url.username or ""
        self.db_password = self.database_url.password or ""
        self.db_name = self.database_url.database or "backup"
        self.retention_days = settings.BACKUP_RETENTION_DAYS

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self) -> str:
        """Creates a timestamped database dump."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.drivername.startswith("sqlite"):
            filename = f"{self.db_name}_{timestamp}.sqlite3"
            filepath = os.path.join(self.backup_dir, filename)
            source = Path(self.database_url.database or "")
            if not source:
                raise RuntimeError("SQLite database path is empty.")
            if not source.is_absolute():
                source = Path.cwd() / source
            if not source.exists():
                raise RuntimeError(f"SQLite database file not found: {source}")
            logger.info(f"Starting sqlite backup: {filename}")
            shutil.copy2(source, filepath)
            logger.info(f"Backup completed successfully: {filepath}")
            return filepath

        if not self.drivername.startswith("postgresql"):
            raise RuntimeError(
                "Manual backup is only supported for PostgreSQL or SQLite databases."
            )

        filename = f"{self.db_name}_{timestamp}.sql.gz"
        filepath = os.path.join(self.backup_dir, filename)

        # Note: In a containerized environment, PGPASSWORD env var should be set
        # or a .pgpass file used. Here we assume the env is correctly configured.
        # Dumps to gzip-compressed format (-Fc) to reduce size and reduce
        # plaintext exposure. For at-rest encryption, pipe through openssl/GPG
        # with a key managed via a secrets manager (recommended for production).
        cmd = [
            "pg_dump",
            "-h",
            self.db_host,
            "-p",
            str(self.db_port),
            "-U",
            self.db_user,
            "-F",
            "c",  # Custom compressed format (pg_restore compatible)
            "-f",
            filepath,
            self.db_name,
        ]

        try:
            logger.info(f"Starting backup: {filename}")
            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password
            subprocess.run(cmd, check=True, capture_output=True, env=env)
            logger.info(f"Backup completed successfully: {filepath}")
            return filepath
        except subprocess.CalledProcessError as e:
            logger.error(f"Backup failed: {e.stderr.decode()}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during backup: {e}")
            raise

    def cleanup_old_backups(self):
        """Removes backups older than the retention threshold."""
        now = datetime.now()
        threshold = now - timedelta(days=self.retention_days)
        _BACKUP_EXTENSIONS = {".sql", ".sql.gz", ".sqlite3"}

        for filename in os.listdir(self.backup_dir):
            if not any(filename.endswith(ext) for ext in _BACKUP_EXTENSIONS):
                continue

            filepath = os.path.join(self.backup_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

            if file_time < threshold:
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted old backup: {filename}")
                except Exception as e:
                    logger.error(f"Failed to delete {filename}: {e}")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    manager = DatabaseBackupManager()
    if "--test" in sys.argv:
        try:
            manager.create_backup()
            manager.cleanup_old_backups()
        except Exception:
            sys.exit(1)
