"""Geçmiş import job'larını listeleme use-case'i."""

from typing import Any, Dict, List

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_import_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Geçmişe dönük yükleme loglarını getirir."""
    async with UnitOfWork() as uow:
        jobs = await uow.import_repo.get_recent_jobs(limit=limit)
        return [
            {
                "id": job.id,
                "dosya_adi": job.dosya_adi,
                "aktarim_tipi": job.aktarim_tipi,
                "durum": job.durum,
                "toplam": job.toplam_kayit,
                "basarili": job.basarili_kayit,
                "hatali": job.hatali_kayit,
                "baslama_zamani": job.baslama_zamani,
                "yukleyen_id": job.yukleyen_id,
            }
            for job in jobs
        ]
