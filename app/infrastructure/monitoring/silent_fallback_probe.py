"""Silent-fallback observability probe.

Several code paths degrade *silently* when an upstream dependency is slow or
returns an error: the request still succeeds, but with reduced fidelity
(NULL fuel prediction, physics-only estimate without real elevation, ...).
Each site already logs a WARNING, but a single WARNING line is invisible at
fleet scale.  This probe aggregates those events by reason so operations can
alarm on a *rate*, not grep logs.

Mirrors the MLProbe pattern (collections.Counter + threshold emit).

Wired sites (2026-06-04 GO operation, gate #3):
  - ``sefer_estimator_timeout``     — SeferFuelEstimator >2.5s → sefer saved without prediction
  - ``open_meteo_elevation_failed`` — Open-Meteo elevation 4xx/None → physics underestimate risk
"""

from __future__ import annotations

import threading
from collections import Counter

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

# Emit an alert event every N occurrences of a given reason, so a sustained
# silent-degradation pattern surfaces in Sentry/alarms without spamming per event.
_ALERT_EVERY_N = 25


class SilentFallbackProbe:
    """Counts silent-degradation events by reason; alerts on sustained rate."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()

    def _emit(self, event: ErrorEvent) -> None:
        try:
            from app.infrastructure.monitoring import emit as _emit_fn

            _emit_fn(event)
        except Exception as exc:  # observability must never break the request
            logger.debug("SilentFallbackProbe emit failed: %s", exc)

    def record(self, reason: str, **context: object) -> None:
        """Record one silent-fallback occurrence. Never raises."""
        with self._lock:
            self._counts[reason] += 1
            count = self._counts[reason]

        if count % _ALERT_EVERY_N == 0:
            try:
                self._emit(
                    ErrorEvent(
                        layer=ErrorLayer.EXTERNAL,
                        category="silent_fallback",
                        severity=ErrorSeverity.WARNING,
                        message=(
                            f"Silent fallback '{reason}' reached {count} occurrences "
                            "— upstream degradation is recurring."
                        ),
                        metadata={"reason": reason, "count": count, **context},
                    )
                )
            except Exception as exc:  # observability must never break the request
                logger.debug("SilentFallbackProbe alert emit failed: %s", exc)

    def get_stats(self) -> dict:
        """Snapshot of all recorded reasons (for the status endpoint)."""
        with self._lock:
            counts = dict(self._counts)
        return {
            "reasons": counts,
            "total": sum(counts.values()),
            "alert_every_n": _ALERT_EVERY_N,
        }


_probe: SilentFallbackProbe | None = None


def get_silent_fallback_probe() -> SilentFallbackProbe:
    global _probe
    if _probe is None:
        _probe = SilentFallbackProbe()
    return _probe


def record_silent_fallback(reason: str, **context: object) -> None:
    """Module-level convenience — safe to call from anywhere; never raises."""
    try:
        get_silent_fallback_probe().record(reason, **context)
    except Exception as exc:
        logger.debug("record_silent_fallback failed: %s", exc)
