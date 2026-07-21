"""Use-case: `.ics` takvim dışa aktarımı için bakım+araç kaydı okuma.

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/admin_maintenance_routes.py::download_ics``
daha önce ``UnitOfWork`` açıp ``select(AracBakim)``/``select(Arac)``
sorgularını route içinde doğrudan çalıştırıyordu. Mekanik taşıma,
davranış değişikliği yok.
"""

from typing import Optional, Tuple

from sqlalchemy import select

from app.database.unit_of_work import UnitOfWork
from v2.modules.fleet.infrastructure.models import Arac, AracBakim


async def get_maintenance_ics_data(
    bakim_id: int,
) -> Optional[Tuple[AracBakim, Optional[Arac]]]:
    """``(bakim, arac)`` çiftini döner; bakım kaydı yoksa ``None``."""
    async with UnitOfWork() as uow:
        bakim_row = (
            await uow.session.execute(select(AracBakim).where(AracBakim.id == bakim_id))
        ).scalar_one_or_none()
        if bakim_row is None:
            return None
        arac_row: Optional[Arac] = None
        if bakim_row.arac_id is not None:
            arac_row = (
                await uow.session.execute(
                    select(Arac).where(Arac.id == bakim_row.arac_id)
                )
            ).scalar_one_or_none()
        return bakim_row, arac_row
