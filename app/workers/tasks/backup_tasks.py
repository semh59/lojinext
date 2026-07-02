"""
Zamanlanmış veritabanı yedek görevi.
Celery beat tarafından günlük tetiklenir (celery_app.py beat_schedule).
"""

import asyncio
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


@celery_app.task(name="infrastructure.db_backup_verify", bind=True, max_retries=1)
def db_backup_verify(self):
    """Tier E madde 27 — en son yedeği throwaway bir DB'ye restore edip
    doğrular (pg_restore + tablo sayımı). Bir yedeğin var olması onun
    gerçekten geri yüklenebilir olduğu anlamına gelmez (bozuk dump, eksik
    extension, sürüm uyumsuzluğu sessizce aylarca fark edilmeyebilir) —
    bu task o boşluğu kapatır. Başarısızlıkta ErrorEvent alarmı tetikler.
    """
    from app.infrastructure.database.backup_manager import DatabaseBackupManager

    manager = DatabaseBackupManager()
    result = manager.verify_backup_restorable()

    if result.get("ok"):
        logger.info(
            "Yedek restore-testi başarılı: %s (table_count=%s)",
            result.get("filepath"),
            result.get("table_count"),
        )
        return result

    logger.error("Yedek restore-testi BAŞARISIZ: %s", result)
    asyncio.run(_alert_restore_failure(result))
    return result


async def _alert_restore_failure(result: dict) -> None:
    try:
        from app.infrastructure.monitoring import aemit
        from app.infrastructure.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        await aemit(
            ErrorEvent(
                layer=ErrorLayer.DB,
                category="backup_restore_verify_failed",
                severity=ErrorSeverity.CRITICAL,
                message=f"DB yedek restore-testi başarısız: {str(result)[:300]}",
            )
        )
    except Exception:
        logger.error("Restore-test alarmı da gönderilemedi", exc_info=True)


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
