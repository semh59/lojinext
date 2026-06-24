"""driver_tasks.py birim testleri — real DB for the score computation.

`_compute_driver_score` runs an AVG/COUNT over a driver's qualifying trips
(``tuketim IS NOT NULL AND tuketim > 0``). The happy paths run against the
real test DB with seeded Sefer rows, so the returned figures are the real
query result — including proof that null/zero-tuketim trips are excluded by
the WHERE clause (a mock would hide a wrong filter).

The celery wrapper tests (task name, ConnectionError → retry, generic →
re-raise) stay mocked, honestly: the task body runs via ``asyncio.run`` in a
fresh event loop, so it cannot share the loop-bound fixture session — those
tests target the celery retry/error boundary, not the DB query.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor
from app.workers.tasks.driver_tasks import (
    _compute_driver_score,
    calculate_performance_score,
)

pytestmark = pytest.mark.unit


async def _seed_driver_with_trips(db_session, tuketim_values):
    """Seed one sofor + arac and one sefer per value in tuketim_values."""
    arac = await seed_arac(db_session, plaka="34 DRV 001")
    sofor = await seed_sofor(db_session, ad_soyad="Perf Sofor")
    for val in tuketim_values:
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            durum="Completed",
            tuketim=val,
        )
    await db_session.commit()
    return sofor


# --- real DB ---------------------------------------------------------------


async def test_compute_driver_score_with_trips(db_session):
    """Average + count come from the real seeded trips."""
    sofor = await _seed_driver_with_trips(db_session, [30.0, 40.0, 50.0])

    result = await _compute_driver_score(sofor.id)

    assert result["driver_id"] == sofor.id
    assert result["trip_count"] == 3
    assert result["avg_tuketim"] == pytest.approx(40.0)


async def test_compute_driver_score_no_trips(db_session):
    """A driver with no qualifying trips → zeroed figures."""
    result = await _compute_driver_score(999999)

    assert result["trip_count"] == 0
    assert result["avg_tuketim"] == 0.0


async def test_compute_driver_score_excludes_null_and_zero(db_session):
    """null- and zero-tuketim trips are filtered out of the average."""
    # 2 qualifying (20, 40) + one None + one 0.0 → avg 30 over 2 trips.
    sofor = await _seed_driver_with_trips(db_session, [20.0, 40.0, None, 0.0])

    result = await _compute_driver_score(sofor.id)

    assert result["trip_count"] == 2
    assert result["avg_tuketim"] == pytest.approx(30.0)


async def test_compute_driver_score_logs_summary(db_session, caplog):
    """The qualifying-trip branch logs the driver id and trip count."""
    import logging

    sofor = await _seed_driver_with_trips(db_session, [35.0, 45.0])
    with caplog.at_level(logging.INFO, logger="app.workers.tasks.driver_tasks"):
        await _compute_driver_score(sofor.id)

    assert str(sofor.id) in caplog.text
    assert "avg_tuketim" in caplog.text


async def test_compute_driver_score_no_trips_logs(db_session, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="app.workers.tasks.driver_tasks"):
        await _compute_driver_score(888888)

    assert "no qualifying trips" in caplog.text.lower()


# --- celery wrapper boundary (documented) ----------------------------------


def test_calculate_performance_score_is_celery_task():
    assert calculate_performance_score.name == "driver.calculate_performance_score"


def test_calculate_performance_score_connection_error_retries():
    """ConnectionError from the inner coro → task retry path is taken."""
    with patch(
        "app.workers.tasks.driver_tasks._compute_driver_score",
        new=AsyncMock(side_effect=ConnectionError("DB unreachable")),
    ):
        with pytest.raises(Exception):
            calculate_performance_score.apply(args=[5]).get(propagate=True)


def test_calculate_performance_score_generic_error_reraises():
    """A generic exception is logged and re-raised (no retry)."""
    with patch(
        "app.workers.tasks.driver_tasks._compute_driver_score",
        new=AsyncMock(side_effect=ValueError("bad data")),
    ):
        with pytest.raises(Exception):
            calculate_performance_score.apply(args=[1]).get(propagate=True)
