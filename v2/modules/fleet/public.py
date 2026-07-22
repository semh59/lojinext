"""Public surface of the fleet module.

Other modules that need to call into fleet must import from here, not from
`application/`, `domain/`, or `infrastructure/` directly (see
TASKS/modules/fleet.md and .importlinter's forbidden-imports contract,
enforced from FAZ1's import-linter gate task onward).

There is no ``AracService``/``DorseService``/``MaintenanceService`` class —
each use-case is a standalone function (same B.1 pattern as the location
module). Vehicle/trailer/maintenance use-cases take an explicit repository
(obtained from the caller's own UnitOfWork, e.g. ``uow.arac_repo``) or open
their own ``UnitOfWork`` internally when the pre-migration code already did
so (list/stats/bulk/delete-all/maintenance use-cases never used the
constructor-injected repo — that repo dependency was dead weight, dropped
here rather than carried forward).
"""

from v2.modules.fleet.application.bulk_add_vehicles import bulk_add_vehicles
from v2.modules.fleet.application.count_active_vehicles import (
    count_active_vehicles,
)
from v2.modules.fleet.application.create_maintenance_record import (
    create_breakdown,
    create_maintenance_record,
)
from v2.modules.fleet.application.create_trailer import create_trailer
from v2.modules.fleet.application.create_vehicle import create_vehicle
from v2.modules.fleet.application.delete_vehicle import (
    delete_all_vehicles,
    delete_vehicle,
)
from v2.modules.fleet.application.export_maintenance_calendar import (
    generate_ics_for_maintenance,
)
from v2.modules.fleet.application.export_trailers import (
    export_all_trailers,
    get_trailer_template,
    import_trailers,
)
from v2.modules.fleet.application.get_fleet_stats import (
    get_trailer_fleet_stats,
    get_vehicle_fleet_stats,
)
from v2.modules.fleet.application.get_inspection_alerts import (
    get_trailer_inspection_alerts,
    get_vehicle_inspection_alerts,
)
from v2.modules.fleet.application.get_maintenance_ics_data import (
    get_maintenance_ics_data,
)
from v2.modules.fleet.application.get_vehicle_events import get_vehicle_events
from v2.modules.fleet.application.get_vehicle_maintenance_history import (
    get_upcoming_maintenance_alerts,
    get_vehicle_maintenance_history,
    mark_maintenance_completed,
)
from v2.modules.fleet.application.list_trailers import (
    get_all_trailers_paged,
    get_trailer_by_id,
)
from v2.modules.fleet.application.list_vehicles import (
    get_all_vehicles,
    get_all_vehicles_paged,
    get_vehicle_by_id,
    get_vehicle_raw_by_id,
    get_vehicle_stats,
)
from v2.modules.fleet.application.maintenance_cache import (
    PREDICTIONS_CACHE_ALL,
    invalidate_predictions_cache,
)
from v2.modules.fleet.application.maintenance_prediction import (
    MaintenancePredictor,
    Prediction,
    PredictionInput,
)
from v2.modules.fleet.application.update_trailer import delete_trailer, update_trailer
from v2.modules.fleet.application.update_vehicle import update_vehicle
from v2.modules.fleet.domain.entities import Arac
from v2.modules.fleet.infrastructure.maintenance_repository import (
    MaintenanceRepository,
)
from v2.modules.fleet.infrastructure.models import Arac as AracORM
from v2.modules.fleet.infrastructure.models import (
    AracBakim,
    BakimTipi,
    Dorse,
    VehicleEventLog,
)
from v2.modules.fleet.infrastructure.trailer_repository import (
    DorseRepository,
    get_dorse_repo,
)
from v2.modules.fleet.infrastructure.vehicle_repository import (
    AracRepository,
    get_arac_repo,
)
from v2.modules.fleet.schemas import (
    AracBase,
    AracCreate,
    AracResponse,
    AracUpdate,
    DorseBase,
    DorseCreate,
    DorseResponse,
    DorseUpdate,
    MaintenancePrediction,
)

__all__ = [
    # vehicle
    "create_vehicle",
    "count_active_vehicles",
    "update_vehicle",
    "delete_vehicle",
    "delete_all_vehicles",
    "bulk_add_vehicles",
    "get_all_vehicles",
    "get_all_vehicles_paged",
    "get_vehicle_by_id",
    "get_vehicle_raw_by_id",
    "get_vehicle_stats",
    "get_vehicle_fleet_stats",
    "get_vehicle_inspection_alerts",
    "get_vehicle_events",
    # trailer
    "create_trailer",
    "update_trailer",
    "delete_trailer",
    "get_trailer_by_id",
    "get_all_trailers_paged",
    "export_all_trailers",
    "get_trailer_template",
    "import_trailers",
    "get_trailer_fleet_stats",
    "get_trailer_inspection_alerts",
    # maintenance
    "create_maintenance_record",
    "create_breakdown",
    "get_vehicle_maintenance_history",
    "mark_maintenance_completed",
    "get_upcoming_maintenance_alerts",
    "generate_ics_for_maintenance",
    "get_maintenance_ics_data",
    "PREDICTIONS_CACHE_ALL",
    "invalidate_predictions_cache",
    "MaintenancePredictor",
    "Prediction",
    "PredictionInput",
    # repositories
    "AracRepository",
    "get_arac_repo",
    "DorseRepository",
    "get_dorse_repo",
    "MaintenanceRepository",
    # domain entity (internal DTO, distinct from AracResponse above — carries
    # yas/yas_faktoru/euro_sinifi computed fields; prediction_ml consumes it
    # for age-based fuel-consumption adjustment)
    "Arac",
    # ORM tabloları (models.py bölünmesi — dalga 16 task #58). `AracORM`
    # adı bilinçli: `Arac` adı yukarıdaki Pydantic domain entity tarafından
    # kullanılıyor (trip.public'teki SeferORM ile aynı isimlendirme deseni).
    "AracORM",
    "Dorse",
    "BakimTipi",
    "AracBakim",
    "VehicleEventLog",
    # schemas
    "AracBase",
    "AracCreate",
    "AracUpdate",
    "AracResponse",
    "DorseBase",
    "DorseCreate",
    "DorseUpdate",
    "DorseResponse",
    "MaintenancePrediction",
]
