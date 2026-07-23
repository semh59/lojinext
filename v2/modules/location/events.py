"""Events published by the location module.

STATUS: the ``@publishes(EventType.X)`` decorator applied in
``application/{create,update,delete}_location.py`` is still repo-wide
metadata-only (nothing reads the ``_publishes`` attribute it sets) — but as
of 2026-07-16 (dedektif denetimi: "ilk 9 dalgada teknik borç bırakma") the
functions themselves genuinely write to the transactional outbox
(``save_outbox_event(repo.session, EventType.LOKASYON_X, {"result": id})``,
same UnitOfWork/session as the caller) rather than doing nothing. No
subscriber currently listens for ``LOKASYON_*`` (unlike ARAC_*/YAKIT_*/
SOFOR_*), so these rows are relayed but land nowhere — harmless, and ready
for a future subscriber without another migration.
"""

from v2.modules.platform_infra.events.event_bus import EventType

LOKASYON_ADDED = EventType.LOKASYON_ADDED
LOKASYON_UPDATED = EventType.LOKASYON_UPDATED
LOKASYON_DELETED = EventType.LOKASYON_DELETED

__all__ = ["LOKASYON_ADDED", "LOKASYON_UPDATED", "LOKASYON_DELETED"]
