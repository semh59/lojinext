"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
import traceback as _tb
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError as SAOperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware.rate_limiter import limiter
from app.api.v1.api import api_router
from app.config import settings
from app.core.errors import BusinessException
from app.core.exceptions import (
    AnomalyDetectionError,
    AuditLogError,
    DomainError,
    ExcelExportError,
    FuelCalculationError,
    ImportValidationError,
    LLMProviderError,
    MLPredictionError,
    RouteProcessingError,
)
from app.database.connection import engine
from app.infrastructure.context.correlation_middleware import CorrelationMiddleware
from app.infrastructure.context.request_context import get_correlation_id
from app.infrastructure.logging.logger import setup_logging
from app.infrastructure.middleware.body_size_middleware import MaxBodySizeMiddleware
from app.infrastructure.middleware.logging_middleware import RequestLoggingMiddleware
from app.infrastructure.middleware.rate_limit_middleware import RateLimitMiddleware

logger = setup_logging(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

# Keep fire-and-forget monitoring tasks alive until completion (prevent GC).
_bg_tasks: set[asyncio.Task] = set()


def _is_metrics_allowed(client_ip: str) -> bool:
    """Check if client IP is in the allowed list for /metrics access."""
    import ipaddress

    allowed_raw = [
        s.strip() for s in settings.METRICS_ALLOWED_IPS.split(",") if s.strip()
    ]
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in allowed_raw:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


def _sentry_before_send(event, hint):
    """Filter non-actionable events before they reach Sentry.
    Also emits to ErrorEventBus so every Sentry-captured error reaches Telegram.
    """
    # Drop monitoring stack self-test events — bunlar her startup'ta tetiklenir,
    # gerçek bir hata değil. Sentry'de gürültü yapıyordu.
    msg = event.get("message") or ""
    if "Monitoring stack self-test" in msg or "self_test" in (
        event.get("logger") or ""
    ):
        return None

    # Drop CancelledError message-only events (capture_message yoluyla
    # gelir, exc_info yoktur). Aşağıdaki isinstance check sadece
    # hint["exc_info"] varsa çalışır — mesaj bazlı drop gerek.
    if msg.startswith("CancelledError") or "CancelledError:" in msg[:60]:
        return None

    # Drop JWT anomaly messages from alarm_router.capture_message — these are
    # authentication probe/scanner events or expired tokens, not backend bugs.
    # alarm_router calls capture_message directly so exc_info check never fires.
    if msg.startswith("JWT ") and " from " in msg and " at /api/" in msg:
        return None

    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        # Drop 4xx HTTP errors — these are client mistakes, not bugs
        try:
            from starlette.exceptions import HTTPException as StarletteHTTPException

            if (
                isinstance(exc_value, StarletteHTTPException)
                and exc_value.status_code < 500
            ):
                return None
        except ImportError:
            pass

        # Drop JWT expired/invalid — kullanıcı oturumu süresi dolmuş normal davranış,
        # her gerçek expired token Sentry'ye düşmemeli.
        try:
            from jwt import ExpiredSignatureError, PyJWTError

            if isinstance(exc_value, (ExpiredSignatureError, PyJWTError)):
                return None
        except ImportError:
            pass

        # Drop intentional disabled-module HTTPException (503 Coaching off vs.)
        # Bunlar feature flag gereği fırlatılıyor, bug değil.
        try:
            from fastapi import HTTPException as FastAPIHTTPException

            if isinstance(exc_value, FastAPIHTTPException):
                detail_lc = str(getattr(exc_value, "detail", "")).lower()
                if (
                    "devre dışı" in detail_lc
                    or "devre disi" in detail_lc
                    or "disabled" in detail_lc
                ):
                    return None
                if exc_value.status_code < 500:
                    return None
        except ImportError:
            pass

        # asyncio.CancelledError — task'lar shutdown'da iptal edilir, bug değil
        try:
            import asyncio as _asyncio

            if isinstance(exc_value, _asyncio.CancelledError):
                return None
        except Exception:
            pass

        # Drop asyncpg UntranslatableCharacterError — test DB is SQL_ASCII encoded,
        # cannot store Unicode. This is an environment/deployment issue, not a bug.
        try:
            from asyncpg.exceptions import UntranslatableCharacterError

            if isinstance(exc_value, UntranslatableCharacterError):
                return None
        except ImportError:
            pass

    # Scrub PII before the event leaves the process. The PIIFilter on the logging
    # handlers does NOT cover Sentry — captured exception values, frame locals,
    # breadcrumbs and `extra` reach Sentry directly, bypassing the log filters.
    # Mirror the log scrubbing here (and before the Telegram emit below) so
    # emails/phones/TCKN and sensitive keys never leave. Defensive: never let a
    # scrub failure drop the error report.
    try:
        from app.infrastructure.security.pii_scrubber import scrub_pii

        event = scrub_pii(event)
    except Exception:
        pass

    # Emit to ErrorEventBus so AlarmRouter routes it to Telegram.
    # emit_sync is safe here: works both with and without a running event loop,
    # and AlarmRouter's 15-min dedup prevents double-notification for errors
    # already handled by the individual exception handlers.
    try:
        from app.infrastructure.monitoring.event_bus import get_event_bus
        from app.infrastructure.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        exc_info = hint.get("exc_info")
        exc_type = type(exc_info[1]).__name__ if exc_info else "SentryEvent"
        # ERROR (not WARNING) so this actually reaches Telegram: AlarmRouter only
        # forwards WARNING-severity events when NOTIFY_MIN_LEVEL=="warning", which
        # is NOT the default ("error") and is never overridden in any deployment
        # config — under WARNING, sentry_capture events silently never left the
        # digest counter uncounted, so no Sentry-captured error ever reached
        # Telegram despite this function's own docstring promising otherwise.
        # The sentry_capture → capture_message → sentry_capture loop this used to
        # guard against is prevented independently, in AlarmRouter._send_immediate's
        # `if event.category != "sentry_capture"` check — not by severity choice —
        # so ERROR is safe here regardless.
        ev = ErrorEvent(
            layer=ErrorLayer.SERVICE,
            category="sentry_capture",
            severity=ErrorSeverity.ERROR,
            message=f"{exc_type}: {event.get('message', '')}",
            trace_id=event.get("event_id", ""),
        )
        get_event_bus().emit_sync(ev)
    except Exception:
        pass

    return event


def _wire_observability(app: FastAPI) -> None:
    """Best-effort instrumentation. Each integration is independent and
    silently disabled if its package or env-var is missing."""
    if settings.SENTRY_DSN:
        try:
            import logging as _logging

            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENVIRONMENT,
                traces_sample_rate=0.05,
                integrations=[
                    # WARNING+ go to breadcrumbs; logs do NOT create Sentry events.
                    # Real exceptions are captured explicitly via capture_exception().
                    LoggingIntegration(
                        level=_logging.WARNING,
                        event_level=None,
                    ),
                ],
                before_send=_sentry_before_send,
                ignore_errors=["KeyboardInterrupt", "SystemExit"],
            )
            logger.info("Sentry initialized")
        except ImportError:
            logger.warning("SENTRY_DSN set but sentry_sdk not installed")
    else:
        if settings.ENVIRONMENT in ("prod", "production"):
            logger.warning(
                "SENTRY_DSN not set — Sentry disabled. "
                "Set SENTRY_DSN in .env for production error tracking."
            )

    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(
            app, endpoint="/metrics", include_in_schema=False
        )
        logger.info("Prometheus metrics exposed at /metrics")
    except ImportError:
        pass

    if settings.OTEL_ENABLED and settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            from opentelemetry.instrumentation.sqlalchemy import (
                SQLAlchemyInstrumentor,
            )
            from opentelemetry.sdk.resources import SERVICE_NAME, Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            # Prior to this, FastAPIInstrumentor.instrument_app() ran against the
            # global no-op TracerProvider — spans were created and immediately
            # discarded, never exported anywhere (Tier E madde 25).
            resource = Resource.create({SERVICE_NAME: "lojinext-backend"})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)

            FastAPIInstrumentor.instrument_app(app)
            SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
            logger.info(
                "OpenTelemetry tracing enabled (endpoint=%s)",
                settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            )
        except ImportError:
            logger.warning("OTEL_ENABLED but opentelemetry not installed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting LojiNext (%s)", settings.ENVIRONMENT)
    from app.infrastructure.resilience.shutdown import register_shutdown_handlers

    register_shutdown_handlers()
    from app.infrastructure.monitoring.event_bus import get_event_bus

    bus = get_event_bus()
    bus.start()

    from app.infrastructure.background.celery_app import celery_app as _celery
    from app.infrastructure.monitoring.activate import activate_all_probes

    activate_all_probes(engine, _celery)

    # Domain event-bus subscribers — these were previously defined but never
    # registered anywhere (dedektif denetimi, 2026-07-16): bildirim kuralları,
    # RAG auto-sync, ML auto-retrain trigger, ve cache invalidation hiçbiri
    # prod'da tetiklenmiyordu. Her biri kendi try/except'i içinde — biri
    # başarısız olursa diğerlerini veya app startup'ı engellemez.
    try:
        from app.infrastructure.cache.cache_invalidation import (
            setup_cache_invalidation,
        )

        setup_cache_invalidation()
    except Exception as exc:  # pragma: no cover
        logger.warning("Cache invalidation listener setup failed: %s", exc)

    try:
        from v2.modules.prediction_ml.public import get_model_training_handler

        get_model_training_handler().setup()
    except Exception as exc:  # pragma: no cover
        logger.warning("ModelTrainingHandler setup failed: %s", exc)

    try:
        from v2.modules.prediction_ml.public import get_physics_handler

        get_physics_handler().register()
    except Exception as exc:  # pragma: no cover
        logger.warning("PhysicsRecalculationHandler registration failed: %s", exc)

    try:
        from v2.modules.notification.public import register_handlers

        register_handlers()
    except Exception as exc:  # pragma: no cover
        logger.warning("Notification event handlers registration failed: %s", exc)

    try:
        from v2.modules.ai_assistant.public import get_rag_sync_service

        await get_rag_sync_service().initialize()
    except Exception as exc:  # pragma: no cover
        logger.warning("RAGSyncService initialization failed: %s", exc)

    # ML predictor warm-up — aktif tüm araç modellerini önceden initialize et
    # ki ilk POST /trips ML cold-start için 4-10sn beklemesin (LRU cache miss).
    # Vehicle 0 (general fallback) her zaman dahil; aktif araç id'leri DB'den.
    try:
        import asyncio as _asyncio

        from v2.modules.prediction_ml.public import get_ensemble_service

        async def _warmup_all_predictors() -> None:
            ids: list[int] = [0]  # general/fallback
            try:
                from sqlalchemy import select as _select

                from app.database.connection import AsyncSessionLocal
                from app.database.models import Arac

                async with AsyncSessionLocal() as session:
                    rows = await session.execute(
                        _select(Arac.id).where(Arac.aktif.is_(True))
                    )
                    ids.extend(r[0] for r in rows.all())
            except Exception as exc:
                logger.debug("Arac fetch for warm-up failed: %s", exc)

            def _init(arac_id: int) -> None:
                try:
                    get_ensemble_service().get_predictor(arac_id)
                except Exception as exc:  # pragma: no cover
                    logger.debug("Predictor warm-up %s skipped: %s", arac_id, exc)

            for arac_id in ids:
                await _asyncio.to_thread(_init, arac_id)
            logger.info("ML predictor warm-up complete for %d models", len(ids))

        _task = _asyncio.create_task(_warmup_all_predictors())
        _bg_tasks.add(_task)
        _task.add_done_callback(_bg_tasks.discard)
    except Exception as exc:  # pragma: no cover
        logger.warning("ML warm-up scheduling failed: %s", exc)

    try:
        yield
    finally:
        await bus.stop()

        # Sentry LOJINEXT-1C5: cancel + await any in-flight fire-and-forget
        # tasks (alarm_router's Telegram notify_error, this module's ML
        # warm-up) before disposing the engine/closing the loop — otherwise
        # a task still mid-DNS-lookup when the loop closes leaves its
        # executor Future's eventual result with nowhere to go, surfacing
        # as asyncio's "Future exception was never retrieved".
        from app.infrastructure.monitoring.alarm_router import drain_bg_tasks

        await drain_bg_tasks()
        pending = [t for t in list(_bg_tasks) if not t.done()]
        if pending:
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        from app.core.container import get_container

        get_container().shutdown()
        await engine.dispose()
        logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.1.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

