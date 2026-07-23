"""Public surface of the prediction_ml module.

Other modules that need to call into prediction_ml should import from here,
not from ``application/``, ``domain/``, or ``infrastructure/`` directly.

Table ownership: ``egitim_kuyrugu``, ``model_versiyonlar``, ``prediction_results``.

``trip`` (migrated, dalga 14) imports ``PredictionService``/
``get_prediction_service`` via ``v2/modules/trip/application/{add_trip,
trip_prediction_enrichment,return_trip,bulk_add_trips}.py`` and
``v2/modules/ai_assistant/api/plan_wizard_routes.py`` — all through this
``public.py``.
"""

from v2.modules.prediction_ml.application.ensemble_service import (
    EnsemblePredictorService,
    get_ensemble_service,
)
from v2.modules.prediction_ml.application.model_training_handler import (
    ModelTrainingHandler,
    get_model_training_handler,
)
from v2.modules.prediction_ml.application.model_warmup import (
    schedule_predictor_warmup,
)
from v2.modules.prediction_ml.application.physics_handler import (
    PhysicsRecalculationHandler,
    get_physics_handler,
)
from v2.modules.prediction_ml.application.prediction_backfill_service import (
    PredictionBackfillService,
)
from v2.modules.prediction_ml.application.prediction_service import (
    PredictionService,
    get_prediction_service,
)
from v2.modules.prediction_ml.application.time_series_service import (
    TimeSeriesService,
    get_time_series_service,
)
from v2.modules.prediction_ml.application.trainer import Trainer
from v2.modules.prediction_ml.domain.adjustment_factors import (
    combine_factors,
    weather_precipitation_factor,
    weather_temperature_factor,
    weather_wind_factor,
)
from v2.modules.prediction_ml.domain.ensemble_core import (
    LIGHTGBM_AVAILABLE,
    SKLEARN_AVAILABLE,
    XGBOOST_AVAILABLE,
    EnsembleFuelPredictor,
    PredictionResult,
    SecurityError,
)
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    FuelPrediction,
    HybridFuelPredictor,
    PhysicsBasedFuelPredictor,
    RouteConditions,
    VehicleSpecs,
)
from v2.modules.prediction_ml.domain.route_similarity import find_similar_trips
from v2.modules.prediction_ml.domain.time_series_predictor import (
    ARIMATimeSeriesPredictor,
    get_arima_predictor,
    get_time_series_predictor,
    is_lstm_available,
)
from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
    HealthInput,
    HealthResult,
    apply_maintenance_factor,
    compute_maintenance_factor,
    fetch_health_input,
    fetch_health_input_batch,
)
from v2.modules.prediction_ml.infrastructure.models import (
    EgitimKuyrugu,
    ModelVersiyon,
)
from v2.modules.prediction_ml.infrastructure.models import (
    PredictionResult as PredictionResultORM,
)

__all__ = [
    "EnsemblePredictorService",
    "get_ensemble_service",
    "ModelTrainingHandler",
    "get_model_training_handler",
    "schedule_predictor_warmup",
    "PhysicsRecalculationHandler",
    "get_physics_handler",
    "PredictionBackfillService",
    "PredictionService",
    "get_prediction_service",
    "TimeSeriesService",
    "get_time_series_service",
    "Trainer",
    "combine_factors",
    "weather_precipitation_factor",
    "weather_temperature_factor",
    "weather_wind_factor",
    "LIGHTGBM_AVAILABLE",
    "SKLEARN_AVAILABLE",
    "XGBOOST_AVAILABLE",
    "EnsembleFuelPredictor",
    "PredictionResult",
    # ORM (dalga 16 task #58 — database/models.py bölünmesi)
    "EgitimKuyrugu",
    "ModelVersiyon",
    "PredictionResultORM",
    "SecurityError",
    "FuelPrediction",
    "HybridFuelPredictor",
    "PhysicsBasedFuelPredictor",
    "RouteConditions",
    "VehicleSpecs",
    "find_similar_trips",
    "ARIMATimeSeriesPredictor",
    "get_arima_predictor",
    "get_time_series_predictor",
    "is_lstm_available",
    "HealthInput",
    "HealthResult",
    "apply_maintenance_factor",
    "compute_maintenance_factor",
    "fetch_health_input",
    "fetch_health_input_batch",
]
