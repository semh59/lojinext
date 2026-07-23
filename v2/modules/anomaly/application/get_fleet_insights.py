"""Use-case: filo analiz dashboard'u (maliyet kaçağı + bakım adayları).

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/anomaly_routes.py::get_fleet_insights``
`application/` katmanını atlayıp doğrudan ``UnitOfWork`` açıyordu. Mekanik
taşıma, davranış değişikliği yok.

NOT: bu use-case ``sefer_repo``/``arac_repo``'yu (trip/fleet modülleri)
okuyor — anomaly'nin `anomalies`/`fuel_investigations` tablolarıyla ilgisi
yok, muhtemelen tarihsel bir yanlış-yerleştirme (bkz. dedektif denetim
notu). Modül taşıma kapsamı dışında bırakıldı, yalnız B.1 katman ihlali
düzeltildi — endpoint yeri/sahipliği ayrı bir karar gerektirir.
"""

from typing import Any, Dict

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


async def get_fleet_insights(days: int) -> Dict[str, Any]:
    async with UnitOfWork() as uow:
        leakage = await uow.sefer_repo.get_cost_leakage_stats(days=days)
        maintenance = await uow.arac_repo.get_maintenance_candidates()

        return {
            "status": "success",
            "data": {"leakage": leakage, "maintenance": maintenance},
        }
