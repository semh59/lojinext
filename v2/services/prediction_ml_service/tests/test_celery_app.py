"""Celery task registration tests for this service's own Celery app.

Split off app/tests/unit/test_workers/test_celery_tasks.py (Task 5,
2026-08-04): run_prediction_task now registers on
prediction_ml_service.celery_app, a separate Celery app/broker connection
from the main backend's v2.modules.platform_infra.background.celery_app --
it never appears in that app's task registry anymore.
"""

import pytest

pytestmark = pytest.mark.unit


class TestPredictionTaskRegistration:
    def test_prediction_task_is_registered(self):
        """run_prediction_task is registered with correct name."""
        from prediction_ml_service.infrastructure.prediction_tasks import (
            run_prediction_task,
        )

        assert run_prediction_task.name == "prediction.generate"

    def test_prediction_task_max_retries(self):
        """run_prediction_task has max_retries=3."""
        from prediction_ml_service.infrastructure.prediction_tasks import (
            run_prediction_task,
        )

        assert run_prediction_task.max_retries == 3

    def test_celery_app_is_importable(self):
        """This service's own celery_app is a Celery instance with its tasks registered."""
        from prediction_ml_service.celery_app import celery_app

        assert celery_app is not None
        assert "prediction.generate" in celery_app.tasks
        assert "ml.weekly_retrain_all_vehicles" in celery_app.tasks
