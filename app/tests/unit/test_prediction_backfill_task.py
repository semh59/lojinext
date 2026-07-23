"""prediction.backfill_missing Celery task wrapper testi (eager)."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_task_invokes_service_and_returns_summary():
    summary = {"processed": 2, "filled": 2, "failed": 0, "skipped": 0}
    with patch(
        "v2.modules.prediction_ml.application.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(return_value=summary),
    ):
        from v2.modules.prediction_ml.infrastructure.prediction_backfill_tasks import (
            backfill_missing,
        )

        result = backfill_missing.run(limit=10)

    assert result == summary


def test_backfill_missing_generic_error_reraises():
    """2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 16): eskiden generic
    bir hata yutulup normal bir sonuç dict'i dönüyordu (Celery bunu SUCCESS
    sayardı, `max_retries` fiilen devre dışı kalıyordu). Artık log'lanıp
    yeniden fırlatılıyor — task gerçekten FAILED olarak işaretlenir."""
    with patch(
        "v2.modules.prediction_ml.application.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(side_effect=ValueError("bad estimator input")),
    ):
        from v2.modules.prediction_ml.infrastructure.prediction_backfill_tasks import (
            backfill_missing,
        )

        with pytest.raises(Exception):
            backfill_missing.apply(args=[10]).get(propagate=True)


def test_backfill_missing_connection_error_retries():
    """Geçici bir bağlantı hatası (Mapbox/Open-Meteo/DB) retry path'ini
    tetikler."""
    with patch(
        "v2.modules.prediction_ml.application.prediction_backfill_service.PredictionBackfillService.backfill",
        new=AsyncMock(side_effect=TimeoutError("Mapbox timeout")),
    ):
        from v2.modules.prediction_ml.infrastructure.prediction_backfill_tasks import (
            backfill_missing,
        )

        with pytest.raises(Exception):
            backfill_missing.apply(args=[10]).get(propagate=True)
