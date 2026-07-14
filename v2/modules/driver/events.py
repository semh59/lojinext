"""Events published by the driver module.

STATUS: the ``@publishes(EventType.X)`` decorator applied in
``application/{add,update,delete}_sofor.py`` mirrors the same repo-wide
finding documented in ``v2/modules/fuel/events.py`` /
``v2/modules/fleet/events.py`` / ``v2/modules/notification/events.py`` /
``v2/modules/location/events.py`` — ``publishes()``
(``app/infrastructure/events/event_bus.py``) only sets a ``_publishes``
attribute on the function; nothing reads that attribute and none of
``add_sofor``/``update_sofor``/``delete_sofor`` call
``event_bus.publish(...)`` internally either (confirmed again here during
dalga 5, same as fleet/fuel/notification/location). This is NOT a
regression introduced by this migration — the original
``app/core/services/sofor_service.py`` had the exact same decorator-only
wiring.

REAL subscriber exists: ``app/core/ai/rag_sync_service.py`` subscribes to
``SOFOR_ADDED``/``SOFOR_UPDATED`` to keep the driver RAG index in sync
(``rag.index_driver``) — but since nothing ever calls
``event_bus.publish(...)`` for these types, this subscriber is dead in
practice too, same class of pre-existing gap as fuel's YAKIT_* finding.
"""

from app.infrastructure.events.event_bus import EventType

SOFOR_ADDED = EventType.SOFOR_ADDED
SOFOR_UPDATED = EventType.SOFOR_UPDATED
SOFOR_DELETED = EventType.SOFOR_DELETED

__all__ = ["SOFOR_ADDED", "SOFOR_UPDATED", "SOFOR_DELETED"]
