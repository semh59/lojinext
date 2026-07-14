"""Events published by the fuel module.

STATUS: the ``@publishes(EventType.X)`` decorator applied in
``application/{add,update,delete}_yakit.py`` mirrors the same repo-wide
finding documented in ``v2/modules/fleet/events.py`` /
``v2/modules/notification/events.py`` / ``v2/modules/location/events.py`` —
``publishes()`` (``app/infrastructure/events/event_bus.py``) only sets a
``_publishes`` attribute on the function; nothing reads that attribute and
none of ``add_yakit``/``update_yakit``/``delete_yakit`` call
``event_bus.publish(...)`` internally either (confirmed again here during
dalga 4, same as fleet/notification/location).

HIGHER-STAKES than the fleet/location repeats of this finding: two REAL
subscribers exist and are consequently dead in practice —
``app/core/handlers/model_training_handler.py`` subscribes to
``YAKIT_ADDED`` (would trigger ML retraining on new fuel data) and
``app/infrastructure/cache/cache_invalidation.py`` subscribes to all three
YAKIT_* events (would invalidate fuel-related caches). Neither fires from
the fuel module today. This is NOT a regression introduced by this
migration — the original ``app/core/services/yakit_service.py`` had the
exact same decorator-only wiring — but it is a more consequential
pre-existing gap than fleet's/location's ARAC_*/LOKASYON_* dead events and
is called out explicitly rather than assumed identical.
"""

from app.infrastructure.events.event_bus import EventType

YAKIT_ADDED = EventType.YAKIT_ADDED
YAKIT_UPDATED = EventType.YAKIT_UPDATED
YAKIT_DELETED = EventType.YAKIT_DELETED

__all__ = ["YAKIT_ADDED", "YAKIT_UPDATED", "YAKIT_DELETED"]
