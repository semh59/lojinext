"""
TIR Yakıt Takip Sistemi - Sefer Okuma Servisi
Command-Query Separation (CQS) prensibi gereği sadece okuma işlemlerini yönetir.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from app.core.entities.models import Sefer
from app.core.services.security_service import SecurityService
from app.database.models import Kullanici
from app.database.repositories.sefer_repo import SeferRepository, get_sefer_repo
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from app.schemas.sefer import SeferResponse

logger = get_logger(__name__)


class SeferReadService:
    """
    Sefer okuma işlemleri (Read-Only).
    """

    def __init__(self, repo: Optional[SeferRepository] = None):
        self.repo = repo or get_sefer_repo()

    async def get_by_id(
        self, sefer_id: int, current_user: Optional[Kullanici] = None
    ) -> Optional[Sefer]:
        """ID ile sefer getir (İzolasyon korumalı)"""
        row = await self.repo.get_by_id_with_details(sefer_id)
        if not row:
            return None

        sefer = Sefer.model_validate(row)

        # Ownership check
        if current_user:
            SecurityService.verify_ownership(current_user, sefer.sofor_id)

        return sefer

    async def get_sefer_by_id(
        self, sefer_id: int, current_user: Optional[Kullanici] = None
    ) -> Optional[Dict[str, Any]]:
        """Legacy support for Dict return (İzolasyon korumalı)"""
        sefer = await self.get_by_id(sefer_id, current_user)
        return sefer.model_dump() if sefer else None

    async def get_by_vehicle(self, arac_id: int, limit: int = 50) -> List[Sefer]:
        """Araç sefer geçmişini getir"""
        records = await self.repo.get_all(arac_id=arac_id, limit=limit)
        return [Sefer.model_validate(dict(r)) for r in records]

    async def get_all_paged(
        self,
        current_user: Optional[Kullanici] = None,
        skip: int = 0,
        limit: int = 100,
        aktif_only: bool = True,
        **filters: Any,
    ) -> Dict[str, Any]:
        """
        Sayfalı ve filtreli sefer listesi (Güvenli Katman).
        Kullanıcı yetkisine göre veri izolasyonu (Isolation) uygular.
        """
        # Repo katmanı zaten MAX_LIMIT'te kesiyor; servis cap'ini ona hizala ki
        # API gerçekte uygulanmayan (5005) bir limiti ima etmesin (API-003).
        limit = min(max(1, limit), SeferRepository.MAX_LIMIT)
        skip = max(0, skip)

        if current_user:
            filters = SecurityService.apply_isolation(current_user, filters)

        # Normalize Turkish or mixed-case durum filter values to the English
        # canonical form stored in the DB ('Planned'/'Completed'/'Cancelled').
        if filters.get("durum"):
            from app.core.utils.sefer_status import normalize_sefer_status

            normalized_durum = normalize_sefer_status(str(filters["durum"]))
            if normalized_durum:
                filters["durum"] = normalized_durum

        # Total count for metadata
        total = await self.repo.count_all(
            include_inactive=not aktif_only, filters=filters
        )

        records = await self.repo.get_all(
            offset=skip, limit=limit, include_inactive=not aktif_only, filters=filters
        )

        results: List[SeferResponse] = []
        for r in records:
            try:
                # Ensure we handle the dict conversion
                data = dict(r) if not isinstance(r, dict) else r
                results.append(SeferResponse.model_validate(data))
            except Exception as e:
                logger.error(f"Sefer validasyon hatasi (ID {r.get('id')}): {e}")
                continue

        return {
            "items": results,
            "meta": {"total": total, "skip": skip, "limit": limit},
        }

    async def get_all_trips(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sofor_id: Optional[int] = None,
        arac_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[SeferResponse]:
        """Filtreli sefer listesi (Legacy support, redirected to paged)"""
        # Note: This returns List[Sefer], but get_all_paged returns Dict.
        # We need to adapt it.
        paged_result = await self.get_all_paged(
            limit=limit,
            arac_id=arac_id,
            sofor_id=sofor_id,
            baslangic_tarih=start_date,
            bitis_tarih=end_date,
            durum=status,
        )

        return paged_result["items"]

    async def get_trip_stats(
        self,
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
        self,
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

    async def get_timeline(self, sefer_id: int) -> List[Dict[str, Any]]:
        async with UnitOfWork() as uow:
            return await uow.audit_repo.get_sefer_timeline(sefer_id)
