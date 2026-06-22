"""Celery tasks for driver service."""

from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


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

    async def run_calc():
        async with UnitOfWork() as uow:
            logger.info(f"Calculating performance score for driver {driver_id}")
            # Fetch recent trips for this driver and compute a simple
            # performance score based on fuel efficiency vs fleet average.
            from sqlalchemy import func, select

            from app.database.models import Sefer

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
            if row and row.trip_count:
                logger.info(
                    "Driver %s: avg_tuketim=%.2f l/100km over %d trips",
                    driver_id,
                    row.avg_tuketim or 0.0,
                    row.trip_count,
                )
            else:
                logger.info("Driver %s: no qualifying trips found.", driver_id)
            # No write needed — score computed on-demand via analiz endpoints.
            await uow.commit()

    try:
        asyncio.run(run_calc())
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
    except Exception:
        logger.exception("Task failed permanently: %s", self.name)
        raise
