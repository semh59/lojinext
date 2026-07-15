"""Use-case: yakıt fişi belgelerinin arşiv listesi.

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): ``api/fuel_routes.py::list_fuel_documents`` `application/`
katmanını atlayıp doğrudan ``db.execute(text(...))`` çalıştırıyordu. Mekanik
taşıma, davranış değişikliği yok.
"""

from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_fuel_documents(db: AsyncSession, limit: int) -> List[Dict[str, Any]]:
    """Yakıt fişi belgelerinin arşiv listesi (en yeni → eski)."""
    rows = (
        (
            await db.execute(
                text(
                    "SELECT id, belge_tipi, ocr_durumu, sofor_id, sefer_id, "
                    "created_at FROM sefer_belgeler WHERE belge_tipi = 'yakit_fisi' "
                    "ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]
