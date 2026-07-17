"""Use-case: tahmine dayalı bakım (Feature D) sorguları.

``api/admin_maintenance_routes.py``'nin `/predictions` ve
`/predictions/{arac_id}` handler'ları eskiden ``MaintenancePredictor``'ı
doğrudan çağırıyordu (modülün diğer route'larının hepsi application/
katmanından geçerken bu 2 endpoint istisnaydı — 2026-07-17 dedektif
denetimi bulgusu, bkz. TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md
madde 1). Cache/audit orkestrasyonu route'ta kalır (diğer route'larla aynı
desen); yalnız ``MaintenancePredictor``'a erişim buradan geçer.
"""

from typing import List, Optional

from v2.modules.fleet.application.maintenance_prediction import (
    MaintenancePredictor,
    Prediction,
)


async def get_all_maintenance_predictions() -> List[Prediction]:
    """Tüm aktif araçlar için PERIYODIK bakım tahmini."""
    return await MaintenancePredictor().predict_all()


async def get_maintenance_prediction_for_vehicle(arac_id: int) -> Optional[Prediction]:
    """Tek araç için PERIYODIK bakım tahmini; araç yoksa None."""
    return await MaintenancePredictor().predict_for_arac(arac_id)


__all__ = ["get_all_maintenance_predictions", "get_maintenance_prediction_for_vehicle"]
