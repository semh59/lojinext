from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity


def emit(event: "ErrorEvent") -> None:
    """Sync emit — safe from SQLAlchemy events, Celery signals, sync code."""
    try:
        from app.infrastructure.monitoring.event_bus import get_event_bus

        get_event_bus().emit_sync(event)
    except Exception:
        import logging

        logging.getLogger(__name__).debug("monitoring.emit failed", exc_info=True)


async def aemit(event: "ErrorEvent") -> None:
    """Async emit — use from async service/endpoint code."""
    try:
        from app.infrastructure.monitoring.event_bus import get_event_bus

        await get_event_bus().emit(event)
    except Exception:
        import logging

        logging.getLogger(__name__).debug("monitoring.aemit failed", exc_info=True)


__all__ = ["ErrorEvent", "ErrorLayer", "ErrorSeverity", "emit", "aemit"]
