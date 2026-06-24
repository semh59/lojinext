"""Celery tasks for driver service."""

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def _compute_driver_score(driver_id: int) -> dict:
    """Compute a driver's qualifying-trip count and average fuel use.

    Only trips with a real, positive ``tuketim`` count toward the average
    (``isnot(None)`` and ``> 0`` exclude unmeasured/zero rows). Returns the
    computed figures so callers (and tests) can assert on real DB results
    rather than only inspecting logs.
    """
    from sqlalchemy import func, select

    from app.database.models import Sefer

    async with UnitOfWork() as uow:
        logger.info(f"Calculating performance score for driver {driver_id}")
        stmt = (
            select(
                func.avg(Sefer.tuketim).label("avg_tuketim"),
                func.count(Sefer.id).label("trip_count"),
            )
            .where(Sefer.sofor_id == driver_id)
            .where(Sefer.tuketim.isnot(None))
            .where(Sefer.tuketim > 0)
        )
        result = await uow.session.execute(stmt)
        row = result.one_or_none()
        trip_count = int(row.trip_count) if row and row.trip_count else 0
        avg_tuketim = float(row.avg_tuketim) if trip_count else 0.0
        if trip_count:
            logger.info(
                "Driver %s: avg_tuketim=%.2f l/100km over %d trips",
                driver_id,
                avg_tuketim,
                trip_count,
            )
        else:
            logger.info("Driver %s: no qualifying trips found.", driver_id)
        # No write needed — score computed on-demand via analiz endpoints.
        await uow.commit()
    return {
        "driver_id": driver_id,
        "trip_count": trip_count,
        "avg_tuketim": avg_tuketim,
    }


@celery_app.task(
    bind=True,
    name="driver.calculate_performance_score",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def calculate_performance_score(self, driver_id: int):
    """
    Computes driver performance score based on trip history,
    fuel efficiency, and safety metrics.
    """
    import asyncio

    try:
        asyncio.run(_compute_driver_score(driver_id))
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
    except Exception:
        logger.exception("Task failed permanently: %s", self.name)
        raise
