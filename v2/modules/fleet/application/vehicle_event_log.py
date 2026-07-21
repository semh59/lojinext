"""Vehicle event-log helper — shared by create/update/delete_vehicle use-cases."""

from typing import Any, Optional

from app.infrastructure.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def log_vehicle_event(
    arac_id: int,
    event_type: str,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    details: Optional[str] = None,
    uow: Optional[Any] = None,
    triggered_by: Optional[str] = "SYSTEM",
) -> None:
    """Creates a vehicle event log entry (Atomic & UoW Compatible)."""
    try:
        from v2.modules.fleet.infrastructure.models import VehicleEventLog

        log = VehicleEventLog(
            arac_id=arac_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            triggered_by=triggered_by,
            details=details,
        )

        if uow:
            uow.session.add(log)
        else:
            async with UnitOfWork() as uow_internal:
                uow_internal.session.add(log)
                await uow_internal.commit()
    except Exception as e:
        logger.error(f"Vehicle event log error: {e}")
