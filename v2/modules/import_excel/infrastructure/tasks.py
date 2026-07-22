"""Celery task: OCR servisine belge gönderir, sonucu DB'ye yazar."""

import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.metrics import telegram_belge_ocr_total
from v2.modules.platform_infra.monitoring.external_api_probe import get_monitored_client
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.public import SeferBelge

logger = logging.getLogger(__name__)


@celery_app.task(
    name="ocr.process_belge",
    bind=True,
    max_retries=3,
    acks_late=True,
    default_retry_delay=30,
)
def process_belge_ocr(self, belge_id: int) -> dict:
    """
    1. belge_id ile SeferBelge kaydını oku
    2. OCR servisine fotoğrafı gönder
    3. Sonucu (ocr_ham, ocr_veri) DB'ye yaz
    """

    async def _mark_hata(bid: int) -> None:
        """Write ocr_durumu='hata' in a separate transaction (survives retry rollback)."""
        async with UnitOfWork() as err_uow:
            r2 = await err_uow.session.execute(
                select(SeferBelge).where(SeferBelge.id == bid)
            )
            b2 = r2.scalar_one_or_none()
            if b2 is not None:
                b2.ocr_durumu = "hata"
                await err_uow.commit()

    async def _run() -> dict:
        async with UnitOfWork() as uow:
            stmt = select(SeferBelge).where(SeferBelge.id == belge_id)
            result = await uow.session.execute(stmt)
            belge: SeferBelge | None = result.scalar_one_or_none()
            if belge is None:
                logger.warning("SeferBelge %s bulunamadı", belge_id)
                return {"ok": False, "error": "not_found"}

            try:
                with open(belge.dosya_yolu, "rb") as f:
                    image_bytes = f.read()
            except OSError as exc:
                await _mark_hata(belge_id)
                raise self.retry(exc=exc)

            ocr_headers = {}
            if settings.OCR_SERVICE_API_KEY:
                ocr_headers["Authorization"] = f"Bearer {settings.OCR_SERVICE_API_KEY}"
            try:
                async with get_monitored_client(timeout=90) as client:
                    resp = await client.post(
                        f"{settings.OCR_SERVICE_URL}/ocr/process",
                        files={
                            "file": (f"belge_{belge_id}.jpg", image_bytes, "image/jpeg")
                        },
                        data={"belge_tipi": belge.belge_tipi},
                        headers=ocr_headers,
                    )
                resp.raise_for_status()
                ocr_result = resp.json()
            except Exception as exc:
                logger.error("OCR servisi hatası (belge %s): %s", belge_id, exc)
                await _mark_hata(belge_id)
                telegram_belge_ocr_total.labels(sonuc="hata").inc()
                raise self.retry(exc=exc)

            belge.ocr_ham = ocr_result.get("ham_metin")
            belge.ocr_veri = ocr_result.get("yapilandirilmis")
            belge.ocr_durumu = "islendi"
            telegram_belge_ocr_total.labels(sonuc="islendi").inc()
            logger.info("Belge %s OCR tamamlandı: %s", belge_id, belge.ocr_veri)
            return {"ok": True, "belge_id": belge_id}

    return asyncio.run(_run())
