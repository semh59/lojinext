"""Use-cases: create maintenance / breakdown records."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.database.models import AracBakim, BakimTipi
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.fleet.application.maintenance_cache import invalidate_predictions_cache

logger = get_logger(__name__)


async def create_maintenance_record(
    arac_id: int,
    bakim_tipi: BakimTipi,
    km_bilgisi: int,
    bakim_tarihi: datetime,
    maliyet: float = 0.0,
    detaylar: str = "",
) -> AracBakim:
    """Create a new maintenance record for a vehicle."""
    async with UnitOfWork() as uow:
        # Verify vehicle exists
        arac = await uow.arac_repo.get_by_id(arac_id)
        if not arac:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Araç bulunamadı: {arac_id}",
            )

        bakim = AracBakim(
            arac_id=arac_id,
            bakim_tipi=bakim_tipi,
            km_bilgisi=km_bilgisi,
            bakim_tarihi=bakim_tarihi,
            maliyet=maliyet,
            detaylar=detaylar,
            tamamlandi=False,
        )

        created_bakim = await uow.maintenance_repo.add(bakim)
        await uow.commit()
        logger.info(
            f"Maintenance record created for vehicle {arac_id}, Type: {bakim_tipi}"
        )
    # D.2 — yeni bakım eklendi, tahmin cache'i geçersiz
    await invalidate_predictions_cache()
    return created_bakim


async def create_breakdown(
    *,
    bakim_tipi: BakimTipi,
    arac_id: Optional[int] = None,
    dorse_id: Optional[int] = None,
    km_bilgisi: int = 0,
    detaylar: str = "",
) -> AracBakim:
    """Açık arıza kaydı — araç VEYA dorse (tam biri). 404 yoksa."""
    if (arac_id is None) == (dorse_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="arac_id veya dorse_id'den tam biri verilmeli",
        )
    async with UnitOfWork() as uow:
        if arac_id is not None:
            if not await uow.arac_repo.get_by_id(arac_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Araç bulunamadı: {arac_id}",
                )
        else:
            if not await uow.dorse_repo.get_by_id(dorse_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Dorse bulunamadı: {dorse_id}",
                )
        bakim = AracBakim(
            arac_id=arac_id,
            dorse_id=dorse_id,
            bakim_tipi=bakim_tipi,
            km_bilgisi=km_bilgisi,
            bakim_tarihi=datetime.now(timezone.utc),
            detaylar=detaylar,
            tamamlandi=False,
        )
        created = await uow.maintenance_repo.add(bakim)
        await uow.commit()
    await invalidate_predictions_cache()
    return created
