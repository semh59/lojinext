"""Public surface of the trip module.

Other modules that need to call into trip must import from here, not from
``application/``, ``domain/``, or ``infrastructure/`` directly (see
TASKS/modules/trip.md and .importlinter's forbidden-imports contract).

``SeferService`` sınıf istisnası (ARCH-006 — facade, bkz. CLAUDE.md);
``SeferReadService``/``SeferWriteService``/``SeferAnalizService`` YOK —
CQRS alt-servisleri dissolve edildi, her use-case bağımsız bir fonksiyon
(B.1, diğer 12 modülle aynı karar). ``SeferFuelEstimator`` de kendi
gerekçesiyle sınıf olarak kaldı (constructor-injected client'lar,
tek-cohesive-pipeline).
"""

from v2.modules.trip.application.add_trip import add_sefer
from v2.modules.trip.application.bulk_add_trips import bulk_add_sefer
from v2.modules.trip.application.bulk_trip_ops import (
    bulk_cancel,
    bulk_delete,
    bulk_update_status,
)
from v2.modules.trip.application.delete_trip import delete_sefer
from v2.modules.trip.application.list_trips import (
    get_all_paged,
    get_all_trips,
    get_by_id,
    get_by_vehicle,
    get_sefer_by_id,
    get_timeline,
)
from v2.modules.trip.application.onay import get_by_onay_durumu, set_onay_durumu
from v2.modules.trip.application.reconcile_costs import reconcile_costs
from v2.modules.trip.application.return_trip import create_return_trip
from v2.modules.trip.application.sefer_fuel_estimator import (
    FactorBreakdown,
    SeferFuelEstimate,
    SeferFuelEstimator,
    SeferFuelInput,
    get_sefer_fuel_estimator,
)
from v2.modules.trip.application.trip_prediction_enrichment import (
    build_prediction_route_analysis,
    extract_prediction_values,
)
from v2.modules.trip.application.trip_service import SeferService, get_sefer_service
from v2.modules.trip.application.trip_stats import (
    get_fuel_performance_analytics,
    get_trip_stats,
)
from v2.modules.trip.application.update_trip import update_sefer
from v2.modules.trip.domain.entities import Sefer
from v2.modules.trip.domain.trip_validation import ALLOWED_TRANSITIONS, safe_durum
from v2.modules.trip.infrastructure.models import Sefer as SeferORM
from v2.modules.trip.infrastructure.models import SeferBelge, SeferLog
from v2.modules.trip.infrastructure.repository import SeferRepository, get_sefer_repo
from v2.modules.trip.schemas import (
    SeferBase,
    SeferBulkCancel,
    SeferBulkDelete,
    SeferBulkResponse,
    SeferBulkStatusUpdate,
    SeferCreate,
    SeferDurum,
    SeferListResponse,
    SeferResponse,
    SeferStatsResponse,
    SeferUpdate,
    TripStatus,
)
from v2.modules.trip.sefer_status import (
    CANONICAL_SEFER_STATUS_SET,
    SEFER_STATUS_IPTAL,
    SEFER_STATUS_PLANLANDI,
    SEFER_STATUS_TAMAMLANDI,
    ensure_canonical_sefer_status,
    normalize_sefer_status,
)

__all__ = [
    # facade (sınıf istisnası)
    "SeferService",
    "get_sefer_service",
    # read
    "get_by_id",
    "get_sefer_by_id",
    "get_by_vehicle",
    "get_all_paged",
    "get_all_trips",
    "get_timeline",
    # write / CRUD
    "add_sefer",
    "update_sefer",
    "delete_sefer",
    "bulk_add_sefer",
    "bulk_update_status",
    "bulk_cancel",
    "bulk_delete",
    "create_return_trip",
    # analytics_executive'in çağırdığı stats/reconciliation
    "get_trip_stats",
    "get_fuel_performance_analytics",
    "reconcile_costs",
    # approval workflow
    "set_onay_durumu",
    "get_by_onay_durumu",
    # prediction enrichment (route_simulation/ai_assistant tüketir)
    "build_prediction_route_analysis",
    "extract_prediction_values",
    # SeferFuelEstimator (Phase 4-5, sınıf istisnası)
    "SeferFuelEstimator",
    "SeferFuelInput",
    "SeferFuelEstimate",
    "FactorBreakdown",
    "get_sefer_fuel_estimator",
    # status
    "SEFER_STATUS_PLANLANDI",
    "SEFER_STATUS_TAMAMLANDI",
    "SEFER_STATUS_IPTAL",
    "CANONICAL_SEFER_STATUS_SET",
    "ensure_canonical_sefer_status",
    "normalize_sefer_status",
    "ALLOWED_TRANSITIONS",
    "safe_durum",
    # domain entity (internal DTO, distinct from the SeferResponse/SeferCreate
    # API schemas below — used by fuel's period-matching and prediction_ml)
    "Sefer",
    # ORM tabloları (models.py bölünmesi — dalga 16 task #58). `SeferORM`
    # adı bilinçli: `Sefer` adı yukarıdaki Pydantic domain entity tarafından
    # kullanılıyor, aynı public.py'de iki farklı sınıf aynı isimle export
    # edilemez. Cross-module tüketiciler (analytics_executive/driver/
    # prediction_ml) tipli SQLAlchemy select() sorguları için gerçek ORM
    # sınıfına ihtiyaç duyuyor (raw SQL değil) — "geçici borç" olarak
    # dokümante edilmişti. (auth_rbac'ın kendi tüketicisi —
    # LicenseEngine.check_monthly_trip_limit — 2026-07-22'de LicenseEngine'le
    # birlikte silindi.)
    "SeferORM",
    "SeferLog",
    "SeferBelge",
    # repository
    "SeferRepository",
    "get_sefer_repo",
    # schemas
    "SeferBase",
    "SeferCreate",
    "SeferUpdate",
    "SeferResponse",
    "SeferDurum",
    "TripStatus",
    "SeferBulkStatusUpdate",
    "SeferBulkCancel",
    "SeferBulkDelete",
    "SeferBulkResponse",
    "SeferListResponse",
    "SeferStatsResponse",
]
