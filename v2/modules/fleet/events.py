"""Events published by the fleet module.

STATUS: the ``@publishes(EventType.X)`` decorator applied in
``application/{create,update,delete}_vehicle.py`` is REPO-WIDE DEAD CODE
today — nothing reads the ``_publishes`` attribute it sets, and no
``event_bus.publish(...)`` call happens inside those functions either
(same finding as ``v2/modules/location/events.py`` — confirmed again here
during dalga 3, grep for ``_publishes`` usage across app/ turns up only the
decorator's own definition and its two isolated unit tests). This is NOT a
regression introduced by this migration — it's a pre-existing behavioral
gap, documented rather than silently carried forward as if it worked.
"""

from app.infrastructure.events.event_bus import EventType

ARAC_ADDED = EventType.ARAC_ADDED
ARAC_UPDATED = EventType.ARAC_UPDATED
ARAC_DELETED = EventType.ARAC_DELETED

__all__ = ["ARAC_ADDED", "ARAC_UPDATED", "ARAC_DELETED"]
