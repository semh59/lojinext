# -*- coding: utf-8 -*-
"""
Celery uygulama tanımı.
Redis broker/backend varsayılan; prod için env zorunlu (settings validator).

`app/infrastructure/background/celery_app.py`'den dalga 17 (platform_infra)
denetiminde taşındı — 9 bağımsız modül + shared_kernel task-registrasyonu
için bu dosyayı import ediyor, genuinely cross-cutting.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from v2.modules.platform_infra.cache.redis_client_factory import (
    get_celery_broker_transport_options,
    get_celery_broker_url,
    get_celery_result_backend_url,
)
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


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
        broker = get_celery_broker_url() or "redis://localhost:6379/0"
        backend = get_celery_result_backend_url() or broker

    # Tier E madde 31 — REDIS_USE_SENTINEL yönlendirir sentinel:// broker'a;
    # kombu'nun SentinelChannel'ı master_name'i visibility_timeout'la BİRLİKTE
    # aynı broker_transport_options dict'inden okuyor, bu yüzden merge edilir.
    broker_transport_options = {
        "visibility_timeout": 4200,
        **get_celery_broker_transport_options(),
    }

    app = Celery("lojinext", broker=broker, backend=backend)
    app.conf.update(
        task_soft_time_limit=70,
        task_time_limit=90,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        result_expires=3600,
        # 2026-07-01 prod-grade denetimi P0 #4: Redis broker'da visibility_timeout,
        # ACK gelmeden redelivery tetikleyen mekanizmadır ve TÜM task'lar için
        # TEK bir global değerdir (per-task override edilemez). Önceki değer
        # (120s) app'teki en uzun task'ların soft/hard time_limit'lerinin
        # (prediction.backfill_missing: 600/660s, coaching_tasks weekly digest:
        # 3600/3900s) çok altındaydı — bu task'lar kendi süreleri içinde normal
        # şekilde bitmeden broker onları "kayıp" sayıp BAŞKA bir worker'a tekrar
        # dağıtıyordu (duplike Mapbox/Open-Meteo çağrısı + duplike push
        # bildirimi + duplike route_simulations satırı). 4200s (70dk), en uzun
        # task'ın (3900s) üzerinde güvenli bir marj bırakır.
        broker_transport_options=broker_transport_options,
        result_backend_transport_options=get_celery_broker_transport_options(),
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
            # 2026-07-07 — Günlük, son 7 gün yakıt-tahmin coverage'ı runtime-config
            # eşiğinin (FUEL_COVERAGE_ALERT_THRESHOLD_PCT) altına düşerse ops alarmı.
            "monitoring-fuel-coverage-check-daily": {
                "task": "monitoring.fuel_coverage_check",
                "schedule": 86400.0,
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
            # Tier E madde 27 — 01:00 UTC (backup'tan 30dk sonra), en son yedeğin
            # gerçekten restore edilebildiğini doğrular (throwaway DB'ye pg_restore
            # + sanity query). Başarısızlık ErrorEvent alarmı tetikler.
            "db-backup-restore-verify-nightly": {
                "task": "infrastructure.db_backup_verify",
                "schedule": crontab(hour=1, minute=0),
            },
            # Item C follow-up (2026-07-30) -- weekly segment-tractive
            # physics recalibration snapshot, see physics_recalibration_
            # tasks.py's own docstring for why.
            "physics-weekly-recalibration-snapshot": {
                "task": "physics.weekly_recalibration_snapshot",
                "schedule": crontab(day_of_week="sun", hour=2, minute=30),
            },
        },
        worker_hostname="lojinext-worker@%h",
        task_always_eager=settings.CELERY_EAGER,
        task_eager_propagates=settings.CELERY_EAGER,
    )
    return app


celery_app = get_celery_app()

# Ensure tasks are registered
from celery.signals import task_postrun, worker_process_init  # noqa: E402

import v2.modules.analytics_executive.infrastructure.compliance_tasks  # noqa: E402,F401
import v2.modules.anomaly.infrastructure.cluster_tasks  # noqa: E402,F401
import v2.modules.anomaly.infrastructure.theft_tasks  # noqa: E402,F401
import v2.modules.driver.infrastructure.coaching_tasks  # noqa: E402,F401
import v2.modules.fuel.infrastructure.tasks  # noqa: E402,F401
import v2.modules.import_excel.infrastructure.tasks  # noqa: E402,F401
import v2.modules.notification.infrastructure.tasks  # noqa: E402,F401

# OPS-002 — Nightly DB backup task
import v2.modules.platform_infra.background.backup_tasks  # noqa: E402,F401
import v2.modules.platform_infra.background.error_digest  # noqa: E402,F401
import v2.modules.prediction_ml.infrastructure.dlq_tasks  # noqa: E402,F401
import v2.modules.prediction_ml.infrastructure.prediction_backfill_tasks  # noqa: E402,F401
import v2.modules.prediction_ml.infrastructure.prediction_tasks  # noqa: E402,F401

# Phase 4.0 — ML weekly retrain Celery task
import v2.modules.prediction_ml.infrastructure.scheduler_task  # noqa: E402,F401
import v2.modules.reports.infrastructure.analytics_tasks  # noqa: E402,F401

# Item C follow-up — weekly physics recalibration snapshot
import v2.modules.route_simulation.infrastructure.physics_recalibration_tasks  # noqa: E402,F401
import v2.modules.shared_kernel.infrastructure.outbox_tasks  # noqa: E402,F401

# NOT: driver.calculate_performance_score orphan Celery task'ı (hiç kayıtlı
# olmamış, hiçbir .delay() çağıranı yoktu) 2026-07-18 ölü-kod temizliğinde
# dosyasıyla birlikte silindi (v2/modules/driver/infrastructure/driver_tasks.py).
from v2.modules.platform_infra.resilience.shutdown import (  # noqa: E402
    register_shutdown_handlers,
)


def _drop_pooled_connections() -> None:
    """Discard every pooled asyncpg connection without trying to close it.

    `close=False` abandons the handles instead of gracefully closing them —
    a graceful close needs a running event loop for the same asyncpg
    connection, which is exactly what's unavailable when this is called
    from a synchronous Celery signal handler between two tasks' separate
    `asyncio.run()` lifetimes. The next `engine.connect()` opens a
    genuinely fresh connection on whatever event loop is current then.
    """
    try:
        from v2.modules.platform_infra.database.connection import engine

        # `close=False` is an Engine.dispose() kwarg, not Pool.dispose()'s
        # (SQLAlchemy 2.0's Pool.dispose() takes no arguments at all --
        # calling it with close=False raises TypeError, silently swallowed
        # by the bare except this pre-existing code used to have, meaning
        # this abandon-without-closing step had never actually run).
        # Engine.dispose(close=False) replaces the pool and abandons the
        # old one's checked-in connections without calling .close() on
        # them -- exactly what's needed here, since closing an asyncpg
        # connection whose event loop is already dead crashes with
        # MissingGreenlet.
        engine.sync_engine.dispose(close=False)
    except Exception as exc:
        logger.warning(
            "Pool dispose failed (engine may not be initialized yet): %s", exc
        )


@worker_process_init.connect
def init_worker(*args, **kwargs):
    register_shutdown_handlers()

    from v2.modules.platform_infra.database.module_role import (
        setup_celery_module_role_signals,
    )

    setup_celery_module_role_signals()
    # After fork, the parent's asyncpg connections are bound to the parent's
    # event loop, which is dead in the child process — drop them so the
    # child opens fresh connections on its own event loop when the first
    # task runs.
    _drop_pooled_connections()


@task_postrun.connect
def _dispose_pool_after_task(*args, **kwargs):
    """Each Celery task body runs its own `asyncio.run(...)`, which creates
    and then closes a fresh event loop per task. SQLAlchemy's async engine
    pool doesn't know that — it hands the next task a connection opened on
    a now-closed event loop, and `pool_pre_ping`'s own liveness check needs
    that same dead event loop to run its ping, so instead of gracefully
    detecting a stale connection it raises `RuntimeError: Event loop is
    closed` (reproduced live: roughly 30-50% of second+ same-child-process
    task runs crashed this way, non-deterministically, depending on which
    pooled connection got handed out). Dropping the pool after every task
    forces the next task's `asyncio.run()` to open connections fresh on its
    own loop — no cross-task connection reuse within a worker child
    process, but task volume here (beat-scheduled jobs, not a hot request
    path) makes that the right trade-off over a more invasive NullPool/
    engine-per-task redesign."""
    _drop_pooled_connections()