# Wire slowapi limiter so @limiter.limit() decorators are active
app.state.limiter = limiter
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
except ImportError:
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "X-Correlation-ID",
        "X-Idempotency-Key",
    ],
)


@app.middleware("http")
async def metrics_ip_guard(request: Request, call_next):
    """Restrict /metrics to internal IPs only."""
    if request.url.path == "/metrics":
        client_ip = request.client.host if request.client else ""
        # Behind a reverse proxy the direct connection is always 127.0.0.1.
        # Use X-Forwarded-For (set by nginx from $remote_addr) to get the
        # real caller IP so the whitelist actually filters external requests.
        if client_ip in ("127.0.0.1", "::1"):
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()
        if not _is_metrics_allowed(client_ip):
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "FORBIDDEN", "message": "Access denied"}},
            )
    return await call_next(request)


# Reject oversized request bodies early (DoS backstop, before buffering).
app.add_middleware(
    MaxBodySizeMiddleware, max_body_bytes=settings.MAX_REQUEST_BODY_BYTES
)

# Per-IP global rate limiter (60 req/min in prod; skipped in dev/test)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# Structured request/response logging (inner: reads correlation ID after it's set)
app.add_middleware(RequestLoggingMiddleware)

# Correlation ID tracking (outermost: must set ID before logging middleware reads it)
# add_middleware inserts at index 0, so the last-added becomes outermost.
app.add_middleware(CorrelationMiddleware)


