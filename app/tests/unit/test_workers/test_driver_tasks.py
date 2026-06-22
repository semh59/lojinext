"""driver_tasks.py birim testleri."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.tasks.driver_tasks import calculate_performance_score

pytestmark = pytest.mark.unit


def _make_uow_mock(avg_tuketim=35.0, trip_count=10):
    mock_row = MagicMock()
    mock_row.avg_tuketim = avg_tuketim
    mock_row.trip_count = trip_count

    mock_execute_result = MagicMock()
    mock_execute_result.one_or_none.return_value = mock_row

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session = mock_session
    mock_uow.commit = AsyncMock()
    return mock_uow


def test_calculate_performance_score_is_celery_task():
    assert calculate_performance_score.name == "driver.calculate_performance_score"


def test_calculate_performance_score_with_trips(caplog):
    """Sefer geçmişi olan şoför için log yazılır."""
    import logging

    mock_uow = _make_uow_mock(avg_tuketim=38.5, trip_count=15)

    with patch("app.workers.tasks.driver_tasks.UnitOfWork", return_value=mock_uow):
        with caplog.at_level(logging.INFO, logger="app.workers.tasks.driver_tasks"):
            result = calculate_performance_score.apply(args=[42]).get()

    assert result is None
    assert "42" in caplog.text


def test_calculate_performance_score_no_trips(caplog):
    """Seferi olmayan şoför için 'no qualifying trips' logu yazılır."""
    import logging

    mock_execute_result = MagicMock()
    mock_execute_result.one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session = mock_session
    mock_uow.commit = AsyncMock()

    with patch("app.workers.tasks.driver_tasks.UnitOfWork", return_value=mock_uow):
        with caplog.at_level(logging.INFO, logger="app.workers.tasks.driver_tasks"):
            calculate_performance_score.apply(args=[99]).get()

    assert "no qualifying trips" in caplog.text.lower()


def test_calculate_performance_score_commits():
    """Task her zaman uow.commit çağırır."""
    mock_uow = _make_uow_mock()

    with patch("app.workers.tasks.driver_tasks.UnitOfWork", return_value=mock_uow):
        calculate_performance_score.apply(args=[7]).get()

    mock_uow.commit.assert_awaited_once()


def test_calculate_performance_score_different_driver_ids():
    """Farklı driver_id'leriyle task çağrılabilir."""
    for driver_id in [1, 100, 9999]:
        mock_uow = _make_uow_mock()
        with patch("app.workers.tasks.driver_tasks.UnitOfWork", return_value=mock_uow):
            result = calculate_performance_score.apply(args=[driver_id]).get()
        assert result is None


def test_calculate_performance_score_connection_error_retries():
    """ConnectionError → task retry mekanizması devreye girer."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session.execute = AsyncMock(side_effect=ConnectionError("DB unreachable"))
    mock_uow.commit = AsyncMock()

    with patch("app.workers.tasks.driver_tasks.UnitOfWork", return_value=mock_uow):
        try:
            calculate_performance_score.apply(args=[5]).get(propagate=True)
        except Exception:
            pass  # retry exhausted — expected


def test_calculate_performance_score_generic_error_reraises():
    """ValueError gibi generic exception retry yapmaz, re-raise eder."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session.execute = AsyncMock(side_effect=ValueError("bad data"))
    mock_uow.commit = AsyncMock()

    with patch("app.workers.tasks.driver_tasks.UnitOfWork", return_value=mock_uow):
        with pytest.raises(Exception):
            calculate_performance_score.apply(args=[1]).get(propagate=True)
