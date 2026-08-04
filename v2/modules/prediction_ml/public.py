"""Public surface of the prediction_ml module.

Other modules that need to call into prediction_ml should import from here,
not from ``application/``, ``domain/``, or ``infrastructure/`` directly.

Extracted into a standalone service (``v2/services/prediction_ml_service/``,
Task 5, 2026-08-04) -- the ensemble/ML pipeline itself now runs in a
separate process. This module keeps two kinds of exports:

1. Pure, I/O-free physics/adjustment-factor logic (``domain/
   {physics_fuel_predictor,adjustment_factors,vehicle_health_adjustment}.py``)
   -- dual-homed here AND in the new service, since several OTHER modules
   (route_simulation, location, trip, analytics_executive) construct
   these objects directly for their own standalone physics calculations,
   not through the ensemble/ML prediction flow.
2. ``find_similar_trips`` (``application/route_similarity.py``) -- also
   kept in-process here. It has zero ML/ensemble dependency (pure route-
   vector cosine similarity + an in-process driver DB query); it was
   briefly moved to the new service and moved back once that became
   clear (see docs/superpowers/plans/2026-07-31-prediction-ml-service-
   extraction.md's session log).
3. ``PredictionService``/``get_prediction_service`` -- now an HTTP-client
   facade calling the new service (``infrastructure_client/http_client.py``),
   keeping the exact same method names/signatures every consumer already
   uses (``predict_consumption``/``explain_consumption``/
   ``train_xgboost_model``).

``EnsemblePredictorService``/``Trainer``/``PredictionBackfillService``/
``ModelTrainingHandler``/``PhysicsRecalculationHandler``/
``schedule_predictor_warmup`` are NOT exported anymore -- none of them had
any consumer outside this module's own (now-moved) internals; the two
event handlers + the warm-up task are wired directly in the new service's
own ``main.py`` lifespan.
"""

from v2.modules.prediction_ml.application.route_similarity import find_similar_trips
from v2.modules.prediction_ml.domain.adjustment_factors import (
    combine_factors,
    weather_precipitation_factor,
    weather_temperature_factor,
    weather_wind_factor,
)
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    FuelPrediction,
    PhysicsBasedFuelPredictor,
    RouteConditions,
    VehicleSpecs,
)
from v2.modules.prediction_ml.domain.vehicle_health_adjustment import (
    HealthInput,
    HealthResult,
    apply_maintenance_factor,
    compute_maintenance_factor,
    fetch_health_input,
    fetch_health_input_batch,
)
from v2.modules.prediction_ml.infrastructure_client.http_client import (
    PredictionService,
    get_prediction_service,
)

__all__ = [
    "PredictionService",
    "get_prediction_service",
    "combine_factors",
    "weather_precipitation_factor",
    "weather_temperature_factor",
    "weather_wind_factor",
    "FuelPrediction",
    "PhysicsBasedFuelPredictor",
    "RouteConditions",
    "VehicleSpecs",
    "find_similar_trips",
    "HealthInput",
    "HealthResult",
    "apply_maintenance_factor",
    "compute_maintenance_factor",
    "fetch_health_input",
    "fetch_health_input_batch",
]
