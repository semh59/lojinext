"""
Server-Sent Events endpoint for real-time error monitoring.
Uses asyncpg LISTEN/NOTIFY directly (not SQLAlchemy pool) so the
connection stays open for the lifetime of the SSE stream.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import get_current_active_admin
from app.config import settings
from v2.modules.admin_platform.schemas import SseTokenResponse
from v2.modules.auth_rbac.public import Kullanici
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.schemas.api_responses import SSE_RESPONSES

router = APIRouter()
logger = get_logger(__name__)

_KEEPALIVE_INTERVAL = 25  # seconds — browsers disconnect SSE after ~30s without data

# ── Connection cap ────────────────────────────────────────────────────────────
_SSE_SEMAPHORE = asyncio.Semaphore(20)  # max 20 concurrent SSE streams


async def _sse_generator(user_id: int, request: Request) -> AsyncGenerator[str, None]:
    """
    Open a dedicated asyncpg connection, LISTEN on error_events_channel,
    and yield SSE-formatted messages. Sends keepalive comments every 25s.
    """
    import asyncpg
    from sqlalchemy.engine.url import make_url

    # NOTE (MINOR-010 incelendi): locked() ile acquire() arasında await yok;
    # asyncio tek-thread modelinde araya başka coroutine giremez ve slot varsa
    # acquire() süspend olmadan tamamlanır. Dolayısıyla gerçek bir TOCTOU yok.
    if _SSE_SEMAPHORE.locked():
        yield 'event: error\ndata: {"error": "too_many_streams"}\n\n'
        return

    await _SSE_SEMAPHORE.acquire()

    url = make_url(settings.DATABASE_URL)
    dsn = str(url.set(drivername="postgresql"))

    conn: asyncpg.Connection | None = None
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)

    def _notify_callback(conn_ref, pid, channel, payload):  # type: ignore[type-arg]
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # Slow consumer — drop

    try:
        conn = await asyncpg.connect(dsn=dsn)
        await conn.add_listener("error_events_channel", _notify_callback)
        logger.info("SSE error stream opened for user %d", user_id)

        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(
                    queue.get(), timeout=_KEEPALIVE_INTERVAL
                )
                try:
                    data = json.loads(payload)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    logger.debug("SSE: non-JSON payload dropped: %s", payload[:100])
                except Exception as exc:
                    logger.debug("SSE: payload processing error: %s", exc)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.warning("SSE stream error for user %d: %s", user_id, exc)
        yield 'event: error\ndata: {"error": "stream_error"}\n\n'
    finally:
        _SSE_SEMAPHORE.release()
        if conn and not conn.is_closed():
            try:
                await conn.remove_listener("error_events_channel", _notify_callback)
                await conn.close()
            except Exception:
                pass
        logger.info("SSE error stream closed for user %d", user_id)


# ── POST /error-stream-token ──────────────────────────────────────────────────


@router.post("/error-stream-token", response_model=SseTokenResponse)
async def create_sse_token(
    current_user: Kullanici = Depends(get_current_active_admin),
):
    """
    Issue a short-lived one-time SSE token for EventSource authentication.
    Admin only. Token is valid for 90 seconds and consumed on first use.
    """
    from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

    token = str(uuid.uuid4())
    mgr = get_pubsub_manager()

    redis = mgr.redis
    key = f"sse_token:{token}"
    payload = json.dumps({"user_id": current_user.id})

    if redis is not None:
        await redis.set(key, payload, ex=90)
    else:
        # Memory fallback (no real TTL, but short-lived by design)
        await mgr.set(key, {"user_id": current_user.id}, expire=90)

    return {"token": token, "expires_in": 90}


# ── GET /error-stream ─────────────────────────────────────────────────────────


@router.get(
    "/error-stream",
    responses=SSE_RESPONSES,
    response_model=None,
    response_class=StreamingResponse,
)
async def error_stream(request: Request):
    """
    SSE stream of live error_events. Admin only.
    Auth via ?token=<one-time SSE token> query param
    (issued by POST /error-stream-token).
    Tokens are short-lived (90s), one-time-use, and stored in Redis.

    Event format: data: {"id": 1, "layer": "db", "severity": "critical", ...}
    Keepalive:    : keepalive
    """
    from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

    token = request.query_params.get("token", "")
    if not token:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "UNAUTHORIZED"}},
        )

    user_id: int | None = None

    # ── One-time Redis token path ─────────────────────────────────────────────
    mgr = get_pubsub_manager()
    redis = mgr.redis
    key = f"sse_token:{token}"

    raw: str | None = None
    if redis is not None:
        # pubsub redis decode_responses=True → str döner; redis-py stub'ı
        # decode moduna bakmadan bytes tipliyor.
        raw = await redis.get(key)  # type: ignore[assignment]
    else:
        cached = await mgr.get(key)
        if cached is not None:
            raw = json.dumps(cached)

    if raw is None:
        logger.warning("SSE auth failed: token not found or expired (key=%s)", key)
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_OR_EXPIRED_TOKEN"}},
        )

    try:
        data = json.loads(raw)
        user_id = int(data["user_id"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("SSE auth failed: malformed token payload: %s", exc)
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_TOKEN"}},
        )

    # One-time use — delete immediately after reading
    if redis is not None:
        await redis.delete(key)
    else:
        await mgr.delete(key)

    # Re-verify admin from DB
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from v2.modules.auth_rbac.public import Kullanici as KullaniciModel
    from v2.modules.platform_infra.database.connection import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KullaniciModel)
                .options(selectinload(KullaniciModel.rol))
                .where(KullaniciModel.id == user_id)
            )
            db_user = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("SSE auth DB lookup failed for user %d: %s", user_id, exc)
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_OR_EXPIRED_TOKEN"}},
        )

    if db_user is None or not db_user.aktif:
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "FORBIDDEN"}},
        )

    from v2.modules.auth_rbac.public import Permission, SecurityService

    if not SecurityService.has_permission(db_user, Permission.ADMIN):
        return JSONResponse(
            status_code=403,
            content={"error": {"code": "FORBIDDEN"}},
        )

    assert user_id is not None  # guaranteed by token path above

    return StreamingResponse(
        _sse_generator(user_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
