"""Events published by the fleet module.

STATUS: the ``@publishes(EventType.X)`` decorator applied in
``application/{create,update,delete}_vehicle.py`` is still repo-wide
metadata-only (nothing reads its ``_publishes`` attribute) — but as of
2026-07-16 (dedektif denetimi: "ilk 9 dalgada teknik borç bırakma") the
functions themselves genuinely write to the transactional outbox
(``save_outbox_event(uow.session, EventType.ARAC_X, {"result": arac_id})``,
same transaction, before ``uow.commit()``). Real subscribers now actually
receive these once Celery's ``relay-outbox-events-every-60s`` task relays
them: ``app/core/ai/rag_sync_service.py`` (indexes the vehicle into RAG,
ARAC_ADDED/UPDATED) and ``app/infrastructure/cache/cache_invalidation.py``
(wildcard cache clear, all three). Both are also now actually REGISTERED —
``app/main.py``'s lifespan calls ``setup_cache_invalidation()`` and
``get_rag_sync_service().initialize()`` at startup (previously neither was
ever invoked anywhere, a repo-wide gap documented in
``v2/modules/notification/CLAUDE.md`` and fixed for every module at once).
"""

from app.infrastructure.events.event_bus import EventType

ARAC_ADDED = EventType.ARAC_ADDED
ARAC_UPDATED = EventType.ARAC_UPDATED
ARAC_DELETED = EventType.ARAC_DELETED

__all__ = ["ARAC_ADDED", "ARAC_UPDATED", "ARAC_DELETED"]
