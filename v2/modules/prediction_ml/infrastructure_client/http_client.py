"""HTTP client facing the standalone prediction_ml_service.

The ensemble/ML prediction pipeline itself moved out of this codebase
(Task 5, 2026-08-04) -- `PredictionService` here is a thin facade with the
exact same method names/signatures every one of the 14 real consumer
files already calls, so none of them need to change. Internally it just
POSTs to the new service and returns its JSON response.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

import httpx

from app.config import settings
from v2.modules.platform_infra.resilience.circuit_breaker import (
    CircuitBreakerRegistry,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# model_warmup.py's own docstring documents cold-start ensemble prediction
# taking up to "4-10sn" (LRU predictor-cache miss) -- 5.0s here would clip
# that ceiling on nearly every cold call, tripping the circuit breaker on
# genuinely successful-but-slow responses rather than real failures
# (caught live via real-backend CI tests once this HTTP client actually
# had a live service behind it, 2026-08-05). Training a full ensemble
# (train_xgboost_model) is slower still than a single prediction, so the
# same generous ceiling applies to every call through this client.
_TIMEOUT_S = 30.0

# Not JSON-serializable and meaningless across a process boundary -- the
# remote service re-fetches via its own cross_module_client if unset.
_STRIP_KEYS = ("_arac_obj", "_sofor_obj", "_dorse_obj")


async def _with_retry(
    coro_fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 0.5,
) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await coro_fn()
        except (httpx.RequestError, asyncio.TimeoutError) as exc:
            if attempt >= max_attempts:
                raise
            logger.warning(
                "prediction_ml http_client retry %d/%d after %s",
                attempt,
                max_attempts,
                exc,
            )
            await asyncio.sleep(base_delay_s * (2 ** (attempt - 1)))


def _headers() -> dict:
    secret = settings.INTERNAL_API_SECRET
    return {"X-Internal-Token": secret} if secret else {}


async def _post(path: str, payload: Dict[str, Any]) -> Any:
    body = {k: v for k, v in payload.items() if k not in _STRIP_KEYS}

    async def _call():
        async with httpx.AsyncClient(
            base_url=settings.PREDICTION_ML_SERVICE_URL, timeout=_TIMEOUT_S
        ) as client:
            resp = await client.post(path, json=body, headers=_headers())
            resp.raise_for_status()
            return resp.json()

    breaker = await CircuitBreakerRegistry.get("prediction_ml_service")
    return await breaker.call(lambda: _with_retry(_call))


class PredictionService:
    """HTTP-client facade -- same method names/signatures as before Task 5."""

    async def predict_consumption(self, **kwargs) -> Dict[str, Any]:
        try:
            return await _post("/predict", kwargs)
        except Exception as exc:
            logger.warning("predict_consumption remote call failed: %s", exc)
            return {
                "status": "error",
                "code": "service_unavailable",
                "message": "prediction_ml_service unreachable",
            }

    async def explain_consumption(self, **kwargs) -> Dict[str, Any]:
        return await _post("/predict/explain", kwargs)

    async def train_xgboost_model(
        self, arac_id: int, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        return await _post(f"/train/{arac_id}", {"user_id": user_id})


_prediction_service: Optional[PredictionService] = None


def get_prediction_service() -> PredictionService:
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionService()
    return _prediction_service
