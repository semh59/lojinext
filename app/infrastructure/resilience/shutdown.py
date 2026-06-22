"""
Shutdown Management - Graceful termination handling
Signals SIGTERM and SIGINT are caught to set a global stop flag.
"""

import signal

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Global stop flag
STOP_REQUESTED = False


def handle_shutdown(signum, frame):
    global STOP_REQUESTED
    logger.info(f"Signal {signum} received, requesting graceful shutdown...")
    STOP_REQUESTED = True


def register_shutdown_handlers():
    """Register SIGTERM and SIGINT handlers.

    No-ops when called from a non-main thread (e.g. TestClient lifespan
    runs inside an anyio worker thread where signal() is not allowed).
    """
    import threading

    if threading.current_thread() is not threading.main_thread():
        logger.debug("Shutdown handlers skipped (non-main thread)")
        return
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    logger.debug("Shutdown handlers registered (SIGTERM, SIGINT)")


def is_stopping() -> bool:
    """Check if a shutdown has been requested."""
    return STOP_REQUESTED
