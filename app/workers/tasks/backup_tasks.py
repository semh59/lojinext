"""
Zamanlanmış veritabanı yedek görevi.
Celery beat tarafından günlük tetiklenir (celery_app.py beat_schedule).
"""

import os

from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(name="infrastructure.db_backup", bind=True, max_retries=2)
def db_backup(self):
    """
    PostgreSQL veritabanını pg_dump ile sıkıştırılmış formatta yedekler.
    Başarı durumunda yedek dosya yolunu döner; hata durumunda 2 kez yeniden dener.
    """
    try:
        from app.infrastructure.database.backup_manager import DatabaseBackupManager

        manager = DatabaseBackupManager()
        filepath = manager.create_backup()
        manager.cleanup_old_backups()

        logger.info("Otomatik DB yedeği alındı: %s", filepath)

        # Opsiyonel: off-site upload (S3/R2)
        _upload_to_offsite(filepath)

        return {"status": "ok", "filepath": filepath}

    except Exception as exc:
        logger.error("DB yedek hatası: %s", exc)
        raise self.retry(exc=exc, countdown=300)  # 5 dakika sonra tekrar dene


def _upload_to_offsite(filepath: str) -> None:
    """
    S3/R2/B2 yükleme — BACKUP_S3_BUCKET env ayarlandıysa çalışır.
    Ayarlanmadıysa sessizce atlanır.
    """
    bucket = os.getenv("BACKUP_S3_BUCKET", "")
    if not bucket:
        return

    try:
        import boto3  # type: ignore[import]

        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=os.getenv("AWS_ENDPOINT_URL"),  # R2/B2 için gerekli
        )
        key = f"backups/{os.path.basename(filepath)}"
        s3.upload_file(filepath, bucket, key)
        logger.info("Yedek S3'e yüklendi: s3://%s/%s", bucket, key)
    except ImportError:
        logger.debug("boto3 kurulu değil — off-site yedek atlandı")
    except Exception as exc:
        logger.warning("Yedek S3'e yüklenemedi (lokal yedek tamam): %s", exc)
