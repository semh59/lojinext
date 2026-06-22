"""
LOJINEXT Fuel Tracking - Fuel Service
Business logic layer: Fuel transactions (English).

TYPE: PER-REQUEST
SCOPE: Transaction-scoped (UnitOfWork ile oluşturulur)
DEPENDS_ON: UoW.yakit_repo
CREATED_BY: app/api/deps.py::deps.get_yakit_service()
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.database.repositories.yakit_repo import YakitRepository

from app.core.entities.models import YakitAlimi, YakitAlimiCreate, YakitUpdate
from app.database.repositories.yakit_repo import get_yakit_repo
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.audit import audit_log
from app.infrastructure.events.event_bus import (
    Event,
    EventBus,
    EventType,
    get_event_bus,
    publishes,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors

logger = get_logger(__name__)


def get_uow() -> UnitOfWork:
    """Backward-compatible UnitOfWork factory."""
    return UnitOfWork()


class YakitService:
    """
    Business logic for fuel transactions.
    Acts as a bridge between UI and DB.
    """

    def __init__(
        self,
        repo: Optional["YakitRepository"] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.repo = repo or get_yakit_repo()
        self.event_bus = event_bus or get_event_bus()

    async def _check_rolling_outlier(
        self, arac_id: int, current_litre: float, current_km: int
    ) -> bool:
        """
        Rolling Outlier Check for Partial Fills (Last 5 Records).
        Examines the average of the last 5 entries instead of single records.
        """
        try:
            async with get_uow() as uow:
                query = """
                    SELECT litre, km_sayac FROM yakit_alimlari
                    WHERE arac_id = :arac_id AND aktif = TRUE
                    ORDER BY km_sayac DESC
                    LIMIT 5
                """
                from sqlalchemy import text

                result = await uow.session.execute(text(query), {"arac_id": arac_id})
                last_5 = result.fetchall()

            if not last_5:
                return False

            litres = [current_litre] + [float(r.litre) for r in last_5]
            kms = [current_km] + [int(r.km_sayac) for r in last_5]

            total_dist = max(kms) - min(kms)
            if len(kms) < 2 or total_dist <= 0:
                return False

            # Rolling Window Logic: the fuel of the earliest record is excluded
            # as it belongs to the period before that odometer reading.
            valid_fuel = sum(litres) - float(last_5[-1].litre)

            if valid_fuel <= 0:
                return False

            rolling_avg = (valid_fuel / total_dist) * 100

            # Smart Thresholds: 18-55 range is considered normal for Heavy Duty Trucks.
            if rolling_avg < 18 or rolling_avg > 55:
                logger.warning(
                    f"Rolling Anomaly ({len(kms)} fills): Vehicle {arac_id}, {rolling_avg:.1f} L/100km (Dist: {total_dist})"  # noqa: E501
                )

                self.event_bus.publish(
                    Event(
                        type=EventType.ANOMALY_DETECTED,
                        data={
                            "arac_id": arac_id,
                            "tip": "rolling_consumption",
                            "deger": rolling_avg,
                            "window_size": len(kms),
                            "total_dist": total_dist,
                        },
                    )
                )
                return True

        except Exception as e:
            logger.error(f"Rolling outlier check error: {e}")

        return False

    @monitor_errors(category="yakit_write", severity="error")
    @publishes(EventType.YAKIT_ADDED)
    async def add_yakit(self, data: YakitAlimiCreate) -> int:
        """Adds a new fuel transaction."""
        try:
            async with UnitOfWork() as uow:
                arac = await uow.arac_repo.get_by_id(data.arac_id)
                if not arac or not arac.get("aktif"):
                    raise ValueError(
                        "Cannot enter fuel for a passive or invalid vehicle."
                    )

                if data.litre <= 0:
                    raise ValueError("Litres must be greater than zero")

                if data.fiyat_tl <= 0:
                    raise ValueError("Price must be greater than zero")

                entry_date = (
                    data.tarih
                    if isinstance(data.tarih, date)
                    else date.fromisoformat(data.tarih)
                )
                if entry_date > date.today():
                    raise ValueError("İleri tarihli yakıt girişine izin verilmez")

                is_duplicate = await uow.yakit_repo.check_duplicate(
                    data.arac_id, entry_date, float(data.litre)
                )
                if is_duplicate:
                    logger.warning(
                        f"Duplicate fuel entry blocked: Vehicle {data.arac_id}, Date {entry_date}, Litre {data.litre}"
                    )
                    raise ValueError(
                        "This fuel record already exists (Duplicate Entry)."
                    )

                last_km = await uow.yakit_repo.get_son_km(data.arac_id)
                if last_km and data.km_sayac < last_km:
                    raise ValueError(
                        f"KM Sayacı düşemez! (Son: {last_km}, Girilen: {data.km_sayac})"
                    )

                if last_km:
                    await self._check_rolling_outlier(
                        data.arac_id, float(data.litre), data.km_sayac
                    )

                yakit_id = await uow.yakit_repo.add(
                    tarih=entry_date,
                    arac_id=data.arac_id,
                    istasyon=data.istasyon,
                    fiyat=float(data.fiyat_tl),
                    litre=float(data.litre),
                    km_sayac=data.km_sayac,
                    fis_no=data.fis_no,
                    depo_durumu=data.depo_durumu or "Unknown",
                    # Verilmezse None geç; repo toplam'ı Decimal'de hesaplar.
                    toplam_tutar=getattr(data, "toplam_tutar", None),
                )

                await uow.commit()
                logger.info(f"Fuel entry added: ID {yakit_id}, Vehicle {data.arac_id}")
                return int(yakit_id)

        except Exception as e:
            logger.error(f"Fuel addition error: {e}", exc_info=True)
            raise

    @monitor_errors(category="yakit_write", severity="error")
    @audit_log("UPDATE", "yakit")
    @publishes(EventType.YAKIT_UPDATED)
    async def update_yakit(self, yakit_id: int, data: YakitUpdate) -> bool:
        """Updates a fuel record (Atomic)."""
        try:
            async with UnitOfWork() as uow:
                current = await uow.yakit_repo.get_by_id(yakit_id, for_update=True)
                if not current:
                    return False

                update_data = data.model_dump(exclude_unset=True)
                if not update_data:
                    return True

                success = await uow.yakit_repo.update_yakit(yakit_id, **update_data)
                if success:
                    await uow.commit()
                    logger.info(f"Fuel record updated: ID {yakit_id}")
                return bool(success)
        except Exception as e:
            logger.error(f"Fuel update error: {e}")
            raise

    @monitor_errors(category="yakit_write", severity="error")
    @publishes(EventType.YAKIT_DELETED)
    async def delete_yakit(
        self, yakit_id: int, deleted_by_id: Optional[int] = None
    ) -> bool:
        """Permanently deletes a fuel record (Hard Delete)."""
        from app.infrastructure.audit.audit_logger import log_audit_event

        try:
            async with UnitOfWork() as uow:
                current = await uow.yakit_repo.get_by_id(yakit_id)
                if not current:
                    return False

                success = await uow.yakit_repo.hard_delete(yakit_id)
                if success:
                    await uow.commit()
                    logger.info(
                        f"Fuel record permanently deleted (Hard Delete): ID {yakit_id}"
                    )
                    await log_audit_event(
                        action="yakit_hard_delete",
                        module="yakit",
                        entity_id=yakit_id,
                        user_id=deleted_by_id,
                        details={
                            "arac_id": current.get("arac_id"),
                            "tarih": str(current.get("tarih")),
                            "litre": str(current.get("litre")),
                            "toplam_tutar": str(current.get("toplam_tutar")),
                        },
                    )
                return bool(success)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Fuel deletion error: {e}")
            raise ValueError("An error occurred while deleting fuel entry.")

    async def add_yakit_alimi(self, **kwargs: Any) -> int:
        """Alias for add_yakit (backward compatibility)."""
        if kwargs:
            try:
                data = YakitAlimiCreate(**kwargs)
                return await self.add_yakit(data)
            except Exception as e:
                logger.error(f"Fuel addition error (alias): {e}")
                raise
        raise ValueError("No data provided")

    async def get_yakit_by_id(self, yakit_id: int) -> Optional[YakitAlimi]:
        """Retrieves fuel transaction details."""
        async with UnitOfWork() as uow:
            record = await uow.yakit_repo.get_by_id(yakit_id)
            if not record:
                return None
            return YakitAlimi.model_validate(dict(record))

    async def get_by_vehicle(self, arac_id: int, limit: int = 50) -> List[YakitAlimi]:
        """Retrieves vehicle fuel history."""
        async with UnitOfWork() as uow:
            result = await uow.yakit_repo.get_all(arac_id=arac_id, limit=limit)
        rows = result.get("items", []) if isinstance(result, dict) else result
        return [YakitAlimi.model_validate(dict(r)) for r in rows]

    async def get_all_paged(
        self, skip: int = 0, limit: int = 100, aktif_only: bool = True, **filters: Any
    ) -> Dict[str, Any]:
        """Returns paged and filtered fuel list."""
        if filters.get("baslangic_tarih") and isinstance(
            filters["baslangic_tarih"], str
        ):
            try:
                filters["baslangic_tarih"] = date.fromisoformat(
                    filters["baslangic_tarih"]
                )
            except ValueError:
                pass

        if filters.get("bitis_tarih") and isinstance(filters["bitis_tarih"], str):
            try:
                filters["bitis_tarih"] = date.fromisoformat(filters["bitis_tarih"])
            except ValueError:
                pass

        async with UnitOfWork() as uow:
            paged_data = await uow.yakit_repo.get_all(
                offset=skip, limit=limit, include_inactive=not aktif_only, **filters
            )

        records = paged_data.get("items", [])
        total_count = paged_data.get("total", 0)

        results = []
        for r in records:
            try:
                results.append(YakitAlimi.model_validate(dict(r)))
            except Exception as e:
                logger.error(f"Fuel validation error (ID {r.get('id')}): {e}")
                continue
        return {"items": results, "total": total_count}

    async def get_all(
        self, limit: int = 100, vehicle_id: Optional[int] = None
    ) -> List[YakitAlimi]:
        """Legacy support for getting all records."""
        result = await self.get_all_paged(limit=limit, arac_id=vehicle_id)
        if isinstance(result, dict):
            return result.get("items", [])
        return result

    async def get_stats(
        self, baslangic_tarih: Optional[date] = None, bitis_tarih: Optional[date] = None
    ) -> Dict:
        """Retrieves general fuel statistics with filter support."""
        if baslangic_tarih is not None or bitis_tarih is not None:
            async with UnitOfWork() as uow:
                return await uow.yakit_repo.get_stats(
                    baslangic_tarih=baslangic_tarih, bitis_tarih=bitis_tarih
                )

        try:
            async with UnitOfWork() as uow:
                dashboard = await uow.analiz_repo.get_dashboard_stats()
            if dashboard:
                return {
                    "toplam_yakit": dashboard.get("toplam_yakit", 0),
                    "aylik_ort": dashboard.get("filo_ortalama", 0),
                    "toplam_tutar": dashboard.get("toplam_tutar", 0),
                    **dashboard,
                }
        except Exception as e:
            logger.warning(f"Dashboard stats fallback failed: {e}")

        async with UnitOfWork() as uow:
            return await uow.yakit_repo.get_stats(
                baslangic_tarih=baslangic_tarih, bitis_tarih=bitis_tarih
            )

    async def get_monthly_summary(self) -> List[Dict]:
        """Retrieves monthly consumption summary."""
        async with UnitOfWork() as uow:
            if hasattr(uow.analiz_repo, "get_monthly_consumption_series"):
                return await uow.analiz_repo.get_monthly_consumption_series()
            return await uow.analiz_repo.get_daily_consumption_series(days=365)

    async def bulk_add_yakit(self, yakit_list: List[YakitAlimiCreate]) -> int:
        """Bulk creates fuel entries (Pre-fetch & Batch Insert)."""
        if not yakit_list:
            return 0
        count = 0
        async with UnitOfWork() as uow:
            try:
                # Son KM'leri tek sorguda topla (araç başına get_son_km = N+1'di).
                # Kaydı olmayan araçlar sözlükte yok → aşağıda .get(id, 0) okunur.
                active_araclar = await uow.arac_repo.get_all(sadece_aktif=True)
                active_arac_ids = {a["id"] for a in active_araclar}
                last_km_cache = await uow.yakit_repo.get_son_km_bulk(
                    list(active_arac_ids)
                )

                today = date.today()
                sorted_list = sorted(yakit_list, key=lambda x: x.tarih)
                items_to_add = []
                for data in sorted_list:
                    if data.arac_id not in active_arac_ids:
                        logger.warning(
                            f"Bulk skip: Vehicle {data.arac_id} is inactive or unknown"
                        )
                        continue
                    if data.litre <= 0:
                        continue
                    if data.fiyat_tl <= 0:
                        logger.warning(f"Bulk skip: Vehicle {data.arac_id} price <= 0")
                        continue
                    entry_date = (
                        data.tarih
                        if isinstance(data.tarih, date)
                        else date.fromisoformat(str(data.tarih))
                    )
                    if entry_date > today:
                        logger.warning(
                            f"Bulk skip: Vehicle {data.arac_id} future date {entry_date}"
                        )
                        continue
                    current_last_km = last_km_cache.get(data.arac_id, 0)
                    if data.km_sayac < current_last_km:
                        logger.warning(
                            f"Odometer error (Skipped): Vehicle {data.arac_id}, Last {current_last_km}, Entered {data.km_sayac}"  # noqa: E501
                        )
                        continue

                    fiyat_tl = float(data.fiyat_tl)
                    litre = float(data.litre)
                    items_to_add.append(
                        {
                            "tarih": data.tarih,
                            "arac_id": data.arac_id,
                            "istasyon": data.istasyon,
                            "fiyat_tl": fiyat_tl,
                            "litre": litre,
                            # Para çarpımı Decimal'de (float çarpımı cent hatası verir).
                            "toplam_tutar": (
                                Decimal(str(litre)) * Decimal(str(fiyat_tl))
                            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                            "km_sayac": data.km_sayac,
                            "fis_no": data.fis_no,
                            "depo_durumu": data.depo_durumu,
                        }
                    )
                    last_km_cache[data.arac_id] = data.km_sayac

                if items_to_add:
                    await uow.yakit_repo.bulk_create(items_to_add)
                    await uow.commit()
                    count = len(items_to_add)

            except Exception as e:
                logger.error(f"Bulk insert error: {e}")
                raise e

        if count > 0:
            logger.info(f"Bulk insert: {count} fuel transactions added")
        return count


def get_yakit_service() -> YakitService:
    from app.core.container import get_container

    return get_container().yakit_service
