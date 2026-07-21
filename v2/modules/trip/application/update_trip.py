"""Sefer güncelleme use-case'i."""

from datetime import date
from typing import Any, Optional, cast

from app.core.services.route_validator import RouteValidator
from app.infrastructure.events.event_bus import (
    Event,
    EventBus,
    EventType,
    get_event_bus,
)
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.return_trip import handle_round_trip_on_update
from v2.modules.trip.application.sla import check_sla_delay
from v2.modules.trip.application.stats_refresh import refresh_stats
from v2.modules.trip.application.trip_prediction_enrichment import (
    check_reprediction_needed,
    repredikt_for_update,
)
from v2.modules.trip.domain.trip_validation import ALLOWED_TRANSITIONS
from v2.modules.trip.schemas import SeferUpdate
from v2.modules.trip.sefer_status import (
    SEFER_STATUS_PLANLANDI,
    SEFER_STATUS_TAMAMLANDI,
    ensure_canonical_sefer_status,
)

logger = get_logger(__name__)


@monitor_errors(category="sefer_write", severity="error")
async def update_sefer(
    sefer_id: int, data: SeferUpdate, user_id: Optional[int] = None
) -> bool:
    """Sefer gunceller."""
    async with UnitOfWork() as uow:
        success = await update_sefer_uow(uow, sefer_id, data, user_id)
        if success:
            await uow.commit()
            await refresh_stats(uow)
        return success


async def update_sefer_uow(
    uow: UnitOfWork,
    sefer_id: int,
    data: SeferUpdate,
    user_id: Optional[int] = None,
    event_bus: Optional[EventBus] = None,
) -> bool:
    """Sefer güncelleme mantığı (Paylaşımlı UoW destekli)."""
    bus = event_bus or get_event_bus()

    try:
        # Fetch current state for transition check
        current_sefer = await uow.sefer_repo.get_by_id(sefer_id, for_update=True)
        if not current_sefer:
            from v2.modules.shared_kernel.exceptions import RouteProcessingError

            raise RouteProcessingError(
                f"Sefer bulunamadı: {sefer_id}",
                entity_id=sefer_id,
                reason="SEFER_NOT_FOUND",
            )

        # mode='json' serializes enums to their .value strings so DB writes and
        # comparisons always see plain strings, not TripStatus.X repr.
        update_data = data.model_dump(exclude_unset=True, mode="json")
        if not update_data:
            return True  # Nothing to update

        if "tarih" in update_data and isinstance(update_data["tarih"], str):
            update_data["tarih"] = date.fromisoformat(update_data["tarih"])

        # B-004: Optimistic Locking version check
        if "version" in update_data and update_data["version"] is not None:
            current_version = current_sefer.get("version", 1)
            if current_version != update_data["version"]:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=409,
                    detail="Bu kayıt başka biri tarafından güncellenmiş. Lütfen sayfayı yenileyin.",
                )
            # Increment version locally.
            update_data["version"] = current_version + 1

        # Status Transition Validation
        new_status = update_data.get("durum")
        if new_status:
            old_status = ensure_canonical_sefer_status(
                current_sefer.get("durum", SEFER_STATUS_PLANLANDI),
                field_name="durum",
                allow_none=False,
            )
            if old_status != new_status:
                # ALLOWED_TRANSITIONS TripStatus str-enum ile key'li; old_status
                # canonical str — runtime'da eşit hash, mypy key tipini ayırıyor.
                allowed = ALLOWED_TRANSITIONS.get(cast(Any, old_status), [])
                if new_status not in allowed:
                    raise ValueError(
                        f"Geçersiz durum geçişi: '{old_status}' -> '{new_status}'"
                    )

        if user_id:
            update_data["updated_by_id"] = user_id

        # Sefer No duplicate check for update
        if "sefer_no" in update_data and update_data["sefer_no"]:
            if current_sefer.get("sefer_no") != update_data["sefer_no"]:
                existing = await uow.sefer_repo.get_by_sefer_no(update_data["sefer_no"])
                if existing:
                    raise ValueError(
                        f"Bu sefer numarası zaten kullanımda: {update_data['sefer_no']}"
                    )

        # Active Trip Check for Update
        target_arac_id = update_data.get("arac_id")

        # RE-PREDICTION LOGIC
        # Check if fields affecting fuel prediction are changed
        if check_reprediction_needed(update_data):
            await repredikt_for_update(uow, current_sefer, update_data)

        # Validate and correct route data before final database write
        update_data = RouteValidator.validate_and_correct(update_data)

        # Ağırlık senkronizasyonu
        # dolu - bos = net kısıtının bozulmaması için tüm alanlar güncellenir.
        if any(
            k in update_data for k in ["net_kg", "bos_agirlik_kg", "dolu_agirlik_kg"]
        ):
            # Değerleri al (yeni yoksa mevcut olanı kullan)
            b_kg = update_data.get(
                "bos_agirlik_kg", current_sefer.get("bos_agirlik_kg", 0)
            )
            d_kg = update_data.get(
                "dolu_agirlik_kg", current_sefer.get("dolu_agirlik_kg", 0)
            )
            n_kg = update_data.get("net_kg", current_sefer.get("net_kg", 0))

            # Öncelik sırasına göre hesapla
            if "dolu_agirlik_kg" in update_data or "bos_agirlik_kg" in update_data:
                # Dolu veya Boş değiştiyse Net'i güncelle
                n_kg = d_kg - b_kg
                update_data["net_kg"] = n_kg
            elif "net_kg" in update_data:
                # Sadece Net değiştiyse Dolu'yu güncelle
                d_kg = b_kg + n_kg
                update_data["dolu_agirlik_kg"] = d_kg

            # Tonajı her durumda güncelle
            update_data["ton"] = round(n_kg / 1000.0, 2)

        success = await uow.sefer_repo.update_sefer(id=sefer_id, **update_data)

        if success:
            # ROUTE EVENTS
            if new_status:
                if new_status == SEFER_STATUS_TAMAMLANDI:
                    await bus.publish_async(
                        Event(
                            type=EventType.ROUTE_COMPLETED,
                            data={
                                "sefer_id": sefer_id,
                                "arac_id": target_arac_id or current_sefer.get("arac_id"),
                            },
                            source="update_trip.update_sefer",
                        )
                    )
                    await check_sla_delay(uow, sefer_id, target_arac_id, current_sefer)

            # ROUND-TRIP CHECK
            if update_data.get("is_round_trip"):
                await handle_round_trip_on_update(uow, sefer_id, update_data)

        return bool(success)

    except Exception as e:
        logger.error(f"Sefer guncelleme hatasi (UoW): {e}")
        raise
