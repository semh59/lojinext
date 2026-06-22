"""theft_tasks.py birim testleri."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.tasks.theft_tasks import _run_pattern_scan, daily_pattern_scan

pytestmark = pytest.mark.unit


def _make_uow_mock(rows=None):
    if rows is None:
        rows = []
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session = mock_session
    return mock_uow


@pytest.mark.asyncio
async def test_run_pattern_scan_no_patterns():
    """Sorgu boş liste döndüğünde patterns_found=0."""
    with patch("app.database.unit_of_work.UnitOfWork", return_value=_make_uow_mock()):
        result = await _run_pattern_scan(days=30, min_count=3, limit=100)

    assert result["patterns_found"] == 0
    assert result["window_days"] == 30
    assert result["min_count"] == 3


@pytest.mark.asyncio
async def test_run_pattern_scan_with_patterns(caplog):
    """Satır bulunan case'de logger.warning THEFT_PATTERN içerir."""
    import logging

    rows = [
        {
            "sofor_id": 1,
            "arac_id": 10,
            "occurrence_count": 5,
            "avg_suspicion_score": 0.87,
            "last_seen": "2026-06-01",
            "sofor_adi": None,
            "plaka": None,
        }
    ]
    with patch(
        "app.database.unit_of_work.UnitOfWork", return_value=_make_uow_mock(rows)
    ):
        with caplog.at_level(logging.WARNING, logger="app.workers.tasks.theft_tasks"):
            result = await _run_pattern_scan()

    assert result["patterns_found"] == 1
    assert "THEFT_PATTERN" in caplog.text


@pytest.mark.asyncio
async def test_run_pattern_scan_db_error():
    """DB hatası → exception fırlatılır (task katmanı yakalar)."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session.execute = AsyncMock(side_effect=Exception("DB error"))

    with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
        with pytest.raises(Exception, match="DB error"):
            await _run_pattern_scan()


@pytest.mark.asyncio
async def test_run_pattern_scan_custom_params():
    """Özel parametreler sonuca yansır."""
    with patch("app.database.unit_of_work.UnitOfWork", return_value=_make_uow_mock()):
        result = await _run_pattern_scan(days=7, min_count=5, limit=50)

    assert result["window_days"] == 7
    assert result["min_count"] == 5


def test_daily_pattern_scan_is_celery_task():
    assert daily_pattern_scan.name == "theft.daily_pattern_scan"


def test_daily_pattern_scan_handles_db_error():
    """DB hatası → task error key döndürür, exception fırlatmaz."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session.execute = AsyncMock(side_effect=Exception("conn refused"))

    with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
        result = daily_pattern_scan.apply().get()

    assert "error" in result
    assert result["patterns_found"] == 0


@pytest.mark.asyncio
async def test_run_pattern_scan_avg_score_null():
    """avg_suspicion_score None ise float(0) kullanılır, TypeError fırlatmaz."""
    rows = [
        {
            "sofor_id": 1,
            "arac_id": 5,
            "occurrence_count": 4,
            "avg_suspicion_score": None,
            "last_seen": None,
            "sofor_adi": None,
            "plaka": None,
        }
    ]
    with patch(
        "app.database.unit_of_work.UnitOfWork", return_value=_make_uow_mock(rows)
    ):
        result = await _run_pattern_scan()

    assert result["patterns_found"] == 1


@pytest.mark.asyncio
async def test_run_pattern_scan_returns_meta_keys():
    """Dönüş dict'i beklenen anahtarları içerir."""
    with patch("app.database.unit_of_work.UnitOfWork", return_value=_make_uow_mock()):
        result = await _run_pattern_scan()

    assert {"patterns_found", "window_days", "min_count"} <= result.keys()
