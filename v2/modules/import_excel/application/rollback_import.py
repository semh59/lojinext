"""``execute_import``'un ürettiği ``inserted_ids`` üzerinden geri alma."""

from fastapi import HTTPException
from sqlalchemy import text

from app.infrastructure.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def rollback_import(job_id: int, user_id: int) -> bool:
    """
    Reverts a previous import by cascading deletions on the tracked IDs.
    """
    async with UnitOfWork() as uow:
        job = await uow.import_repo.get_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Aktarım geçmişi bulunamadı.")

        if job.durum == "ROLLED_BACK":
            raise HTTPException(status_code=400, detail="Bu aktarım zaten geri alındı.")

        if not job.islem_haritasi or "inserted_ids" not in job.islem_haritasi:
            raise HTTPException(
                status_code=400, detail="Geri alınacak veri haritası yok."
            )

        inserted_ids = job.islem_haritasi["inserted_ids"]

        if not inserted_ids:
            return True  # Nothing to delete

        try:
            if job.aktarim_tipi == "arac":
                stmt = text("DELETE FROM araclar WHERE id = ANY(:ids)")
                await uow.session.execute(stmt, {"ids": inserted_ids})
            elif job.aktarim_tipi == "surucu":
                stmt = text("DELETE FROM soforler WHERE id = ANY(:ids)")
                await uow.session.execute(stmt, {"ids": inserted_ids})
            elif job.aktarim_tipi == "sefer":
                stmt = text("DELETE FROM seferler WHERE id = ANY(:ids)")
                await uow.session.execute(stmt, {"ids": inserted_ids})
            elif job.aktarim_tipi == "yakit":
                stmt = text("DELETE FROM yakit_alimlari WHERE id = ANY(:ids)")
                await uow.session.execute(stmt, {"ids": inserted_ids})

            await uow.import_repo.update_job_status(
                job.id,
                durum="ROLLED_BACK",
                degisiklik_sebebi=f"Geri alındı, yetkili: {user_id}",
            )
            await uow.commit()
            return True
        except Exception as e:
            logger.error(f"Rollback hatası (Job {job_id}): {e}")
            raise HTTPException(
                status_code=500,
                detail="Rollback sırasında kritik veritabanı hatası oluştu.",
            )
