"""
Typed event contracts used across producers and consumers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.infrastructure.events.event_types import EventType


class BaseEvent(BaseModel):
    event_id: str = Field(..., description="UUID4 idempotency key.")
    event_type: EventType
    version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None


class TripCreatedEvent(BaseEvent):
    payload: dict


class FuelUpdatedEvent(BaseEvent):
    payload: dict


class ModelRetrainRequestedEvent(BaseEvent):
    payload: dict


__all__ = [
    "EventType",
    "BaseEvent",
    "TripCreatedEvent",
    "FuelUpdatedEvent",
    "ModelRetrainRequestedEvent",
]
