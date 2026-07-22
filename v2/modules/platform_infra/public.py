"""Public surface of the platform_infra "module".

This is NOT a business module — it is the genuinely cross-cutting runtime
infrastructure (Redis cache/pub-sub, domain + error event buses, the DI
composition root, circuit breaker/rate limiter, DB engine/session bootstrap,
observability probes, ASGI middleware, structured logging, audit logging,
Celery/background jobs, PII crypto, shared WebSocket plumbing) left over
once all 15 business modules + shared_kernel were carved out of ``app/``
(dalga 17, `TASKS/modules/platform-infra.md`).

Unlike ``shared_kernel`` — which holds domain-PATTERN code that other
modules' code directly subclasses/composes (``BaseRepository``,
``UnitOfWork``, ...) and therefore has NO enforced public-surface
contract — platform_infra holds RUNTIME SERVICES that modules merely
*call*. So this module DOES get its own
``public-surface-only-platform_infra`` import-linter contract: every
business module's ``application`` layer must import platform_infra symbols
from here, not by reaching into ``cache/``, ``events/``, ``monitoring/``,
``resilience/``, ``middleware/``, ``database/``, ``container.py``,
``security/``, ``context/``, ``logging/``, ``audit/``, ``background/``, or
``websocket/`` directly.

**Naming collision**: ``events.event_bus.get_event_bus`` (the domain
``EventBus``, used by ``@publishes``/business modules) and
``monitoring.event_bus.get_event_bus`` (the ``ErrorEventBus``, used by
main.py's lifespan + Sentry hook) share a name but are two different
classes at two different paths. Resolved below via
``import ... as get_error_event_bus`` — application-layer code that needs
the domain event bus imports ``get_event_bus``; code that needs the error/
alarm bus imports ``get_error_event_bus`` (or, more commonly, the
``emit``/``aemit`` wrappers, which never require importing either
``get_event_bus`` directly).
"""

from v2.modules.platform_infra.audit.audit_logger import (
    audit_log,
    audit_logger,
    log_audit_event,
)
from v2.modules.platform_infra.background.job_manager import (
    AsyncJobStatus,
    BackgroundJobManager,
    get_job_manager,
)
from v2.modules.platform_infra.cache.cache_manager import (
    CacheManager,
    get_cache_manager,
)
from v2.modules.platform_infra.cache.redis_cache import RedisCache, get_redis_cache
from v2.modules.platform_infra.cache.redis_client_factory import (
    get_async_redis_client,
    get_celery_broker_transport_options,
    get_celery_broker_url,
    get_celery_result_backend_url,
    get_sync_redis_client,
)
from v2.modules.platform_infra.cache.redis_pubsub import (
    RedisPubSubManager,
    get_pubsub_manager,
    get_redis_val,
    set_redis_val,
)
from v2.modules.platform_infra.container import (
    Container,
    get_container,
    reset_container,
)
from v2.modules.platform_infra.context.correlation_middleware import (
    CorrelationMiddleware,
)
from v2.modules.platform_infra.context.request_context import (
    clear_context,
    get_correlation_id,
    get_request_path,
    set_correlation_id,
    set_request_path,
)
from v2.modules.platform_infra.database.backup_manager import DatabaseBackupManager
from v2.modules.platform_infra.database.connection import (
    AsyncSessionLocal,
    engine,
    get_connection,
    get_db,
    get_sync_session,
    session_scope,
)
from v2.modules.platform_infra.database.init_db import init_primary_data
from v2.modules.platform_infra.events.event_bus import (
    Event,
    EventBus,
    EventType,
    get_event_bus,
    publishes,
)
from v2.modules.platform_infra.logging.logger import (
    get_audit_logger,
    get_logger,
    setup_logging,
)
from v2.modules.platform_infra.metrics import (
    telegram_belge_ocr_total,
    telegram_belge_upload_total,
    trip_approval_total,
)
from v2.modules.platform_infra.middleware.body_size_middleware import (
    MaxBodySizeMiddleware,
)
from v2.modules.platform_infra.middleware.logging_middleware import (
    RequestLoggingMiddleware,
)
from v2.modules.platform_infra.middleware.rate_limit_middleware import (
    RateLimitMiddleware,
    get_real_client_ip,
)
from v2.modules.platform_infra.monitoring import aemit, emit
from v2.modules.platform_infra.monitoring.activate import activate_all_probes
from v2.modules.platform_infra.monitoring.alarm_router import (
    AlarmRouter,
    drain_bg_tasks,
    get_alarm_router,
)
from v2.modules.platform_infra.monitoring.celery_probe import (
    check_beat_health,
    setup_celery_probe,
)
from v2.modules.platform_infra.monitoring.db_probe import (
    get_query_count,
    reset_query_counter,
    reset_recent_queries,
    setup_db_probe,
)
from v2.modules.platform_infra.monitoring.event_bus import (
    ErrorEventBus,
    reset_event_bus,
)
from v2.modules.platform_infra.monitoring.event_bus import (
    get_event_bus as get_error_event_bus,
)
from v2.modules.platform_infra.monitoring.external_api_probe import (
    emit_network_error,
    get_monitored_client,
)
from v2.modules.platform_infra.monitoring.models import (
    ErrorEvent,
    ErrorLayer,
    ErrorSeverity,
    make_fingerprint,
)
from v2.modules.platform_infra.monitoring.security_probe import (
    BruteForceDetector,
    RBACViolationTracker,
    emit_jwt_anomaly,
    get_brute_force_detector,
    get_rbac_tracker,
)
from v2.modules.platform_infra.monitoring.service_probe import (
    assert_invariant,
    intentional_fallback,
    monitor_errors,
    setup_asyncio_exception_handler,
)
from v2.modules.platform_infra.monitoring.silent_fallback_probe import (
    SilentFallbackProbe,
    get_silent_fallback_probe,
    record_silent_fallback,
)
from v2.modules.platform_infra.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_protected,
)
from v2.modules.platform_infra.resilience.rate_limiter import (
    AsyncRateLimiter,
    RateLimiterDependency,
    RateLimiterRegistry,
    rate_limited,
)
from v2.modules.platform_infra.resilience.shutdown import (
    is_stopping,
    register_shutdown_handlers,
)
from v2.modules.platform_infra.security.pii_encryption import (
    blind_index,
    decrypt_pii,
    decrypt_pii_or,
    encrypt_pii,
    trigram_blind_indexes,
)
from v2.modules.platform_infra.security.pii_scrubber import scrub_pii

