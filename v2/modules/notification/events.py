"""Events consumed by the notification module.

notification does not publish events of its own — it subscribes to
SEFER_UPDATED and SLA_DELAY (published by the trip module) and turns them
into `bildirim_gecmisi` rows + UI/email delivery. The payload DTOs below
are intentionally tolerant (all fields Optional) because several different
trip-module call sites publish these events with slightly different field
sets (see application/handle_trip_events.py for what is actually read).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from v2.modules.platform_infra.events.event_bus import EventType

SEFER_UPDATED = EventType.SEFER_UPDATED
SLA_DELAY = EventType.SLA_DELAY


class SeferUpdatedPayload(BaseModel):
    sefer_id: Optional[int] = None
    trigger: Optional[str] = None


class SlaDelayPayload(BaseModel):
    sefer_id: Optional[int] = None
    delay_min: int = 0


__all__ = [
    "SEFER_UPDATED",
    "SLA_DELAY",
    "SeferUpdatedPayload",
    "SlaDelayPayload",
]
