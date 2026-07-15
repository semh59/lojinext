"""Public surface of the anomaly module.

Other modules that need to call into anomaly must import from here, not
from ``application/``, ``domain/``, or ``infrastructure/`` directly (see
TASKS/modules/anomaly.md and .importlinter's forbidden-imports contract,
enforced from FAZ1's import-linter gate task onward).

Sınıf istisnaları (B.1, CLAUDE.md'de detaylı gerekçe): ``AnomalyDetector``
(sklearn/LightGBM eğitilmiş model state'i), ``AnomalyDetectionService``
(cache-injected istatistiksel alt-sistem), ``FuelTheftClassifier``
(stateless tek-pipeline). ``AttributionService`` KALDIRILDI —
``override_attribution``/``bulk_override_attribution`` free function.
"""

from v2.modules.anomaly.application.attribute_loss import (
    bulk_override_attribution,
    override_attribution,
)
from v2.modules.anomaly.application.classify_theft import (
    FuelTheftClassifier,
    get_fuel_theft_classifier,
)
from v2.modules.anomaly.application.detect_anomaly import (
    AnomalyDetector,
    AnomalyResult,
    AnomalyType,
    SeverityEnum,
    get_anomaly_detector,
)
from v2.modules.anomaly.application.detect_statistical_anomaly import (
    AnomalyDetectionService,
    get_anomaly_detection_service,
)
from v2.modules.anomaly.domain.clustering import cluster_anomalies
from v2.modules.anomaly.schemas import (
    AttributionOverrideRequest,
    AttributionOverrideResponse,
    InvestigationCreate,
    InvestigationResponse,
    InvestigationUpdate,
    PatternMatch,
    SuspicionLevel,
    TheftClassification,
)

__all__ = [
    "AnomalyDetectionService",
    "AnomalyDetector",
    "AnomalyResult",
    "AnomalyType",
    "AttributionOverrideRequest",
    "AttributionOverrideResponse",
    "FuelTheftClassifier",
    "InvestigationCreate",
    "InvestigationResponse",
    "InvestigationUpdate",
    "PatternMatch",
    "SeverityEnum",
    "SuspicionLevel",
    "TheftClassification",
    "bulk_override_attribution",
    "cluster_anomalies",
    "get_anomaly_detection_service",
    "get_anomaly_detector",
    "get_fuel_theft_classifier",
    "override_attribution",
]