# NOT: `background.celery_app` ve `websocket.ws_auth` KASITLI OLARAK burada
# eager import edilmiyor — ikisi de kendi modül gövdelerinde business-modül
# zincirlerine (celery_app.py: 12 modülün task dosyası; ws_auth.py:
# auth_rbac.public -> auth_service.py) eager import ile giriyor. public.py
# ise BAŞTA (application-katmanı dosyalarının en üstünde) import ediliyor —
# bu iki dosyayı da buraya eklemek `platform_infra.public` yüklenirken
# `auth_service.py`/`knowledge_base.py` gibi application dosyalarının HENÜZ
# TAMAMLANMAMIŞ `platform_infra.public`'i geri import etmeye çalışmasına
# (partially-initialized module ImportError) yol açtı — canlı olarak
# `pytest` koşumunda yakalandı. Hiçbir application-katmanı dosyası zaten bu
# ikisini KULLANMIYOR (yalnız main.py/admin_platform+notification'ın api/
# infrastructure katmanları — kontratın kapsamı dışı); o tüketiciler kendi
# doğrudan yollarından (`v2.modules.platform_infra.background.celery_app`,
# `v2.modules.platform_infra.websocket.{connection_manager,ws_auth}`)
# import etmeye devam eder.

__all__ = [
    # cache
    "CacheManager",
    "get_cache_manager",
    "RedisCache",
    "get_redis_cache",
    "get_async_redis_client",
    "get_sync_redis_client",
    "get_celery_broker_url",
    "get_celery_broker_transport_options",
    "get_celery_result_backend_url",
    "RedisPubSubManager",
    "get_pubsub_manager",
    "get_redis_val",
    "set_redis_val",
    # domain event bus
    "Event",
    "EventBus",
    "EventType",
    "get_event_bus",
    "publishes",
    # DI composition root
    "Container",
    "get_container",
    "reset_container",
    # request context
    "CorrelationMiddleware",
    "clear_context",
    "get_correlation_id",
    "get_request_path",
    "set_correlation_id",
    "set_request_path",
    # database
    "AsyncSessionLocal",
    "engine",
    "get_connection",
    "get_db",
    "get_sync_session",
    "session_scope",
    "init_primary_data",
    "DatabaseBackupManager",
    # structured logging
    "get_logger",
    "get_audit_logger",
    "setup_logging",
    # metrics
    "trip_approval_total",
    "telegram_belge_upload_total",
    "telegram_belge_ocr_total",
    # ASGI middleware
    "MaxBodySizeMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "get_real_client_ip",
    # error/alarm monitoring
    "emit",
    "aemit",
    "activate_all_probes",
    "AlarmRouter",
    "get_alarm_router",
    "drain_bg_tasks",
    "check_beat_health",
    "setup_celery_probe",
    "get_query_count",
    "reset_query_counter",
    "reset_recent_queries",
    "setup_db_probe",
    "ErrorEventBus",
    "get_error_event_bus",
    "reset_event_bus",
    "emit_network_error",
    "get_monitored_client",
    "ErrorEvent",
    "ErrorLayer",
    "ErrorSeverity",
    "make_fingerprint",
    "BruteForceDetector",
    "RBACViolationTracker",
    "emit_jwt_anomaly",
    "get_brute_force_detector",
    "get_rbac_tracker",
    "assert_invariant",
    "intentional_fallback",
    "monitor_errors",
    "setup_asyncio_exception_handler",
    "SilentFallbackProbe",
    "get_silent_fallback_probe",
    "record_silent_fallback",
    # resilience
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "circuit_protected",
    "AsyncRateLimiter",
    "RateLimiterDependency",
    "RateLimiterRegistry",
    "rate_limited",
    "is_stopping",
    "register_shutdown_handlers",
    # security / PII
    "blind_index",
    "decrypt_pii",
    "decrypt_pii_or",
    "encrypt_pii",
    "trigram_blind_indexes",
    "scrub_pii",
    # audit
    "audit_log",
    "audit_logger",
    "log_audit_event",
    # background jobs
    "AsyncJobStatus",
    "BackgroundJobManager",
    "get_job_manager",
]
