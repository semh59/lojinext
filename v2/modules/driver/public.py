"""Public surface of the driver module.

Other modules that need to call into driver must import from here, not
from ``application/``, ``domain/``, or ``infrastructure/`` directly (see
TASKS/modules/driver.md and .importlinter's forbidden-imports contract,
enforced from FAZ1's import-linter gate task onward).

There is no ``SoforService``/``SoforAnalizService``/``SoforDegerlendirmeService``
class — each CRUD/analysis/evaluation use-case is a standalone function
(same B.1 pattern as location/notification/fleet/fuel). ``DriverCoachingEngine``
and ``DriverPerformanceML`` stay classes — see CLAUDE.md for the exception
rationale (constructor-injected clients / stateful trained ML model).
"""

from v2.modules.driver.application.add_sofor import add_sofor, bulk_add_sofor
from v2.modules.driver.application.delete_sofor import bulk_delete, delete_sofor
from v2.modules.driver.application.generate_coaching import (
    DriverCoachingEngine,
    get_driver_coaching_engine,
)
from v2.modules.driver.application.get_coaching_effectiveness import (
    get_coaching_effectiveness_stats,
)
from v2.modules.driver.application.get_performance import get_performance_details
from v2.modules.driver.application.get_route_profile import get_route_profile_sofor
from v2.modules.driver.application.get_score import (
    calculate_hybrid_score,
    get_score_breakdown_sofor,
)
from v2.modules.driver.application.list_sofor import (
    get_all_paged,
    get_by_id,
    get_driver_fleet_stats,
)
from v2.modules.driver.application.record_coaching_delivery import (
    record_coaching_delivery,
)
from v2.modules.driver.application.update_sofor import update_score, update_sofor
from v2.modules.driver.domain.driver_stats import (
    calculate_elite_performance_score,
    calculate_performance_score,
    calculate_trend,
    compare_drivers,
    get_driver_stats,
    get_driver_trend,
    get_route_performance,
)
from v2.modules.driver.domain.evaluation import (
    DereceEnum,
    GuzergahPerformans,
    SoforDegerlendirme,
    TrendEnum,
    evaluate_driver,
    get_all_evaluations,
    get_rankings,
)
from v2.modules.driver.domain.performance_ml import (
    DriverPerformanceML,
    DriverScorePrediction,
    get_driver_performance_ml,
)
from v2.modules.driver.domain.route_profile import (
    ROUTE_TYPES,
    classify_route,
    get_driver_route_coefficient,
)
from v2.modules.driver.infrastructure.pdf_export import SoforSeferPDFService
from v2.modules.driver.infrastructure.repository import SoforRepository, get_sofor_repo
from v2.modules.driver.schemas import (
    CoachingCategory,
    CoachingEffectivenessResponse,
    CoachingInsightItem,
    CoachingInsightsResponse,
    CoachingPriority,
    CoachingSource,
    DriverPerformanceSchema,
    DriverRouteProfileSchema,
    DriverScoreBreakdownSchema,
    SendCoachingRequest,
    SendCoachingResponse,
    SoforCreate,
    SoforResponse,
    SoforUpdate,
)

__all__ = [
    # driver CRUD
    "add_sofor",
    "bulk_add_sofor",
    "update_sofor",
    "update_score",
    "delete_sofor",
    "bulk_delete",
    "get_by_id",
    "get_all_paged",
    "get_driver_fleet_stats",
    "get_performance_details",
    # score / route profile
    "calculate_hybrid_score",
    "get_score_breakdown_sofor",
    "get_route_profile_sofor",
    # coaching delivery / effectiveness
    "record_coaching_delivery",
    "get_coaching_effectiveness_stats",
    # analytics / ranking
    "get_driver_stats",
    "compare_drivers",
    "get_driver_trend",
    "get_route_performance",
    "calculate_elite_performance_score",
    "calculate_performance_score",
    "calculate_trend",
    # evaluation (0-100 scorecard)
    "evaluate_driver",
    "get_all_evaluations",
    "get_rankings",
    "SoforDegerlendirme",
    "GuzergahPerformans",
    "DereceEnum",
    "TrendEnum",
    # ML
    "DriverPerformanceML",
    "DriverScorePrediction",
    "get_driver_performance_ml",
    # route-type classification
    "ROUTE_TYPES",
    "classify_route",
    "get_driver_route_coefficient",
    # coaching (Feature A)
    "DriverCoachingEngine",
    "get_driver_coaching_engine",
    # PDF export
    "SoforSeferPDFService",
    # repository
    "SoforRepository",
    "get_sofor_repo",
    # schemas
    "SoforCreate",
    "SoforUpdate",
    "SoforResponse",
    "DriverPerformanceSchema",
    "DriverScoreBreakdownSchema",
    "DriverRouteProfileSchema",
    "CoachingCategory",
    "CoachingPriority",
    "CoachingSource",
    "CoachingInsightItem",
    "CoachingInsightsResponse",
    "SendCoachingRequest",
    "SendCoachingResponse",
    "CoachingEffectivenessResponse",
]