# ── Unified error envelope ────────────────────────────────────────────────────
# All error responses follow: {"error": {"code": str, "message": str, "trace_id": str}}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = get_correlation_id()
    if exc.status_code == 403:
        # 2026-07-01 prod-grade denetimi P1: izin reddi (403) denemeleri
        # önceden hiçbir yerde `admin_audit_log`'a düşmüyordu — sadece
        # dosya loguna (varsa) yazılıyordu. Merkezi handler'da tek noktadan
        # yakalanır (security_service.py'nin senkron classmethod'larını
        # veya require_permissions dependency'sini async'e çevirip her
        # çağrı noktasını değiştirmek yerine — çok daha büyük bir blast
        # radius olurdu). Best-effort: audit DB yazımı asıl 403 yanıtını
        # asla bloklamaz/bozmaz.
        try:
            from app.infrastructure.audit.audit_logger import log_audit_event
            from v2.modules.auth_rbac.public import jwt_handler

            sub = None
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                try:
                    payload = jwt_handler.decode_token(auth_header[7:])
                    sub = payload.get("sub")
                except Exception:
                    sub = None
            message = (
                exc.detail.get("message")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            )
            await log_audit_event(
                action="authz.forbidden",
                module="security",
                entity_id=str(request.url.path),
                new_value={"detail": message, "sub": sub, "method": request.method},
                basarili=False,
            )
        except Exception as audit_exc:  # pragma: no cover
            logger.warning("403 audit log failed: %s", audit_exc)
    if exc.status_code >= 500:
        from app.infrastructure.monitoring import aemit
        from app.infrastructure.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        message = (
            exc.detail.get("message")
            if isinstance(exc.detail, dict)
            else str(exc.detail)
        )
        await aemit(
            ErrorEvent(
                layer=ErrorLayer.API,
                category=f"http_{exc.status_code}",
                severity=ErrorSeverity.ERROR,
                message=str(message),
                path=str(request.url.path),
                trace_id=trace_id,
            )
        )

    # Always wrap into the unified envelope. If a caller passed a structured dict
    # (legacy shape), surface its message under `error.message` and keep the dict
    # under `error.details` so clients can read both.
    if isinstance(exc.detail, dict):
        message = (
            exc.detail.get("error_message")
            or exc.detail.get("message")
            or str(exc.detail)
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": message,
                    "trace_id": trace_id,
                    "details": exc.detail,
                }
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "trace_id": trace_id,
            }
        },
    )


