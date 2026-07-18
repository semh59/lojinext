"""Sefer istatistik/performans agregasyonları.

``analytics_executive``'in ``get_trip_stats``/``get_fuel_performance_analytics``
route'ları bu iki fonksiyonu ``public.py`` üzerinden çağırır — veri mantığı
``seferler`` tablosunu sahiplenen trip'te kalır (task dosyasının kendi
bağlaşıklık karnesindeki "analytics_executive→trip 2" yönüyle tutarlı; bkz.
CLAUDE.md).
"""

from datetime import date
from typing import Any, Dict, Optional

from app.database.unit_of_work import UnitOfWork


async def get_trip_stats(
    durum: Optional[str] = None,
    baslangic_tarih: Optional[date] = None,
    bitis_tarih: Optional[date] = None,
) -> Dict[str, Any]:
    async with UnitOfWork() as uow:
        return await uow.sefer_repo.get_trip_stats(
            durum=durum,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
        )


async def get_fuel_performance_analytics(
    durum: Optional[str] = None,
    baslangic_tarih: Optional[date] = None,
    bitis_tarih: Optional[date] = None,
    arac_id: Optional[int] = None,
    sofor_id: Optional[int] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    async with UnitOfWork() as uow:
        return await uow.sefer_repo.get_fuel_performance_analytics(
            durum=durum,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            search=search,
        )
