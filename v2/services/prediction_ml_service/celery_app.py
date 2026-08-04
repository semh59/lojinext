"""Celery app for the standalone prediction_ml_service.

Split off the main backend's `v2.modules.platform_infra.background.
celery_app` when `domain/application/infrastructure` moved here (Task 5,
2026-08-04) -- this service now owns its own worker/beat process for
training, DLQ drain, and RAG/LLM tasks, sharing only the same Redis broker
the main backend uses (standard Celery multi-service pattern).

Docker-compose wiring for an actual worker/beat container is Task 9's job
-- this module just defines the app + registers tasks so imports resolve
and `celery -A prediction_ml_service.celery_app worker` is runnable today.
"""

import os

from celery import Celery
from celery.schedules import crontab

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", broker_url)

celery_app = Celery("prediction_ml_service", broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_soft_time_limit=70,
    task_time_limit=90,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    result_expires=3600,
    broker_transport_options={"visibility_timeout": 4200},
    beat_schedule={
        "drain-prediction-dlq-every-60s": {
            "task": "prediction.drain_dlq",
            "schedule": 60.0,
        },
        "ml-weekly-retrain-all-vehicles": {
            "task": "ml.weekly_retrain_all_vehicles",
            "schedule": crontab(day_of_week="sun", hour=3, minute=0),
        },
    },
)

import prediction_ml_service.infrastructure.dlq_tasks  # noqa: E402,F401
import prediction_ml_service.infrastructure.prediction_tasks  # noqa: E402,F401
import prediction_ml_service.infrastructure.scheduler_task  # noqa: E402,F401