def _sanitize_validation_errors(errors: list) -> list:
    """Pydantic ctx dict'indeki JSON-unsafe tipleri (Decimal, Exception, set…) str'ye çevirir."""
    from decimal import Decimal

    _UNSAFE = (Decimal, set, frozenset, Exception, BaseException)

    def _safe(v):
        return str(v) if isinstance(v, _UNSAFE) else v

    result = []
    for e in errors:
        e = dict(e)
        if "ctx" in e:
            e["ctx"] = {k: _safe(v) for k, v in e["ctx"].items()}
        result.append(e)
    return result


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = get_correlation_id()
    errors = _sanitize_validation_errors(list(exc.errors()))
    message = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "trace_id": trace_id,
                "details": errors,
            }
        },
    )


# HTTP mapping tablosu — en spesifik tip önce eşleşir
_DOMAIN_ERROR_STATUS: dict[type[DomainError], int] = {
    FuelCalculationError: 422,
    ImportValidationError: 422,
    ExcelExportError: 422,
    RouteProcessingError: 422,  # Default; can be overridden to 424 if provider_status is set
    MLPredictionError: 503,
    AnomalyDetectionError: 503,
    LLMProviderError: 503,
    AuditLogError: 500,
}


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """DomainError alt sınıflarını tipe göre doğru HTTP koduna dönüştürür."""
    trace_id = get_correlation_id()
    status_code = 500
    for exc_type, code in _DOMAIN_ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    # Special handling for RouteProcessingError with provider_status
    if isinstance(exc, RouteProcessingError):
        if hasattr(exc, "provider_status") and exc.provider_status in (403, 404, 429):
            status_code = 424  # Failed Dependency

    if status_code >= 500:
        logger.error(
            "Domain error trace_id=%s path=%s type=%s: %s",
            trace_id,
            request.url.path,
            type(exc).__name__,
            exc,
        )
        from app.infrastructure.monitoring import aemit
        from app.infrastructure.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        await aemit(
            ErrorEvent(
                layer=ErrorLayer.SERVICE,
                category=type(exc).__name__.lower(),
                severity=ErrorSeverity.ERROR,
                message=f"{type(exc).__name__}: {exc}",
                path=str(request.url.path),
                trace_id=trace_id,
                metadata=exc.to_dict(),
            )
        )

    error_code = type(exc).__name__.upper().replace("ERROR", "_ERROR")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc),
                "trace_id": trace_id,
                "details": exc.to_dict(),
            }
        },
    )


