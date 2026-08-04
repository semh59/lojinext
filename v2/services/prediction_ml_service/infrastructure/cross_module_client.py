"""HTTP client for prediction_ml_service's cross-module data access.

This service runs in its own container/process (Task 5, 2026-08-04) and
can no longer import v2.modules.fleet/driver/trip/analytics_executive/
ai_assistant.public directly -- those packages physically live in the
main backend's codebase. Every operation below hits a new internal
endpoint on the main backend instead (X-Internal-Token auth, see
docs/superpowers/plans/2026-07-31-prediction-ml-service-extraction.md
Task 5 Step 2b's corrected audit table for the full call-site mapping).

Retry: a small local exponential-backoff helper, not an import of
route_simulation's `with_async_retry` -- that module isn't vendored into
this service's image and the module's own docstring already says it
isn't a general-purpose platform_infra abstraction, so importing it
cross-service would be a worse coupling than a ~15-line local copy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_READ_TIMEOUT_S = 3.0
_WRITE_TIMEOUT_S = 3.0


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
                "cross_module_client retry %d/%d after %s", attempt, max_attempts, exc
            )
            await asyncio.sleep(base_delay_s * (2 ** (attempt - 1)))


def _headers() -> dict:
    secret = getattr(settings, "INTERNAL_API_SECRET", "") or ""
    return {"X-Internal-Token": secret} if secret else {}


def _base_url() -> str:
    return getattr(settings, "MAIN_BACKEND_INTERNAL_URL", "http://backend:8000")


async def _get(path: str, params: Optional[dict] = None) -> Any:
    async def _call():
        async with httpx.AsyncClient(
            base_url=_base_url(), timeout=_READ_TIMEOUT_S
        ) as client:
            resp = await client.get(path, params=params, headers=_headers())
            resp.raise_for_status()
            return resp.json()

    return await _with_retry(_call)


async def _post(path: str, json_body: dict) -> Any:
    async def _call():
        async with httpx.AsyncClient(
            base_url=_base_url(), timeout=_WRITE_TIMEOUT_S
        ) as client:
            resp = await client.post(path, json=json_body, headers=_headers())
            resp.raise_for_status()
            return resp.json()

    return await _with_retry(_call)


async def _patch(path: str, json_body: dict) -> Any:
    async def _call():
        async with httpx.AsyncClient(
            base_url=_base_url(), timeout=_WRITE_TIMEOUT_S
        ) as client:
            resp = await client.patch(path, json=json_body, headers=_headers())
            resp.raise_for_status()
            return resp.json()

    return await _with_retry(_call)


# ── fleet ─────────────────────────────────────────────────────────────────


async def get_vehicle(arac_id: int) -> Optional[dict]:
    try:
        return await _get(f"/api/v1/internal/fleet/araclar/{arac_id}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


async def get_trailer(dorse_id: int) -> Optional[dict]:
    try:
        return await _get(f"/api/v1/internal/fleet/dorseler/{dorse_id}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


# ── driver ────────────────────────────────────────────────────────────────


async def get_driver_stats(
    sofor_id: Optional[int] = None, include_elite_score: bool = True
) -> list:
    params = {"include_elite_score": include_elite_score}
    if sofor_id is not None:
        params["sofor_id"] = sofor_id
    return await _get("/api/v1/internal/driver/stats", params=params)


async def get_driver(sofor_id: int) -> Optional[dict]:
    try:
        return await _get(f"/api/v1/internal/driver/{sofor_id}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


# ── trip ──────────────────────────────────────────────────────────────────


async def get_training_data(arac_id: int, limit: int = 500) -> list:
    return await _get(
        f"/api/v1/internal/trip/training-data/{arac_id}", params={"limit": limit}
    )


async def get_all_training_data(limit: int = 2000) -> list:
    return await _get(
        "/api/v1/internal/trip/training-data-all", params={"limit": limit}
    )


async def get_sefer(sefer_id: int) -> Optional[dict]:
    try:
        return await _get(f"/api/v1/internal/trip/seferler/{sefer_id}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


async def update_tahmini_tuketim(sefer_id: int, tahmini_tuketim: float) -> None:
    await _patch(
        f"/api/v1/internal/trip/seferler/{sefer_id}/tahmini-tuketim",
        {"tahmini_tuketim": tahmini_tuketim},
    )


# ── analytics_executive ──────────────────────────────────────────────────


async def save_model_params(arac_id: int, result: dict) -> None:
    try:
        await _post(
            "/api/v1/internal/analytics/model-params",
            {"arac_id": arac_id, "result": result},
        )
    except Exception as exc:  # best-effort, same tolerance as before the move
        logger.warning("save_model_params failed (arac_id=%s): %s", arac_id, exc)


async def get_daily_summary_for_ml(
    days: int = 60, arac_id: Optional[int] = None
) -> list:
    params: dict = {"days": days}
    if arac_id is not None:
        params["arac_id"] = arac_id
    return await _get("/api/v1/internal/analytics/daily-summary", params=params)


# ── ai_assistant ──────────────────────────────────────────────────────────


async def teach(msg: str, category: str = "genel") -> None:
    try:
        await _post("/api/v1/internal/ai/teach", {"msg": msg, "category": category})
    except Exception as exc:  # best-effort, same tolerance as before the move
        logger.warning("teach failed: %s", exc)


async def ai_chat(
    messages: list,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> str:
    result = await _post(
        "/api/v1/internal/ai/chat",
        {
            "messages": messages,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )
    return result["answer"]


# ── admin_platform (training progress callback + runtime config) ───────────


async def post_training_progress(payload: dict) -> None:
    try:
        await _post("/api/v1/internal/admin/training-progress", payload)
    except Exception as exc:  # best-effort, same tolerance as before the move
        logger.warning("post_training_progress failed: %s", exc)


async def get_runtime_float(key: str, fallback: float) -> float:
    try:
        result = await _get(
            "/api/v1/internal/admin/runtime-config/float",
            params={"key": key, "fallback": fallback},
        )
        return float(result["value"])
    except Exception as exc:  # config reads must never break the caller
        logger.warning("get_runtime_float(%s) failed: %s", key, exc)
        return fallback
