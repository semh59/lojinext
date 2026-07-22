"""
Canonical event type definitions shared by typed contracts and the event bus.
"""

from enum import Enum


class EventType(str, Enum):
    # Legacy operational events
    ARAC_ADDED = "arac_added"
    ARAC_UPDATED = "arac_updated"
    ARAC_DELETED = "arac_deleted"

    SOFOR_ADDED = "sofor_added"
    SOFOR_UPDATED = "sofor_updated"
    SOFOR_DELETED = "sofor_deleted"

    YAKIT_ADDED = "yakit_added"
    YAKIT_UPDATED = "yakit_updated"
    YAKIT_DELETED = "yakit_deleted"

    SEFER_ADDED = "sefer_added"
    SEFER_UPDATED = "sefer_updated"
    SEFER_DELETED = "sefer_deleted"

    LOKASYON_ADDED = "lokasyon_added"
    LOKASYON_UPDATED = "lokasyon_updated"
    LOKASYON_DELETED = "lokasyon_deleted"

    ROUTE_STARTED = "route.started"
    ROUTE_COMPLETED = "route.completed"

    PERIYOT_CREATED = "periyot_created"
    YAKIT_DISTRIBUTED = "yakit_distributed"
    ANOMALY_DETECTED = "anomaly_detected"
    SLA_DELAY = "sla_delay"

    DATA_REFRESH_NEEDED = "data_refresh_needed"
    CACHE_INVALIDATED = "cache_invalidated"

    APP_STARTED = "app_started"
    APP_CLOSING = "app_closing"
    SETTINGS_CHANGED = "settings_changed"

    # Typed contract events
    TRIP_CREATED = "trip.created"
    FUEL_UPDATED = "fuel.updated"
    MODEL_RETRAIN_REQUESTED = "ml.retrain.requested"


__all__ = ["EventType"]
