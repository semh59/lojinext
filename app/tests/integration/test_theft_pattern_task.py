"""Feature B.3 — daily_pattern_scan Celery task smoke testleri."""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pattern_task_runs_with_empty_table(db_session):
    """Task çalışır; boş tablo için patterns_found=0 döner.

    db_session fixture'ı AsyncSessionLocal'ı test DB'ye monkeypatch eder
    → UoW içeride doğru session'a bağlanır.
    """
    from v2.modules.anomaly.infrastructure.theft_tasks import _run_pattern_scan

    result = await _run_pattern_scan(days=30, min_count=3, limit=50)
    assert "patterns_found" in result
    assert result["patterns_found"] >= 0
    assert result["window_days"] == 30
    assert result["min_count"] == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_celery_beat_schedule_includes_pattern_scan():
    """theft.daily_pattern_scan beat'te kayıtlı + 03:00 UTC."""
    from app.infrastructure.background.celery_app import celery_app

    assert "theft.daily_pattern_scan" in celery_app.tasks
    sched = celery_app.conf.beat_schedule
    assert "theft-pattern-scan-daily" in sched
    entry = sched["theft-pattern-scan-daily"]
    assert entry["task"] == "theft.daily_pattern_scan"
    cron = entry["schedule"]
    assert cron.hour == {3}
    assert cron.minute == {0}
