"""Operator-facing maintenance endpoints (non-admin namespace).

Breakdown reporting is intentionally open to any active user — reporting that
a vehicle has a fault is an operational fact, not a privileged action. The
more breakdowns/maintenance get logged, the better the maintenance-driven
fuel factor and the maintenance predictions. Admin/scheduled-maintenance
management stays under /admin/maintenance (require_yetki bakim_ekle/ariza_bildir).
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import get_current_active_user
from app.database.models import Kullanici
from v2.modules.fleet.application.create_maintenance_record import create_breakdown
from v2.modules.fleet.infrastructure.models import BakimTipi

router = APIRouter()

# Yalnız "arıza" tipleri — planlı PERIYODIK bakım buradan girilmez.
_BREAKDOWN_TYPES = {"ARIZA", "ACIL"}


class BreakdownReport(BaseModel):
    arac_id: Optional[int] = Field(None, description="Arızalı araç id")
    dorse_id: Optional[int] = Field(None, description="Arızalı dorse id")
    bakim_tipi: str = Field("ARIZA", description="ARIZA | ACIL")
    detaylar: str = Field("", max_length=2000, description="Arıza açıklaması")
    km_bilgisi: int = Field(0, ge=0, description="Bilinmiyorsa 0")

    @field_validator("bakim_tipi")
    @classmethod
    def _only_breakdown(cls, v: str) -> str:
        if v not in _BREAKDOWN_TYPES:
            raise ValueError("bakim_tipi yalnız ARIZA veya ACIL olabilir")
        return v

    @model_validator(mode="after")
    def _one_target(self) -> "BreakdownReport":
        if (self.arac_id is None) == (self.dorse_id is None):
            raise ValueError("arac_id veya dorse_id'den tam biri verilmeli")
        return self


@router.post("/report-breakdown", status_code=201)
async def report_breakdown(
    body: BreakdownReport,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> dict:
    """Arıza bildir — herhangi bir aktif kullanıcı (operatör/sürücü).

    Araç VEYA dorse için açık (tamamlanmamış) ARIZA/ACIL kaydı oluşturur.
    404 araç/dorse yoksa.
    """
    rec = await create_breakdown(
        arac_id=body.arac_id,
        dorse_id=body.dorse_id,
        bakim_tipi=BakimTipi(body.bakim_tipi),
        km_bilgisi=body.km_bilgisi,
        detaylar=body.detaylar,
    )
    return {
        "id": rec.id,
        "arac_id": rec.arac_id,
        "dorse_id": rec.dorse_id,
        "bakim_tipi": rec.bakim_tipi,
        "tamamlandi": rec.tamamlandi,
    }
