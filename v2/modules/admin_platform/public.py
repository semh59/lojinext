"""Public surface of the admin_platform module.

Other modules that need to call into admin_platform must import from here,
not from ``application/``, ``domain/``, or ``infrastructure/`` directly (see
TASKS/modules/admin-platform.md and .importlinter's forbidden-imports
contract).

No class-exception service objects here except ``HealthService`` (genuine
mutable state: ``start_time``, ``_bg_tasks`` GC-protection set — same
category as trip's ``stats_refresh.py::_bg_stats_tasks``). Every other
former ``*Service`` class (``KonfigService``, ``AdminAuditService``,
``InternalService``) was dissolved to free functions per B.1 — none had
real mutable state.
"""

from v2.modules.admin_platform.api.admin_ws_routes import training_ws_manager
from v2.modules.admin_platform.application.admin_audit_service import (
    log_action,
    log_config_change,
    log_login,
)
from v2.modules.admin_platform.application.error_events import (
    get_error_stats,
    get_trace_chain,
    list_error_events,
    resolve_error_event,
)
from v2.modules.admin_platform.application.health_service import (
    HealthService,
    get_health_service,
)
from v2.modules.admin_platform.application.idempotency_service import (
    IdempotencyKeyConflictError,
    IdempotencyKeyInProgressError,
    finalize_response,
    release_reservation,
    reserve_or_get_cached,
)
from v2.modules.admin_platform.application.integration_secrets import (
    BOT_TOKEN_SERVICES,
    KNOWN_SERVICES,
    IntegrationStatus,
    get_integration_secret,
    get_integration_statuses,
    set_integration_secret,
)
from v2.modules.admin_platform.application.konfig_service import (
    get_all_by_group,
    get_all_configs,
    get_config_history,
    get_config_value,
    update_config,
)
from v2.modules.admin_platform.application.runtime_config import (
    get_runtime_float,
    get_runtime_value,
)
from v2.modules.admin_platform.application.telegram_bridge import (
    get_coaching_snapshot,
    get_seferler,
    get_sofor_by_telegram_id,
    kaydet_belge,
    olustur_pdf,
    report_driver_breakdown,
)
from v2.modules.admin_platform.infrastructure.models import (
    AdminAuditLog,
    EntegrasyonAyari,
    IdempotencyKey,
    KonfigGecmis,
    SistemKonfig,
)
from v2.modules.admin_platform.infrastructure.repository import (
    AdminConfigRepository,
    get_admin_config_repo,
)

__all__ = [
    "AdminConfigRepository",
    # ORM (dalga 16 task #58 — database/models.py bölünmesi)
    "AdminAuditLog",
    "EntegrasyonAyari",
    "IdempotencyKey",
    "KonfigGecmis",
    "SistemKonfig",
    "BOT_TOKEN_SERVICES",
    "HealthService",
    "IdempotencyKeyConflictError",
    "IdempotencyKeyInProgressError",
    "IntegrationStatus",
    "KNOWN_SERVICES",
    "finalize_response",
    "get_admin_config_repo",
    "get_all_by_group",
    "get_all_configs",
    "get_coaching_snapshot",
    "get_config_history",
    "get_config_value",
    "get_error_stats",
    "get_health_service",
    "get_integration_secret",
    "get_integration_statuses",
    "get_runtime_float",
    "get_runtime_value",
    "get_seferler",
    "get_sofor_by_telegram_id",
    "get_trace_chain",
    "kaydet_belge",
    "list_error_events",
    "log_action",
    "log_config_change",
    "log_login",
    "olustur_pdf",
    "release_reservation",
    "report_driver_breakdown",
    "reserve_or_get_cached",
    "resolve_error_event",
    "set_integration_secret",
    "training_ws_manager",
    "update_config",
]
