"""Events published by the driver module.

STATUS (FIXED 2026-07-16, dedektif denetimi: "ilk 9 dalgada teknik borç
bırakma"): the ``@publishes(EventType.X)`` decorator on
``add_sofor``/``update_sofor``/``delete_sofor`` is still metadata-only, but
each function now genuinely writes to the transactional outbox
(``save_outbox_event(uow.session, EventType.SOFOR_X, {"result": sofor_id})``,
same transaction, before ``uow.commit()``).
``app/core/ai/rag_sync_service.py``'s ``SOFOR_ADDED``/``SOFOR_UPDATED``
subscriber (``rag.index_driver``) now actually fires once Celery's
``relay-outbox-events-every-60s`` task relays the row — its
``_on_sofor_changed`` handler was extended with the same int-id fallback
``_on_arac_changed`` already had (``event.data["result"]`` is a bare id,
not a full dict; the handler fetches the record itself via
``get_sofor_repo().get_by_id``). ``RAGSyncService.initialize()`` is also
now actually called at app startup (``app/main.py`` lifespan) — previously
nothing anywhere invoked it, so this subscription never existed at
runtime.
"""

from app.infrastructure.events.event_bus import EventType

SOFOR_ADDED = EventType.SOFOR_ADDED
SOFOR_UPDATED = EventType.SOFOR_UPDATED
SOFOR_DELETED = EventType.SOFOR_DELETED

__all__ = ["SOFOR_ADDED", "SOFOR_UPDATED", "SOFOR_DELETED"]
