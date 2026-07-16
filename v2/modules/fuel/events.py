"""Events published by the fuel module.

STATUS (FIXED 2026-07-16, dedektif denetimi: "ilk 9 dalgada teknik borç
bırakma"): the ``@publishes(EventType.X)`` decorator on
``add_yakit``/``update_yakit``/``delete_yakit`` is still metadata-only, but
each function now genuinely writes to the transactional outbox
(``save_outbox_event(uow.session, EventType.YAKIT_X, {"result": yakit_id,
"arac_id": ...})``, same transaction, before ``uow.commit()``). Both
previously-dead real subscribers now actually fire once Celery's
``relay-outbox-events-every-60s`` task relays the row:
``app/core/handlers/model_training_handler.py`` (YAKIT_ADDED → ML retrain
counter, reads the flat ``arac_id`` key) and
``app/infrastructure/cache/cache_invalidation.py`` (all three YAKIT_*,
wildcard cache clear). Both handlers are also now actually REGISTERED at
app startup (``app/main.py`` lifespan) — previously neither
``ModelTrainingHandler.setup()`` nor ``setup_cache_invalidation()`` was
ever called anywhere in the repo.
"""

from app.infrastructure.events.event_bus import EventType

YAKIT_ADDED = EventType.YAKIT_ADDED
YAKIT_UPDATED = EventType.YAKIT_UPDATED
YAKIT_DELETED = EventType.YAKIT_DELETED

__all__ = ["YAKIT_ADDED", "YAKIT_UPDATED", "YAKIT_DELETED"]
