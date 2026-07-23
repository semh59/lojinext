"""Trip facade — sınıf istisnası (ARCH-006, bkz. CLAUDE.md).

Facade for Trip operations — the single entry point endpoints depend on.
Internally CQRS-split use-case'leri (read/write/analysis) çağırır; facade
bunları tek cohesive bir interface arkasında toplar ve endpoint'lerin
bağımlı olduğu TEK yerdir (hiçbir endpoint alt-fonksiyonları doğrudan import
etmez — doğrulandı). Bu kasıtlı ve load-bearing, gereksiz sarmalama değil
(ARCH-006): kaldırılsaydı her endpoint 5-6 use-case fonksiyonu inject edip
read/write/analysis ayrımını yeniden türetmek zorunda kalırdı. Yeni trip
operasyonları buradan akmalı, gerçek mantık ilgili use-case dosyasına
gitmeli.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from v2.modules.auth_rbac.public import Kullanici
from v2.modules.platform_infra.public import (
    EventBus,
    UOWDep,
    get_event_bus,
    get_logger,
)
from v2.modules.trip.application import list_trips, onay
from v2.modules.trip.application.add_trip import add_sefer as _add_sefer
from v2.modules.trip.application.bulk_add_trips import bulk_add_sefer as _bulk_add_sefer
from v2.modules.trip.application.bulk_trip_ops import (
    bulk_cancel as _bulk_cancel,
)
from v2.modules.trip.application.bulk_trip_ops import (
    bulk_delete as _bulk_delete,
)
from v2.modules.trip.application.bulk_trip_ops import (
    bulk_update_status as _bulk_update_status,
)
from v2.modules.trip.application.delete_trip import delete_sefer as _delete_sefer
from v2.modules.trip.application.reconcile_costs import reconcile_costs as _reconcile
from v2.modules.trip.application.return_trip import create_return_trip as _create_return
from v2.modules.trip.application.update_trip import update_sefer as _update_sefer
from v2.modules.trip.domain.entities import Sefer
from v2.modules.trip.infrastructure.repository import SeferRepository, get_sefer_repo
from v2.modules.trip.schemas import SeferCreate, SeferUpdate

logger = get_logger(__name__)


class SeferService:
    """Facade for Trip operations — the single entry point endpoints depend on."""

    def __init__(
        self,
        repo: Optional[SeferRepository] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.repo = repo or get_sefer_repo()
        self.event_bus = event_bus or get_event_bus()

    # --- READ OPERATIONS ---

    async def get_by_id(
        self, sefer_id: int, current_user: Optional[Kullanici] = None
    ) -> Optional[Sefer]:
        """Retrieves a trip by ID."""
        return await list_trips.get_by_id(sefer_id, current_user, repo=self.repo)

    async def get_sefer_by_id(
        self, sefer_id: int, current_user: Optional[Kullanici] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves trip details by ID."""
        return await list_trips.get_sefer_by_id(sefer_id, current_user, repo=self.repo)

    async def get_by_vehicle(self, arac_id: int, limit: int = 50) -> List[Sefer]:
        """Retrieves trips associated with a specific vehicle."""
        return await list_trips.get_by_vehicle(arac_id, limit, repo=self.repo)

    async def get_all_paged(
        self,
        current_user: Optional[Kullanici] = None,
        skip: int = 0,
        limit: int = 100,
        aktif_only: bool = True,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Retrieves paged trips with optional filtering."""
        return await list_trips.get_all_paged(
            current_user, skip, limit, aktif_only, repo=self.repo, **filters
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
        return await list_trips.get_all_trips(
            start_date, end_date, sofor_id, arac_id, status, limit, repo=self.repo
        )

    async def get_trip_stats(
        self,
        durum: Optional[str] = None,
        baslangic_tarih: Optional[date] = None,
        bitis_tarih: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Retrieves aggregate trip statistics."""
        from v2.modules.trip.application.trip_stats import get_trip_stats

        return await get_trip_stats(
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
        from v2.modules.trip.application.trip_stats import (
            get_fuel_performance_analytics,
        )

        return await get_fuel_performance_analytics(
            durum=durum,
            baslangic_tarih=baslangic_tarih,
            bitis_tarih=bitis_tarih,
            arac_id=arac_id,
            sofor_id=sofor_id,
            search=search,
        )

    async def get_timeline(self, sefer_id: int) -> List[Dict[str, Any]]:
        """Retrieves the event timeline for a trip."""
        return await list_trips.get_timeline(sefer_id)

    # --- WRITE OPERATIONS ---

    async def add_sefer(self, data: SeferCreate, user_id: Optional[int] = None) -> int:
        """Creates a new trip record."""
        return await _add_sefer(data, user_id)

    async def update_sefer(
        self, sefer_id: int, data: SeferUpdate, user_id: Optional[int] = None
    ) -> bool:
        """Updates an existing trip record."""
        return await _update_sefer(sefer_id, data, user_id)

    async def delete_sefer(self, sefer_id: int) -> bool:
        """Soft-deletes a trip record."""
        return await _delete_sefer(sefer_id)

    async def bulk_add_sefer(self, sefer_list: List[SeferCreate]) -> int:
        """Creates multiple trip records in bulk."""
        return await _bulk_add_sefer(sefer_list)

    async def create_return_trip(
        self, sefer_id: int, user_id: Optional[int] = None
    ) -> int:
        """Generates a return trip based on an existing trip."""
        return await _create_return(sefer_id, user_id)

    async def bulk_update_status(
        self, sefer_ids: List[int], new_status: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Updates the status of multiple trips at once."""
        return await _bulk_update_status(sefer_ids, new_status, user_id)

    async def bulk_cancel(
        self, sefer_ids: List[int], iptal_nedeni: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Cancels multiple trips with a reason."""
        return await _bulk_cancel(sefer_ids, iptal_nedeni, user_id)

    async def bulk_delete(self, sefer_ids: List[int]) -> Dict[str, Any]:
        """Soft-deletes multiple trips in bulk."""
        return await _bulk_delete(sefer_ids)

    # --- ANALYSIS OPERATIONS ---

    async def reconcile_costs(self, sefer_id: int) -> Dict[str, Any]:
        """Analyzes and reconciles costs for a trip."""
        return await _reconcile(sefer_id)

    async def set_onay_durumu(
        self,
        sefer_id: int,
        yeni_durum: str,
        onay_notu: Optional[str] = None,
        onaylayan_id: Optional[int] = None,
    ) -> Optional[Any]:
        """Sefer onay durumunu günceller (beklemede → onaylandi / reddedildi)."""
        return await onay.set_onay_durumu(
            sefer_id, yeni_durum, onay_notu, onaylayan_id, repo=self.repo
        )

    async def get_by_onay_durumu(
        self, onay_durumu: str, skip: int = 0, limit: int = 50
    ) -> List[Any]:
        """Onay durumuna göre seferler."""
        return await onay.get_by_onay_durumu(onay_durumu, skip, limit, repo=self.repo)


def get_sefer_service() -> SeferService:
    """Dependency Injection provider for SeferService."""
    from v2.modules.platform_infra.public import get_container

    return get_container().sefer_service


async def get_sefer_service_for_request(uow: UOWDep) -> SeferService:
    """Per-request SeferService factory (moved from app/api/deps.py, Kalem 3
    commit 3) — NOT the same thing as ``get_sefer_service()`` above.

    That one is a no-arg getter backed by ``container.py``'s app-lifetime
    singleton (UoW-less, stateless-service style). This one builds a fresh
    ``SeferService`` from the per-request ``UnitOfWork`` injected via
    ``UOWDep`` (transaction-scoped, commits/rolls back with the request
    lifecycle) — the "two-layered DI architecture" documented in the old
    ``app/api/deps.py`` docstring. Endpoints that need transaction-scoped
    behavior depend on this one; container-lifetime callers use the other.
    """
    return SeferService(repo=uow.sefer_repo)
