"""Single entry point to activate all monitoring probes at startup."""

from __future__ import annotations

import sys

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def activate_all_probes(engine, celery_app=None) -> None:
    """
    Wire all probes to their respective systems.
    Call once from lifespan BEFORE accepting requests.

    Args:
        engine: The SQLAlchemy AsyncEngine instance.
        celery_app: The Celery application (optional — omit in test/dev).
    """
    from app.infrastructure.monitoring.event_bus import get_event_bus

    get_event_bus().start()

    from app.infrastructure.monitoring.db_probe import setup_db_probe

    setup_db_probe(engine)

    if celery_app is not None:
        from app.infrastructure.monitoring.celery_probe import setup_celery_probe

        setup_celery_probe()  # uses Celery signals — celery_app arg unused

    from app.infrastructure.monitoring.service_probe import (
        setup_asyncio_exception_handler,
    )

    setup_asyncio_exception_handler()

    _self_test()

    logger.info(
        "All monitoring probes activated: db=%s celery=%s service=asyncio",
        True,
        celery_app is not None,
    )


def _self_test() -> None:
    """Verify monitoring stack is reachable at startup.

    Emits a test event and checks that Redis accepted it. Logs to stderr
    (bypassing the bus itself) if the stack is broken so the failure is
    visible even when the event bus is down.
    """
    try:
        from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

        mgr = get_pubsub_manager()
        if mgr.redis is None:
            _warn_stderr(
                "monitoring self-test: Redis not connected — events will be lost"
            )
            return

        from app.infrastructure.monitoring.event_bus import get_event_bus
        from app.infrastructure.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        bus = get_event_bus()
        ev = ErrorEvent(
            layer=ErrorLayer.SERVICE,
            category="monitoring_self_test",
            severity=ErrorSeverity.INFO,
            message="Monitoring stack self-test on startup",
        )
        bus.emit_sync(ev)
        logger.info("Monitoring self-test: OK")
    except Exception as exc:
        _warn_stderr(f"monitoring self-test FAILED: {exc}")


def _warn_stderr(msg: str) -> None:
    print(f"[MONITORING SELF-TEST WARNING] {msg}", file=sys.stderr, flush=True)
    logger.warning(msg)
    try:
        import sentry_sdk

        sentry_sdk.capture_message(msg, level="warning")
    except Exception:
        pass
