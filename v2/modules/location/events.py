"""Events published by the location module.

STATUS: the ``@publishes(EventType.X)`` decorator applied in
``application/{create,update,delete}_location.py`` is REPO-WIDE DEAD CODE
today — nothing reads the ``_publishes`` attribute it sets, and no
``event_bus.publish(...)`` call happens inside those functions either.
This was discovered while mapping the whole codebase's coupling (see
MEMORY/PROGRESS.md §3) and is NOT something this module migration fixes —
it's a pre-existing behavioral gap, documented here rather than silently
carried forward as if it worked.
"""

from app.infrastructure.events.event_bus import EventType

LOKASYON_ADDED = EventType.LOKASYON_ADDED
LOKASYON_UPDATED = EventType.LOKASYON_UPDATED
LOKASYON_DELETED = EventType.LOKASYON_DELETED

__all__ = ["LOKASYON_ADDED", "LOKASYON_UPDATED", "LOKASYON_DELETED"]
