"""Public surface of the fuel module.

Other modules that need to call into fuel must import from here, not from
`application/`, `domain/`, or `infrastructure/` directly (see
TASKS/modules/fuel.md and .importlinter's forbidden-imports contract,
enforced from FAZ1's import-linter gate task onward).

There is no ``YakitService``/``PeriodCalculationService``/
``YakitTahminService`` class — each use-case is a standalone function (same
B.1 pattern as location/notification/fleet). The pre-migration
``YakitService.__init__(repo=...)`` parameter was dead weight (every method
opened its own ``UnitOfWork()`` and never read ``self.repo``) — dropped
here rather than carried forward.
"""

from v2.modules.fuel.application.add_yakit import add_yakit
from v2.modules.fuel.application.bulk_add_yakit import bulk_add_yakit
from v2.modules.fuel.application.calculate_period import create_fuel_periods
from v2.modules.fuel.application.delete_yakit import delete_yakit
from v2.modules.fuel.application.distribute_fuel_to_trips import (
    distribute_fuel_to_trips,
    match_periods_with_trips,
)
from v2.modules.fuel.application.get_fuel_accuracy import get_fuel_accuracy_stats
from v2.modules.fuel.application.get_yakit import get_by_vehicle, get_yakit_by_id
from v2.modules.fuel.application.list_fuel_documents import list_fuel_documents
from v2.modules.fuel.application.list_yakit import (
    get_all,
    get_all_paged,
    get_monthly_cost_trend,
    get_monthly_summary,
    get_stats,
)
from v2.modules.fuel.application.recalculate_vehicle_periods import (
    recalculate_vehicle_periods,
)
from v2.modules.fuel.application.update_yakit import update_yakit
from v2.modules.fuel.domain.entities import YakitAlimiCreate
from v2.modules.fuel.domain.period_matcher import PeriyotSeferMatch
from v2.modules.fuel.infrastructure.integrations.opet_client import (
    FuelCardProvider,
    FuelTransaction,
    OpetFuelProvider,
)
from v2.modules.fuel.infrastructure.models import YakitAlimi as YakitAlimiORM
from v2.modules.fuel.infrastructure.models import YakitFormul, YakitPeriyot
from v2.modules.fuel.infrastructure.repository import YakitRepository, get_yakit_repo
from v2.modules.fuel.infrastructure.tasks import CoverageResult, compute_coverage
from v2.modules.fuel.schemas import (
    FuelDocumentItem,
    FuelDocumentList,
    OcrParsedFields,
    OcrPreviewResponse,
    YakitBase,
    YakitCreate,
    YakitListResponse,
    YakitResponse,
    YakitUpdate,
)

__all__ = [
    # ORM (dalga 16 task #58 — database/models.py bölünmesi). YakitAlimi ORM
    # sınıfı "YakitAlimiORM" olarak export edilir — domain/entities.py'de
    # zaten aynı isimli Pydantic YakitAlimi(BaseEntity) var (prediction_ml'in
    # PredictionResult -> PredictionResultORM ile aynı gerekçe).
    "YakitAlimiORM",
    "YakitPeriyot",
    "YakitFormul",
    # fuel transactions
    "add_yakit",
    "update_yakit",
    "delete_yakit",
    "bulk_add_yakit",
    "get_yakit_by_id",
    "get_by_vehicle",
    "get_all",
    "get_all_paged",
    "get_stats",
    "get_monthly_summary",
    "get_monthly_cost_trend",
    "list_fuel_documents",
    "get_fuel_accuracy_stats",
    # periods
    "create_fuel_periods",
    "distribute_fuel_to_trips",
    "match_periods_with_trips",
    "recalculate_vehicle_periods",
    "PeriyotSeferMatch",
    # consumption prediction (module-internal, distinct from prediction_ml)
    # fuel-card integrations
    "FuelCardProvider",
    "FuelTransaction",
    "OpetFuelProvider",
    # coverage ops alarm
    "CoverageResult",
    "compute_coverage",
    # repository
    "YakitRepository",
    "get_yakit_repo",
    # schemas
    "YakitBase",
    "YakitCreate",
    "YakitUpdate",
    "YakitResponse",
    "YakitListResponse",
    "OcrParsedFields",
    "OcrPreviewResponse",
    "FuelDocumentItem",
    "FuelDocumentList",
    # domain entity (internal DTO, distinct from YakitCreate above — used by
    # bulk_add_yakit/add_yakit; import_excel constructs these for its bulk
    # Excel-import path)
    "YakitAlimiCreate",
]
