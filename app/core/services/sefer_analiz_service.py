"""
TIR Yakıt Takip Sistemi - Sefer Analiz Servisi
Maliyet hesaplama, tahminleme ve raporlama mantığını içerir.
"""

from typing import Any, Dict, Optional

from app.database.repositories.sefer_repo import SeferRepository, get_sefer_repo
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.audit import audit_log
from app.infrastructure.events.event_bus import (
    EventBus,
    EventType,
    get_event_bus,
)
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class SeferAnalizService:
    """
    Sefer analiz ve maliyet işlemleri.
    """

    def __init__(
        self,
        repo: Optional[SeferRepository] = None,
        event_bus: Optional[EventBus] = None,
        consumption_threshold: float = 50.0,
    ):
        self.repo = repo or get_sefer_repo()
        self.event_bus = event_bus or get_event_bus()
        self.consumption_threshold = consumption_threshold

    @audit_log("RECONCILE", "sefer")
    async def reconcile_costs(self, sefer_id: int) -> Dict[str, Any]:
        """
        Belirtilen seferin (ve o günkü diğer seferlerin) yakıt maliyetlerini
        KM oranına göre yeniden hesapla ve dağıt.
        """
        async with UnitOfWork() as uow:
            # 1. Target Trip & Context
            target_trip = await uow.sefer_repo.get_by_id(sefer_id)
            if not target_trip:
                raise ValueError("Sefer bulunamadı")

            tarih = target_trip["tarih"]
            arac_id = target_trip["arac_id"]

            # 2. Get All Fuel for that Day & Vehicle.
            # YakitRepository.get_all returns a paginated {"items": [...]} envelope
            # (unlike SeferRepository.get_all which returns a plain list) — take items.
            daily_fuels = (
                await uow.yakit_repo.get_all(
                    filters={"arac_id": arac_id, "tarih": tarih}, limit=100
                )
            ).get("items", [])
            total_fuel_liters = sum(float(f["litre"]) for f in daily_fuels)

            if total_fuel_liters <= 0:
                return {
                    "status": "skipped",
                    "reason": "No fuel records for this day — existing consumption preserved",
                    "total_fuel": 0,
                }

            # 3. Get All Trips for that Day & Vehicle
            daily_trips = await uow.sefer_repo.get_all(
                filters={"arac_id": arac_id, "tarih": tarih}
            )

            total_daily_km = sum(
                t["mesafe_km"] for t in daily_trips if t.get("mesafe_km")
            )

            if total_daily_km <= 0:
                return {
                    "status": "skipped",
                    "reason": "Total daily distance is 0",
                    "total_fuel": total_fuel_liters,
                }

            # 4. Distribute & Updates
            updates = []
            for trip in daily_trips:
                t_id = trip["id"]
                t_km = trip.get("mesafe_km", 0)

                if t_km <= 0:
                    continue

                # Weighted Allocation
                ratio = t_km / total_daily_km
                allocated = total_fuel_liters * ratio
                consumption = (allocated / t_km) * 100

                # Update DB
                updated = await uow.sefer_repo.update_sefer(
                    t_id,
                    tuketim=consumption,
                    dagitilan_yakit=allocated,
                )
                if not updated:
                    continue

                # Publish update event
                await self.event_bus.publish_simple_async(
                    EventType.SEFER_UPDATED, id=t_id, tuketim=consumption
                )

                # 5. Anomaly Detection
                if consumption > self.consumption_threshold:
                    logger.warning(
                        f"Anomaly detected for trip {t_id}: High consumption {consumption}"
                    )
                    await self.event_bus.publish_simple_async(
                        EventType.ANOMALY_DETECTED,
                        id=t_id,
                        type="HIGH_CONSUMPTION",
                        value=consumption,
                        threshold=self.consumption_threshold,
                    )

                updates.append(
                    {
                        "trip_id": t_id,
                        "km": t_km,
                        "allocated_liters": round(allocated, 2),
                        "consumption": round(consumption, 2),
                    }
                )

            await uow.commit()

            return {
                "status": "success",
                "date": str(tarih),
                "total_km": total_daily_km,
                "total_fuel": total_fuel_liters,
                "trips_updated": len(updates),
                "details": updates,
            }
