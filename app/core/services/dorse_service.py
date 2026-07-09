"""
LojiNext AI - Dorse Service
Trailer business logic and management.

TYPE: PER-REQUEST
SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
DEPENDS_ON: UoW.dorse_repo
CREATED_BY: app/api/deps.py::deps.get_dorse_service()
"""

import asyncio
from typing import Any, Dict, List, Optional

from app.database.repositories.dorse_repo import DorseRepository
from app.infrastructure.events.event_bus import EventBus
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DorseService:
    """Trailer business logic service."""

    def __init__(self, repo: DorseRepository, event_bus: EventBus):
        self.repo = repo
        self.event_bus = event_bus
        self._lock = (
            asyncio.Lock()
        )  # process-local; does not protect against multi-worker races

    async def get_by_id(self, dorse_id: int) -> Optional[Dict[str, Any]]:
        """Get trailer by ID."""
        return await self.repo.get_by_id(dorse_id)

    async def get_all(self, **kwargs) -> List[Dict[str, Any]]:
        """Get all trailers with optional filters."""
        return await self.repo.get_all(**kwargs)

    async def get_all_paged(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str = None,
        aktif_only: bool = True,
        marka: Optional[str] = None,
        model: Optional[str] = None,
        min_yil: Optional[int] = None,
        max_yil: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get trailers with pagination, search and filters.

        AracService.get_all_paged ile aynı desen (2026-07-09 tasarım
        denetimi bulgusu): frontend'in "Detaylı Filtre" paneli (marka/
        model/min_yil/max_yil) + dorseService.getAll bu parametreleri
        zaten gönderiyordu, backend hiçbirini kabul etmiyordu — filtre
        sessizce hiçbir şey yapmıyordu. `yil_ge`/`yil_le`, BaseRepository.
        get_all'ın genel range-filter desteğidir (repo katmanında ek kod
        gerektirmez).
        """
        filters: Dict[str, Any] = {}
        if marka:
            filters["marka"] = marka
        if model:
            filters["model"] = model
        if min_yil is not None:
            filters["yil_ge"] = min_yil
        if max_yil is not None:
            filters["yil_le"] = max_yil

        return await self.repo.get_paged(
            skip=skip,
            limit=limit,
            search=search,
            aktif_only=aktif_only,
            filters=filters,
        )

    async def create(self, **data) -> int:
        """Create a new trailer record (Duplicate Check + Reactivation).

        AracService.create_arac ile aynı desen (2026-07-09 canlı-hazırlık
        denetimi bulgusu): eskiden buradan doğrudan `repo.create()`'e
        düşülüyordu — plaka.unique constraint aktif/pasif ayrımı yapmadığı
        için (1) aynı plakalı aktif bir dorse eklenmeye çalışılırsa
        IntegrityError endpoint'te özel yakalanmıyordu (genel 500), (2) pasif
        bir dorsenin plakası asla yeniden kullanılamıyordu (varsayılan liste
        aktif_only=True olduğu için operatör pasif kaydı görüp elle reaktive
        de edemiyordu) — kalıcı çıkmaz sokak.
        """
        plaka = data.get("plaka")
        async with self._lock:  # Race Condition Guard (TOCTOU)
            existing = await self.repo.get_by_plate(plaka, for_update=True)
            if existing:
                if existing.aktif is False:
                    logger.info(f"Re-activating passive trailer: {plaka}")
                    update_data = {k: v for k, v in data.items() if k != "plaka"}
                    update_data["aktif"] = True
                    await self.repo.update(existing.id, **update_data)
                    return existing.id
                raise ValueError(f"A trailer with this plate already exists: {plaka}")

            return await self.repo.create(**data)

    async def update(self, dorse_id: int, **data) -> bool:
        """Update trailer record."""
        return await self.repo.update(dorse_id, **data)

    async def delete(self, dorse_id: int) -> bool:
        """Delete trailer record (Internal repo handles soft/hard)."""
        return await self.repo.delete(dorse_id)

    async def export_all_trailers(self) -> bytes:
        """Tüm dorseleri Excel olarak dışa aktar."""
        dorseler = await self.repo.get_all(limit=10000)
        data = [
            {
                "plaka": d.get("plaka") if isinstance(d, dict) else d.plaka,
                "marka": d.get("marka") if isinstance(d, dict) else d.marka,
                "model": d.get("model") if isinstance(d, dict) else d.model,
                "yil": d.get("yil") if isinstance(d, dict) else d.yil,
                "tipi": d.get("tipi") if isinstance(d, dict) else d.tipi,
                "bos_agirlik_kg": d.get("bos_agirlik_kg")
                if isinstance(d, dict)
                else d.bos_agirlik_kg,
                "lastik_sayisi": d.get("lastik_sayisi")
                if isinstance(d, dict)
                else d.lastik_sayisi,
                "aktif": d.get("aktif") if isinstance(d, dict) else d.aktif,
            }
            for d in dorseler
        ]

        from .excel_service import ExcelService

        return await ExcelService.export_data(data, type="dorse_listesi")

    async def get_template(self) -> bytes:
        """Dorse yükleme şablonunu getir."""
        from .excel_service import ExcelService

        return await ExcelService.generate_template("dorse")

    async def import_trailers(self, content: bytes) -> Dict[str, Any]:
        """Excel'den dorse aktarımı."""
        from .excel_service import ExcelService

        parsed_data = await ExcelService.parse_dorse_excel(content)

        count = 0
        errors = []

        for item in parsed_data:
            try:
                # Plaka bazlı mükerrer kontrolü repo içinde create metodunda var
                await self.create(**item)
                count += 1
            except Exception as e:
                errors.append({"plaka": item.get("plaka"), "error": str(e)})

        return {"imported": count, "errors": errors}
