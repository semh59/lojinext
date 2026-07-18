"""SLA gecikme kontrolü — tamamlanan sefer için outbox'a SLA_DELAY event'i yazar.

NOT: task dosyası (``TASKS/modules/trip.md`` madde 5) bunu ``domain/sla.py``
olarak planlamıştı; gerçek kod ``uow.sefer_repo``/``uow.lokasyon_repo`` DB I/O'su
ve ``get_outbox_service()`` çağrısı yapıyor — kök CLAUDE.md'nin domain-saflığı
kuralını (I/O yok) ihlal ederdi. prediction_ml dalgasındaki aynı sınıf sapmayla
tutarlı olarak ``application/``'a taşındı.
"""

from typing import Any, Dict, Optional

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.events.event_bus import EventType
from app.infrastructure.events.outbox_service import get_outbox_service
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def check_sla_delay(
    uow: UnitOfWork,
    sefer_id: int,
    target_arac_id: Optional[int],
    current_sefer: Dict[str, Any],
) -> None:
    """Tamamlanan seferin SLA gecikmesini hesaplar ve outbox'a yazar."""
    try:
        current_full = await uow.sefer_repo.get_by_id(sefer_id)
        if not current_full:
            return
        actual_duration = current_full.get("duration_min")
        planned_duration_min = 0
        if current_full.get("guzergah_id"):
            route = await uow.lokasyon_repo.get_by_id(current_full["guzergah_id"])
            if route and route.get("tahmini_sure_saat"):
                planned_duration_min = int(route["tahmini_sure_saat"] * 60)
        if planned_duration_min > 0 and actual_duration:
            delay_min = actual_duration - planned_duration_min
            outbox = get_outbox_service()
            await outbox.save_event(
                event_type=EventType.SLA_DELAY,
                payload={
                    "sefer_id": sefer_id,
                    "arac_id": target_arac_id or current_sefer.get("arac_id"),
                    "planned_min": planned_duration_min,
                    "actual_min": actual_duration,
                    "delay_min": delay_min,
                },
                uow=uow,
            )
    except Exception as sla_err:
        logger.error(f"SLA Check fail: {sla_err}")
