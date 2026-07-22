"""Outbox event relay tasks.

`app/workers/tasks/outbox_tasks.py`'den dalga 17 (platform-infra) denetiminde
taşındı — bu task'ın tek işi `v2.modules.shared_kernel.infrastructure.outbox`'ı
periyodik relay etmek, OutboxEvent zaten shared_kernel'de yaşıyor (dalga 16).
"""

from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="infrastructure.relay_outbox_events",
    max_retries=5,
    default_retry_delay=60,
    acks_late=True,
)
def relay_outbox_events(self):
    """
    Background task to relay pending outbox events to the message bus.
    Should be scheduled to run every minute or so.
    """
    import asyncio

    from v2.modules.shared_kernel.infrastructure.outbox import get_outbox_service

    async def run_relay():
        service = get_outbox_service()
        count = await service.relay_pending_events(limit=100)
        if count > 0:
            logger.info(f"Relayed {count} outbox events.")

    try:
        # Dispose the shared async engine before starting a new event loop.
        # Celery fork workers inherit the parent's connection pool; those
        # connections are bound to the parent's event loop and will raise
        # "Future attached to a different loop" when reused in asyncio.run().
        from app.database.connection import engine

        engine.sync_engine.dispose()
        asyncio.run(run_relay())
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
    except Exception:
        logger.exception("Task failed permanently: %s", self.name)
        raise
