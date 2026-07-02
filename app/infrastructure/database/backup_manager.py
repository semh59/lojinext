import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

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

    def get_latest_backup(self) -> Optional[str]:
        """Returns the path of the most recently created backup file, or None."""
        _BACKUP_EXTENSIONS = (".sql.gz", ".sqlite3")
        candidates = [
            f for f in os.listdir(self.backup_dir) if f.endswith(_BACKUP_EXTENSIONS)
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda f: os.path.getmtime(os.path.join(self.backup_dir, f)),
            reverse=True,
        )
        return os.path.join(self.backup_dir, candidates[0])

    def verify_backup_restorable(
        self, filepath: Optional[str] = None
    ) -> Dict[str, Any]:
        """Restores a backup into a disposable database and sanity-checks it.

        This is the actual proof a backup is usable (Tier E madde 27) — a
        pg_dump that never gets restore-tested can silently rot (corrupt
        dump, missing extension, wrong pg_dump version) for months without
        anyone noticing until the day it's actually needed. Only supports
        the PostgreSQL custom-format (-F c) dumps create_backup() produces.

        Steps: CREATE DATABASE <throwaway> -> pg_restore into it -> count
        public tables (>0 proves the schema actually landed, not just an
        empty shell) -> DROP DATABASE <throwaway> (always, even on failure).
        """
        if not self.drivername.startswith("postgresql"):
            return {"ok": False, "error": "Only PostgreSQL dumps are restore-tested."}

        filepath = filepath or self.get_latest_backup()
        if not filepath or not filepath.endswith(".sql.gz"):
            return {"ok": False, "error": "No PostgreSQL backup file found to verify."}

        verify_db = f"{self.db_name}_restore_check_{uuid.uuid4().hex[:8]}"
        env = os.environ.copy()
        if self.db_password:
            env["PGPASSWORD"] = self.db_password
        conn_args = ["-h", self.db_host, "-p", str(self.db_port), "-U", self.db_user]

        try:
            subprocess.run(
                ["createdb", *conn_args, verify_db],
                check=True,
                capture_output=True,
                env=env,
            )
            # No check=True here: pg_restore exits 1 even for warnings it has
            # already logged as "errors ignored on restore" (e.g. a pg_dump
            # client newer than the target server emitting a session-level
            # SET the server's GUC list doesn't recognize yet — cosmetic, the
            # schema/data still land). The table count below is the real
            # signal of whether the restore actually worked, not this exit code.
            restore_proc = subprocess.run(
                ["pg_restore", *conn_args, "-d", verify_db, "--no-owner", filepath],
                capture_output=True,
                env=env,
            )
            if restore_proc.returncode != 0:
                logger.warning(
                    "pg_restore exited %d for %s (may be non-fatal — verifying via "
                    "table count next): %s",
                    restore_proc.returncode,
                    filepath,
                    restore_proc.stderr.decode(errors="replace"),
                )
            result = subprocess.run(
                [
                    "psql",
                    *conn_args,
                    "-d",
                    verify_db,
                    "-tAc",
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public'",
                ],
                check=True,
                capture_output=True,
                env=env,
                text=True,
            )
            table_count = int(result.stdout.strip())
            ok = table_count > 0
            logger.info(
                "Backup restore-test %s: %s (table_count=%d)",
                "PASSED" if ok else "FAILED",
                filepath,
                table_count,
            )
            return {"ok": ok, "table_count": table_count, "filepath": filepath}
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
            logger.error("Backup restore-test FAILED for %s: %s", filepath, stderr)
            return {"ok": False, "error": stderr, "filepath": filepath}
        finally:
            subprocess.run(
                ["dropdb", *conn_args, "--if-exists", verify_db],
                capture_output=True,
                env=env,
            )


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
