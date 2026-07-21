"""Public surface of the shared_kernel "module".

This is NOT a business module — it is what's left over once all 15 business
modules were carved out of ``app/``: genuinely cross-cutting code with no
single owning module (ORM base class, domain exception hierarchy, the UoW,
the generic repository base, security validators, generic response
envelopes). There is no ``public-surface-only-shared_kernel`` import-linter
contract (the whole point is that everyone imports it freely) — this file
exists only so the intentional public surface is documented in one place
instead of every consumer reaching into ``infrastructure/``/``schemas/``/
``utils/`` at random (see ``TASKS/modules/shared-kernel.md`` madde 0
düzeltme #5).
"""

from v2.modules.shared_kernel.domain.base_entity import BaseEntity
from v2.modules.shared_kernel.errors import (
    BusinessException,
    DiagnosticHelper,
    create_error_response,
)
from v2.modules.shared_kernel.exceptions import (
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
from v2.modules.shared_kernel.infrastructure.base import Base, EncryptedPII, get_utc_now
from v2.modules.shared_kernel.infrastructure.base_repository import BaseRepository
from v2.modules.shared_kernel.infrastructure.error_monitoring_models import (
    ErrorEvent,
    ErrorOccurrence,
)
from v2.modules.shared_kernel.infrastructure.outbox import (
    OutboxEvent,
    OutboxService,
    get_outbox_service,
    save_outbox_event,
)
from v2.modules.shared_kernel.infrastructure.unit_of_work import (
    UnitOfWork,
    get_uow,
    unit_of_work,
)
from v2.modules.shared_kernel.schemas.api_responses import (
    DeleteResultResponse,
    ImportResultResponse,
    MessageResponse,
    MessageWithWarningResponse,
    SuccessCountResponse,
    SuccessOnlyResponse,
    TaskStatusResponse,
    UploadResultResponse,
)
from v2.modules.shared_kernel.schemas.base import ResponseMeta, StandardResponse
from v2.modules.shared_kernel.schemas.validators import (
    check_sql_injection,
    check_xss,
    create_name_validator,
    create_password_validator,
    create_phone_validator,
    create_safe_string_validator,
    create_username_validator,
    mask_phone,
    sanitize_string,
    validate_dict_size,
    validate_name,
    validate_password_complexity,
    validate_phone,
    validate_safe_string,
    validate_username,
)
from v2.modules.shared_kernel.utils.clock import current_date, current_datetime_utc
from v2.modules.shared_kernel.utils.type_helpers import safe_float

__all__ = [
    # domain entity
    "BaseEntity",
    # errors (FastAPI-facing)
    "BusinessException",
    "DiagnosticHelper",
    "create_error_response",
    # domain exception hierarchy
    "DomainError",
    "FuelCalculationError",
    "ImportValidationError",
    "ExcelExportError",
    "RouteProcessingError",
    "MLPredictionError",
    "AnomalyDetectionError",
    "AuditLogError",
    "LLMProviderError",
    # ORM base + generic infra
    "Base",
    "EncryptedPII",
    "get_utc_now",
    "BaseRepository",
    "ErrorEvent",
    "ErrorOccurrence",
    "OutboxEvent",
    "OutboxService",
    "get_outbox_service",
    "save_outbox_event",
    "UnitOfWork",
    "get_uow",
    "unit_of_work",
    # generic response envelopes
    "ResponseMeta",
    "StandardResponse",
    "MessageResponse",
    "MessageWithWarningResponse",
    "SuccessCountResponse",
    "ImportResultResponse",
    "DeleteResultResponse",
    "UploadResultResponse",
    "TaskStatusResponse",
    "SuccessOnlyResponse",
    # security validators
    "sanitize_string",
    "check_xss",
    "check_sql_injection",
    "validate_safe_string",
    "validate_username",
    "validate_name",
    "mask_phone",
    "validate_dict_size",
    "validate_password_complexity",
    "validate_phone",
    "create_safe_string_validator",
    "create_username_validator",
    "create_name_validator",
    "create_password_validator",
    "create_phone_validator",
    # clock injection
    "current_date",
    "current_datetime_utc",
    # type helpers
    "safe_float",
]
