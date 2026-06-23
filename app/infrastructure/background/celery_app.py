# -*- coding: utf-8 -*-
"""
Celery uygulama tanımı.
Redis broker/backend varsayılan; prod için env zorunlu (settings validator).
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings


def get_celery_app() -> Celery:
    """
    Celery uygulamasını hazırlar.

    settings.CELERY_EAGER=True ise bellek broker/backend kullanılır ve
    görevler yayıncı süreçte senkron çalışır (dev/test).
    """
    if settings.CELERY_EAGER:
        broker = "memory://"
        backend = "cache+memory://"
    else:
        broker = settings.CELERY_BROKER_URL or "redis://localhost:6379/0"
        backend = settings.CELERY_RESULT_BACKEND or broker

    app = Celery("lojinext", broker=broker, backend=backend)
    app.conf.update(
        task_soft_time_limit=70,
        task_time_limit=90,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        result_expires=3600,
        broker_transport_options={"visibility_timeout": 120},
        beat_schedule={
            "drain-prediction-dlq-every-60s": {
                "task": "prediction.drain_dlq",
                "schedule": 60.0,
            },
            "relay-outbox-events-every-60s": {
                "task": "infrastructure.relay_outbox_events",
                "schedule": 60.0,
            },
            "monitoring-error-digest-every-5m": {
                "task": "monitoring.error_digest",
                "schedule": 300.0,
            },
            "monitoring-create-monthly-partition-daily": {
                "task": "monitoring.create_monthly_partition",
                "schedule": 86400.0,
            },
            "monitoring-db-health-check-every-5m": {
                "task": "monitoring.db_health_check",
                "schedule": 300.0,
            },
            # Feature A.2 — Pazartesi 09:00 UTC haftalık koçluk özeti.
            "coaching-weekly-digest-mondays": {
                "task": "coaching.weekly_digest",
                "schedule": crontab(day_of_week="mon", hour=9, minute=0),
            },
            # Feature A.5 — Her gün 02:00 UTC, vakti gelmiş delivery delta hesabı.
            "coaching-evaluate-pending-daily": {
                "task": "coaching.evaluate_pending",
                "schedule": crontab(hour=2, minute=0),
            },
            # Feature B.3 — Her gün 03:00 UTC, hırsızlık pattern logu.
            "theft-pattern-scan-daily": {
                "task": "theft.daily_pattern_scan",
                "schedule": crontab(hour=3, minute=0),
            },
            # Phase 4.0 — Pazar 03:00 UTC, ML modeli haftalık yenileme.
            "ml-weekly-retrain-all-vehicles": {
                "task": "ml.weekly_retrain_all_vehicles",
                "schedule": crontab(day_of_week="sun", hour=3, minute=0),
            },
            # Faz 1 — Her gün 01:00 UTC, tahminisiz seferleri doldur (gece/düşük tempo).
            "prediction-backfill-missing-nightly": {
                "task": "prediction.backfill_missing",
                "schedule": crontab(hour=1, minute=0),
            },
            # Faz 3 — Her gün 04:00 UTC, retention: eski page_views temizliği.
            "analytics-prune-page-views-nightly": {
                "task": "analytics.prune_page_views",
                "schedule": crontab(hour=4, minute=0),
            },
            # Faz 4 — Her gün 06:00 UTC, muayenesi yaklaşan/geçmiş araç push'u.
            "compliance-inspection-push-daily": {
                "task": "compliance.inspection_push",
                "schedule": crontab(hour=6, minute=0),
            },
            # Faz 5 — Pazartesi 08:00 UTC, haftalık "dikkat etmen gereken 3 şey".
            "notifications-weekly-digest-mondays": {
                "task": "notifications.weekly_digest",
                "schedule": crontab(day_of_week="mon", hour=8, minute=0),
            },
            # Faz 8 — Her gün 05:00 UTC, anomali kümeleme taraması (pattern izleme).
            "anomaly-cluster-scan-daily": {
                "task": "anomaly.cluster_scan",
                "schedule": crontab(hour=5, minute=0),
            },
            # OPS-002 — Her gün 00:30 UTC, veritabanı yedeği al + eski yedekleri temizle.
            "db-backup-nightly": {
                "task": "infrastructure.db_backup",
                "schedule": crontab(hour=0, minute=30),
            },
        },
        worker_hostname="lojinext-worker@%h",
        task_always_eager=settings.CELERY_EAGER,
        task_eager_propagates=settings.CELERY_EAGER,
    )
    return app


celery_app = get_celery_app()

# Ensure tasks are registered
from celery.signals import worker_process_init  # noqa: E402

# Phase 4.0 — ML weekly retrain Celery task
import app.core.ml.training.scheduler_task  # noqa: E402,F401
import app.workers.tasks.analytics_tasks  # noqa: E402,F401
import app.workers.tasks.anomaly_cluster_tasks  # noqa: E402,F401

# OPS-002 — Nightly DB backup task
import app.workers.tasks.backup_tasks  # noqa: E402,F401
import app.workers.tasks.coaching_tasks  # noqa: E402,F401
import app.workers.tasks.compliance_tasks  # noqa: E402,F401
import app.workers.tasks.dlq_tasks  # noqa: E402,F401
import app.workers.tasks.error_digest  # noqa: E402,F401
import app.workers.tasks.notification_tasks  # noqa: E402,F401
import app.workers.tasks.outbox_tasks  # noqa: E402,F401
import app.workers.tasks.prediction_backfill_tasks  # noqa: E402,F401
import app.workers.tasks.prediction_tasks  # noqa: E402,F401
import app.workers.tasks.theft_tasks  # noqa: E402,F401
from app.infrastructure.resilience.shutdown import (  # noqa: E402
    register_shutdown_handlers,
)


@worker_process_init.connect
def init_worker(*args, **kwargs):
    register_shutdown_handlers()
    # After fork, the parent's asyncpg connections are bound to the parent's
    # event loop which is dead in the child process.  close=False abandons the
    # inherited handles without trying to close them (which would crash with
    # MissingGreenlet).  The child then opens fresh connections on its own
    # event loop when the first task runs.
    try:
        from app.database.connection import engine

        engine.sync_engine.pool.dispose(close=False)
    except Exception:
        pass
