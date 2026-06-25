"""Operator-facing maintenance endpoints (non-admin namespace).

Breakdown reporting is intentionally open to any active user — reporting that
a vehicle has a fault is an operational fact, not a privileged action. The
more breakdowns/maintenance get logged, the better the maintenance-driven
fuel factor and the maintenance predictions. Admin/scheduled-maintenance
management stays under /admin/maintenance (require_yetki bakim_ekle/ariza_bildir).
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_current_active_user
from app.core.services.maintenance_service import MaintenanceService
from app.database.models import BakimTipi, Kullanici

router = APIRouter()

# Yalnız "arıza" tipleri — planlı PERIYODIK bakım buradan girilmez.
_BREAKDOWN_TYPES = {"ARIZA", "ACIL"}


class BreakdownReport(BaseModel):
    arac_id: int = Field(..., description="Arızalı araç id")
    bakim_tipi: str = Field("ARIZA", description="ARIZA | ACIL")
    detaylar: str = Field("", max_length=2000, description="Arıza açıklaması")
    km_bilgisi: int = Field(0, ge=0, description="Bilinmiyorsa 0")

    @field_validator("bakim_tipi")
    @classmethod
    def _only_breakdown(cls, v: str) -> str:
        if v not in _BREAKDOWN_TYPES:
            raise ValueError("bakim_tipi yalnız ARIZA veya ACIL olabilir")
        return v


@router.post("/report-breakdown", status_code=201)
async def report_breakdown(
    body: BreakdownReport,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> dict:
    """Arıza bildir — herhangi bir aktif kullanıcı (operatör/sürücü).

    Açık (tamamlanmamış) ARIZA/ACIL kaydı oluşturur. 404 araç yoksa.
    """
    svc = MaintenanceService()
    rec = await svc.create_maintenance_record(
        arac_id=body.arac_id,
        bakim_tipi=BakimTipi(body.bakim_tipi),
        km_bilgisi=body.km_bilgisi,
        bakim_tarihi=datetime.now(timezone.utc),
        detaylar=body.detaylar,
    )
    return {
        "id": rec.id,
        "arac_id": rec.arac_id,
        "bakim_tipi": rec.bakim_tipi,
        "tamamlandi": rec.tamamlandi,
    }
