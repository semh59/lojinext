"""prediction.backfill_missing Celery task wrapper testi (eager)."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_task_invokes_service_and_returns_summary():
    summary = {"processed": 2, "filled": 2, "failed": 0, "skipped": 0}
    with patch(
        "app.core.services.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(return_value=summary),
    ):
        from app.workers.tasks.prediction_backfill_tasks import backfill_missing

        result = backfill_missing.run(limit=10)

    assert result == summary