@app.exception_handler(SAOperationalError)
async def db_operational_error_handler(request: Request, exc: SAOperationalError):
    """DB connection drops (asyncpg ConnectionDoesNotExistError etc.) → 503."""
    trace_id = get_correlation_id()
    logger.error(
        "DB operational error trace_id=%s path=%s: %s",
        trace_id,
        request.url.path,
        exc,
    )
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        pass
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import (
        ErrorEvent,
        ErrorLayer,
        ErrorSeverity,
    )

    await aemit(
        ErrorEvent(
            layer=ErrorLayer.DB,
            category="db_unavailable",
            severity=ErrorSeverity.CRITICAL,
            message=f"DB unavailable: {type(exc).__name__}: {exc}",
            path=str(request.url.path),
            trace_id=trace_id,
        )
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": "Veritabanı bağlantısı geçici olarak kesildi. Lütfen tekrar deneyin.",
                "trace_id": trace_id,
            }
        },
    )


@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """BusinessException → 400 with canonical envelope."""
    trace_id = get_correlation_id()
    logger.warning("Business error trace_id=%s: %s", trace_id, exc.message)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "trace_id": trace_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = get_correlation_id()
    logger.error(
        "Unhandled exception trace_id=%s path=%s: %s",
        trace_id,
        request.url.path,
        exc,
        exc_info=True,
    )
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        pass
    # _sentry_before_send also emits to ErrorEventBus, but aemit is the
    # authoritative path — AlarmRouter's 15-min dedup prevents double-notification.
    from app.infrastructure.monitoring import aemit
    from app.infrastructure.monitoring.models import (
        ErrorEvent,
        ErrorLayer,
        ErrorSeverity,
    )

    await aemit(
        ErrorEvent(
            layer=ErrorLayer.SERVICE,
            category="unhandled_exception",
            severity=ErrorSeverity.CRITICAL,
            message=f"{type(exc).__name__}: {exc}",
            path=str(request.url.path),
            trace_id=trace_id,
            stack_trace=_tb.format_exc(),
        )
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "trace_id": trace_id,
            }
        },
    )


_wire_observability(app)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    return {"message": "LojiNext API", "docs": "/docs", "version": "2.1.0"}


# ── Health endpoints (liveness + readiness) ───────────────────────────────────


@app.get("/health/liveness", include_in_schema=False, tags=["health"])
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe — always 200 as long as process is running."""
    return {"status": "ok"}


@app.get("/health/readiness", include_in_schema=False, tags=["health"])
async def readiness() -> JSONResponse:
    """Kubernetes readiness probe — checks DB + Redis connectivity."""
    import asyncio

    checks: dict[str, str] = {}

    # DB check
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        logger.warning("Readiness DB check failed: %s", e)
        checks["db"] = "error"

    # Redis check
    try:
        from app.infrastructure.cache.redis_pubsub import get_redis_val

        await asyncio.wait_for(get_redis_val("__ping__"), timeout=1.0)
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning("Readiness Redis check failed: %s", e)
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )


@app.get("/.well-known/jwks.json", include_in_schema=False)
async def jwks() -> dict[str, Any]:
    """RS256 JWKS endpoint (only meaningful when ALGORITHM=RS256)."""
    from v2.modules.auth_rbac.public import get_jwks

    return get_jwks()
