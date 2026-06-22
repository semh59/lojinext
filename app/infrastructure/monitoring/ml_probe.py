from __future__ import annotations

import threading
from collections import Counter

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity

logger = get_logger(__name__)

_FALLBACK_RATE_THRESHOLD = 0.80  # 80% fallback → model broken
_CHECK_EVERY_N_PREDICTIONS = 100


class MLProbe:
    """Tracks physics fallback rate per model. Emits alert if rate > 80%."""

    def __init__(self) -> None:
        self._total: Counter[str] = Counter()
        self._fallback: Counter[str] = Counter()
        self._lock = threading.Lock()

    def _emit(self, event: ErrorEvent) -> None:
        try:
            from app.infrastructure.monitoring import emit as _emit_fn

            _emit_fn(event)
        except Exception as exc:
            logger.debug("MLProbe emit failed: %s", exc)

    def record_prediction(self, model_id: str, used_fallback: bool) -> None:
        with self._lock:
            self._total[model_id] += 1
            if used_fallback:
                self._fallback[model_id] += 1
            total = self._total[model_id]
            fallback_count = self._fallback[model_id]
        # emit outside lock
        if total % _CHECK_EVERY_N_PREDICTIONS == 0:
            rate = fallback_count / total
            if rate > _FALLBACK_RATE_THRESHOLD:
                self._emit(
                    ErrorEvent(
                        layer=ErrorLayer.ML,
                        category="high_fallback_rate",
                        severity=ErrorSeverity.ERROR,
                        message=(
                            f"Model '{model_id}' fallback rate {rate:.0%} "
                            f"({fallback_count}/{total} predictions)"
                        ),
                        metadata={
                            "model_id": model_id,
                            "fallback_rate": round(rate, 3),
                            "fallback_count": fallback_count,
                            "total_predictions": total,
                        },
                    )
                )

    def record_model_load_failure(self, model_id: str, exc: Exception) -> None:
        self._emit(
            ErrorEvent(
                layer=ErrorLayer.ML,
                category="model_load_failure",
                severity=ErrorSeverity.CRITICAL,
                message=f"Model '{model_id}' failed to load: {type(exc).__name__}: {exc}",
                metadata={"model_id": model_id, "exception_type": type(exc).__name__},
            )
        )

    def get_stats(self, model_id: str) -> dict:
        total = self._total[model_id]
        fallback = self._fallback[model_id]
        return {
            "model_id": model_id,
            "total_predictions": total,
            "fallback_count": fallback,
            "fallback_rate": round(fallback / total, 3) if total else 0.0,
        }


_ml_probe: MLProbe | None = None


def get_ml_probe() -> MLProbe:
    global _ml_probe
    if _ml_probe is None:
        _ml_probe = MLProbe()
    return _ml_probe
