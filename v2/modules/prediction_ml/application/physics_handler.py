import asyncio
from datetime import date

from v2.modules.platform_infra.events.event_bus import Event, EventType, get_event_bus
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
    RouteConditions,
    VehicleSpecs,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class PhysicsRecalculationHandler:
    """
    Handles automatic physics-based consumption recalculation when trips are updated.
    """

    def __init__(self):
        self.event_bus = get_event_bus()

    def register(self):
        """Register the handler to EventBus"""
        self.event_bus.subscribe(EventType.SEFER_UPDATED, self.on_sefer_updated)
        logger.info("PhysicsRecalculationHandler registered for SEFER_UPDATED events.")

    async def on_sefer_updated(self, event: Event):
        """
        Triggered when a trip is updated (including manual overrides).
        """
        data = event.data
        sefer_id = data.get("sefer_id")
        trigger = data.get("trigger")

        # Only process if triggered by manual override or specific calculation triggers
        # To avoid infinite loops, check if this was already a physics update
        if trigger == "physics_recalculation":
            return

        logger.info(
            f"Processing physics recalculation for Sefer {sefer_id} due to {trigger}"
        )

        async with UnitOfWork() as uow:
            # 1. Fetch Sefer with Arac details
            sefer = await uow.sefer_repo.get_by_id(sefer_id)
            if not sefer:
                return

            arac = await uow.arac_repo.get_by_id(sefer.get("arac_id"))
            if not arac:
                return

            # 2. Fetch Dorse if exists
            dorse = None
            if sefer.get("dorse_id"):
                dorse = await uow.dorse_repo.get_by_id(sefer.get("dorse_id"))

            # 3. Dynamic Calculation: Vehicle Age
            current_year = date.today().year
            arac_yasi = current_year - (arac.get("yil") or current_year - 5)

            # 4. Map to VehicleSpecs (Merging Truck + Trailer specs)
            specs = VehicleSpecs(
                empty_weight_kg=arac.get("bos_agirlik_kg") or 8000.0,
                trailer_empty_weight_kg=dorse.get("bos_agirlik_kg")
                if dorse
                else 6000.0,
                drag_coefficient=arac.get("hava_direnc_katsayisi") or 0.6,
                trailer_drag_contribution=dorse.get("dorse_hava_direnci")
                if dorse
                else 0.15,
                frontal_area_m2=arac.get("on_kesit_alani_m2") or 8.5,
                rolling_resistance=arac.get("lastik_direnc_katsayisi") or 0.007,
                trailer_rolling_resistance=dorse.get("dorse_lastik_direnc_katsayisi")
                if dorse
                else 0.006,
                engine_efficiency=arac.get("motor_verimliligi") or 0.38,
            )

            # 5. Map Sefer to RouteConditions
            conditions = RouteConditions(
                distance_km=sefer.get("mesafe_km"),
                load_ton=sefer.get("ton") or 0.0,
                is_empty_trip=sefer.get("bos_sefer"),
                ascent_m=sefer.get("ascent_m") or 0.0,
                descent_m=sefer.get("descent_m") or 0.0,
                flat_distance_km=sefer.get("flat_distance_km") or 0.0,
                arac_yasi=arac_yasi,
            )

            # 6. Predict — run sync physics calculation off the event loop.
            predictor = PhysicsBasedFuelPredictor(specs)
            prediction = await asyncio.to_thread(predictor.predict, conditions)

            # 7. Update Sefer
            await uow.sefer_repo.update(
                sefer_id,
                tahmini_tuketim=prediction.total_liters,
            )

            await uow.commit()

            # Emit internal event to notify UI or logs (if needed).
            # trigger="physics_recalculation" prevents recursion.
            await self.event_bus.publish_async(
                Event(
                    type=EventType.SEFER_UPDATED,
                    data={
                        "sefer_id": sefer_id,
                        "tahmini_tuketim": prediction.total_liters,
                        "trigger": "physics_recalculation",
                    },
                    source="PhysicsRecalculationHandler",
                )
            )

            logger.info(
                f"Recalculated consumption for Sefer {sefer_id}: {prediction.total_liters}L"
            )


# Singleton instance
_handler = PhysicsRecalculationHandler()


def get_physics_handler():
    return _handler
