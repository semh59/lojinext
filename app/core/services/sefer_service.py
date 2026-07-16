"""
LOJINEXT Fuel Tracking System - Trip Service (Facade)
This class is a Facade that delegates requests to specialized sub-services.
Maintained for backward compatibility.

TYPE: PER-REQUEST
SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
DEPENDS_ON: UoW.sefer_repo
CREATED_BY: app/api/deps.py::deps.get_sefer_service()
"""

from datetime import date
from typing import Any, Dict, List, Optional

from app.core.entities.models import Sefer
from app.core.services.sefer_analiz_service import SeferAnalizService

# Import Sub-Services
from app.core.services.sefer_read_service import SeferReadService
from app.core.services.sefer_write_service import SeferWriteService
from app.database.models import Kullanici
from app.database.repositories.sefer_repo import SeferRepository, get_sefer_repo
from app.infrastructure.events.event_bus import EventBus, get_event_bus
from app.infrastructure.logging.logger import get_logger
from app.schemas.sefer import SeferCreate, SeferUpdate

logger = get_logger(__name__)


class SeferService:
    """Facade for Trip operations — the single entry point endpoints depend on.

    Internally CQRS-split into Read / Write / Analysis sub-services; the facade
    composes them behind one cohesive interface and is the *only* place that
    wiring lives (no endpoint imports the sub-services directly — verified). This
    is intentional and load-bearing, not redundant wrapping (ARCH-006): removing
    it would force every endpoint to inject 2-3 services and re-derive the
    read/write/analysis split, increasing coupling. Keep new trip operations
    flowing through here; put the actual logic in the matching sub-service.
    """

    def __init__(
        self,
        repo: Optional[SeferRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.repo = repo or get_sefer_repo()
        self.event_bus = event_bus or get_event_bus()

        # Initialize Sub-Services
        self.read_service = SeferReadService(repo=self.repo)
        self.write_service = SeferWriteService(repo=self.repo, event_bus=self.event_bus)
        self.analiz_service = SeferAnalizService(
            repo=self.repo, event_bus=self.event_bus
        )

    # --- READ OPERATIONS (Delegated to SeferReadService) ---

    async def get_by_id(
        self, sefer_id: int, current_user: Optional[Kullanici] = None
    ) -> Optional[Sefer]:
        """Retrieves a trip by ID."""
        return await self.read_service.get_by_id(sefer_id, current_user)

    async def get_sefer_by_id(
        self, sefer_id: int, current_user: Optional[Kullanici] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves trip details by ID."""
        return await self.read_service.get_sefer_by_id(sefer_id, current_user)

    async def get_by_vehicle(self, arac_id: int, limit: int = 50) -> List[Sefer]:
        """Retrieves trips associated with a specific vehicle."""
        return await self.read_service.get_by_vehicle(arac_id, limit)

    async def get_all_paged(
        self,
        current_user: Optional[Kullanici] = None,
        skip: int = 0,
        limit: int = 100,
        aktif_only: bool = True,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Retrieves paged trips with optional filtering."""
        return await self.read_service.get_all_paged(
            current_user, skip, limit, aktif_only, **filters
        )

    async def get_all_trips(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sofor_id: Optional[int] = None,
        arac_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        """Retrieves all trips based on criteria."""
        return await self.read_service.get_all_trips(
            start_date, end_date, sofor_id, arac_id, status, limit
        )

    async def get_trip_stats(
        self,
        durum: Optional[str] = None,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Retrieves aggregate trip statistics."""
        return await self.read_service.get_trip_stats(
            durum=durum,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
        )

    async def get_fuel_performance_analytics(
        self,
        durum: Optional[str] = None,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
        arac_id: Optional[int] = None,
        sofor_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves deep fuel performance analytics."""
        return await self.read_service.get_fuel_performance_analytics(
            durum=durum,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            search=search,
        )

    async def get_timeline(self, sefer_id: int) -> List[Dict[str, Any]]:
        """Retrieves the event timeline for a trip."""
        return await self.read_service.get_timeline(sefer_id)

    # --- WRITE OPERATIONS (Delegated to SeferWriteService) ---

    async def add_sefer(self, data: SeferCreate, user_id: Optional[int] = None) -> int:
        """Creates a new trip record."""
        return await self.write_service.add_sefer(data, user_id)

    async def update_sefer(
        self, sefer_id: int, data: SeferUpdate, user_id: Optional[int] = None
    ) -> bool:
        """Updates an existing trip record."""
        return await self.write_service.update_sefer(sefer_id, data, user_id)

    async def delete_sefer(self, sefer_id: int) -> bool:
        """Soft-deletes a trip record."""
        return await self.write_service.delete_sefer(sefer_id)

    async def bulk_add_sefer(self, sefer_list: List[SeferCreate]) -> int:
        """Creates multiple trip records in bulk."""
        return await self.write_service.bulk_add_sefer(sefer_list)

    async def create_return_trip(
        self, sefer_id: int, user_id: Optional[int] = None
    ) -> int:
        """Generates a return trip based on an existing trip."""
        return await self.write_service.create_return_trip(sefer_id, user_id)

    async def bulk_update_status(
        self, sefer_ids: List[int], new_status: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Updates the status of multiple trips at once."""
        return await self.write_service.bulk_update_status(
            sefer_ids, new_status, user_id
        )

    async def bulk_cancel(
        self, sefer_ids: List[int], iptal_nedeni: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Cancels multiple trips with a reason."""
        return await self.write_service.bulk_cancel(sefer_ids, iptal_nedeni, user_id)

    async def bulk_delete(self, sefer_ids: List[int]) -> Dict[str, Any]:
        """Soft-deletes multiple trips in bulk."""
        return await self.write_service.bulk_delete(sefer_ids)

    # --- ANALYSIS OPERATIONS (Delegated to SeferAnalizService) ---

    async def reconcile_costs(self, sefer_id: int) -> Dict[str, Any]:
        """Analyzes and reconciles costs for a trip."""
        return await self.analiz_service.reconcile_costs(sefer_id)

    async def set_onay_durumu(
        self,
        sefer_id: int,
        yeni_durum: str,
        onay_notu: Optional[str] = None,
        onaylayan_id: Optional[int] = None,
    ) -> Optional[Any]:
        """Sefer onay durumunu günceller (beklemede → onaylandi / reddedildi)."""
        _VALID_ONAY_DURUMLARI = {"beklemede", "onaylandi", "reddedildi"}
        if yeni_durum not in _VALID_ONAY_DURUMLARI:
            raise ValueError(f"Geçersiz onay durumu: '{yeni_durum}'")

        from app.infrastructure.audit.audit_logger import log_audit_event

        before = await self.read_service.get_sefer_by_id(sefer_id)
        updated = await self.repo.set_onay_durumu(
            sefer_id, yeni_durum, onay_notu, onaylayan_id
        )
        if updated is None:
            return None

        eski_durum = before.get("onay_durumu") if before else None
        logger.info(
            "set_onay_durumu: sefer_id=%s %s→%s by user_id=%s",
            sefer_id,
            eski_durum,
            yeni_durum,
            onaylayan_id,
        )
        await log_audit_event(
            action="sefer_onay_guncelle",
            module="sefer",
            entity_id=str(sefer_id),
            user_id=onaylayan_id,
            details={"eski": eski_durum, "yeni": yeni_durum, "not": onay_notu},
        )
        return await self.read_service.get_sefer_by_id(sefer_id)

    async def get_by_onay_durumu(
        self, onay_durumu: str, skip: int = 0, limit: int = 50
    ) -> List[Any]:
        """Onay durumuna göre seferler."""
        return await self.repo.get_by_onay_durumu(onay_durumu, skip=skip, limit=limit)


def get_sefer_service() -> SeferService:
    """Dependency Injection provider for SeferService."""
    from app.core.container import get_container

    return get_container().sefer_service
