"""Celery task — haftalık ML model retraining (Phase 4.0).

celery_app.py beat schedule'a kayıt edilir:
    "ml-weekly-retrain": {
        "task": "ml.weekly_retrain_all_vehicles",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),  # Pazar 03:00 UTC
    }

Aktif araçların hepsi için tek tek train_for_vehicle çağırır. Eğitim sayfa
yüklendiğinde değil, **boş trafik saatlerinde** koşar.
"""

from __future__ import annotations

import asyncio

from celery import shared_task

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@shared_task(
    name="ml.weekly_retrain_all_vehicles",
    bind=True,
    max_retries=3,
    # n araç × ~30s eğitim = büyük filo için 30+ dakika; global 90s limiti
    # tüm eğitimi keserdi. 1 saat aktif + 5 dakika cooldown.
    soft_time_limit=3600,
    time_limit=3900,
)
def weekly_retrain_all_vehicles(self) -> dict:
    """Filo geneli haftalık model yenileme.

    Tüm aktif araçları DB'den çeker, her biri için Trainer.train_for_vehicle
    çağırır. Hata olan araç: log + skip (tek araç başarısı diğerlerini bozmaz).

    Returns:
        {total, success, failed, skipped, durations}
    """
    return asyncio.run(_run_async())


async def _run_async() -> dict:
    from app.core.ml.training.trainer import Trainer
    from app.database.unit_of_work import UnitOfWork

    trainer = Trainer()
    results = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    async with UnitOfWork() as uow:
        from sqlalchemy import text

        rows = (
            (
                await uow.session.execute(
                    text(
                        "SELECT id FROM araclar WHERE aktif = TRUE AND is_deleted = FALSE"
                    )
                )
            )
            .mappings()
            .all()
        )
        arac_ids = [int(r["id"]) for r in rows]

    results["total"] = len(arac_ids)
    logger.info("Weekly retrain start: %d aracs", results["total"])

    for arac_id in arac_ids:
        try:
            r = await trainer.train_for_vehicle(arac_id)
            if r.get("success"):
                results["success"] += 1
            elif "Yetersiz veri" in str(r.get("error", "")):
                results["skipped"] += 1
            else:
                results["failed"] += 1
                logger.warning(
                    "Weekly retrain failed for arac %s: %s",
                    arac_id,
                    r.get("error"),
                )
        except Exception as exc:
            results["failed"] += 1
            logger.exception("Weekly retrain exception (arac %s): %s", arac_id, exc)

    logger.info("Weekly retrain done: %s", results)
    return results
