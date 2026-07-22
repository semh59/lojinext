"""Maliyet mutabakatı (cost reconciliation) — eski SeferAnalizService'in dissolve edilmiş hali.

``analytics_executive``'in ``analyze_trip_costs`` route'u bu fonksiyonu
``public.py`` üzerinden çağırır (task dosyası madde 2'nin
``trip_analytics_routes.py`` kararı).
"""

from typing import Any, Dict

from app.infrastructure.audit import audit_log
from app.infrastructure.logging.logger import get_logger
from v2.modules.platform_infra.events.event_bus import EventType, get_event_bus
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)

CONSUMPTION_THRESHOLD = 50.0


@audit_log("RECONCILE", "sefer")
async def reconcile_costs(
    sefer_id: int, consumption_threshold: float = CONSUMPTION_THRESHOLD
) -> Dict[str, Any]:
    """
    Belirtilen seferin (ve o günkü diğer seferlerin) yakıt maliyetlerini
    KM oranına göre yeniden hesapla ve dağıt.
    """
    event_bus = get_event_bus()
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

        total_daily_km = sum(t["mesafe_km"] for t in daily_trips if t.get("mesafe_km"))

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
            await event_bus.publish_simple_async(
                EventType.SEFER_UPDATED, id=t_id, tuketim=consumption
            )

            # 5. Anomaly Detection
            if consumption > consumption_threshold:
                logger.warning(
                    f"Anomaly detected for trip {t_id}: High consumption {consumption}"
                )
                await event_bus.publish_simple_async(
                    EventType.ANOMALY_DETECTED,
                    id=t_id,
                    type="HIGH_CONSUMPTION",
                    value=consumption,
                    threshold=consumption_threshold,
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
