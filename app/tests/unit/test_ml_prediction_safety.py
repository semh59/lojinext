from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from v2.modules.prediction_ml.application.ensemble_service import (
    EnsemblePredictorService,
)
from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    FuelPrediction,
    PhysicsBasedFuelPredictor,
    RouteConditions,
)


def _sample_trip(**overrides):
    base = {
        "mesafe_km": 100.0,
        "ton": 18.0,
        "ascent_m": 240.0,
        "descent_m": 120.0,
        "flat_distance_km": 70.0,
        "yas_faktoru": 1.2,
        "mevsim_faktor": 1.1,
        "rota_detay": {
            "route_analysis": {
                "motorway": {"flat": 60.0, "up": 5.0, "down": 0.0},
                "other": {"flat": 10.0, "up": 3.0, "down": 2.0},
            }
        },
        "tuketim": 30.0,
        "tarih": "2025-01-15",
        "arac_id": 1,
        "sofor_id": 1,
    }
    base.update(overrides)
    return base


class _ZeroResidualModel:
    def predict(self, X):
        return np.zeros(X.shape[0], dtype=float)


class _LockAwareScaler:
    def __init__(self, predictor: EnsembleFuelPredictor, expected_features: int):
        self.predictor = predictor
        self.n_features_in_ = expected_features

    def fit_transform(self, X):
        return X

    def transform(self, X):
        if not self.predictor._model_lock.locked():
            raise AssertionError("transform must run while _model_lock is held")
        return X


class _CapturePhysicsModel:
    def __init__(self):
        self.vehicle = SimpleNamespace(
            trailer_empty_weight_kg=6500.0,
            trailer_rolling_resistance=0.006,
            trailer_drag_contribution=0.13,
        )
        self.routes = []

    def predict(self, route, historical_stats=None):
        self.routes.append(route)
        return SimpleNamespace(consumption_l_100km=22.0)


class _TrainingPredictorStub:
    def __init__(self, result):
        self.result = result
        self.is_trained = True
        self.saved_paths = []

    def fit(self, seferler, y_values):
        return self.result

    def save_model(self, path):
        self.saved_paths.append(path)


def _fuel_prediction():
    return FuelPrediction(
        total_liters=30.0,
        consumption_l_100km=30.0,
        energy_breakdown={},
        confidence_range=(28.0, 32.0),
        factors_used={},
    )


def test_predict_keeps_ml_transform_inside_model_lock():
    predictor = EnsembleFuelPredictor()
    predictor.is_trained = True
    predictor.weights = {
        "physics": 1.0,
        "gb": 0.0,
        "rf": 0.0,
        "xgboost": 0.0,
        "lightgbm": 0.0,
    }
    predictor.physics_weight = 1.0
    predictor.scaler = _LockAwareScaler(predictor, len(predictor.FEATURE_NAMES))
    predictor.gb_model = _ZeroResidualModel()
    predictor.rf_model = _ZeroResidualModel()
    predictor.xgb_model = None
    predictor.lgb_model = None
    predictor.physics_model = SimpleNamespace(
        predict=lambda route, historical_stats=None: SimpleNamespace(
            consumption_l_100km=10.0
        ),
        vehicle=SimpleNamespace(),
    )

    result = predictor.predict(_sample_trip(yas_faktoru=1.0, mevsim_faktor=1.0))

    assert result.tahmin_l_100km == 10.0


def test_predict_feature_mismatch_falls_back_to_physics_only_and_invalidates_model():
    predictor = EnsembleFuelPredictor()
    predictor.is_trained = True
    predictor.weights = {
        "physics": 0.4,
        "gb": 0.3,
        "rf": 0.3,
        "xgboost": 0.0,
        "lightgbm": 0.0,
    }
    predictor.physics_weight = 0.4
    predictor.scaler = _LockAwareScaler(predictor, len(predictor.FEATURE_NAMES) + 2)
    predictor.gb_model = _ZeroResidualModel()
    predictor.rf_model = _ZeroResidualModel()
    predictor.xgb_model = None
    predictor.lgb_model = None
    predictor.physics_model = SimpleNamespace(
        predict=lambda route, historical_stats=None: SimpleNamespace(
            consumption_l_100km=10.0
        ),
        vehicle=SimpleNamespace(),
    )

    result = predictor.predict(_sample_trip(yas_faktoru=1.0, mevsim_faktor=1.0))

    assert predictor.is_trained is False
    assert result.tahmin_l_100km == 10.0
    assert result.ml_correction == 0.0
    assert result.physics_weight == 1.0


def test_trained_predict_does_not_double_apply_age_and_season_factors():
    predictor = EnsembleFuelPredictor()
    predictor.is_trained = True
    predictor.weights = {
        "physics": 1.0,
        "gb": 0.0,
        "rf": 0.0,
        "xgboost": 0.0,
        "lightgbm": 0.0,
    }
    predictor.physics_weight = 1.0
    predictor.scaler = _LockAwareScaler(predictor, len(predictor.FEATURE_NAMES))
    predictor.gb_model = _ZeroResidualModel()
    predictor.rf_model = _ZeroResidualModel()
    predictor.xgb_model = None
    predictor.lgb_model = None
    predictor.physics_model = SimpleNamespace(
        predict=lambda route, historical_stats=None: SimpleNamespace(
            consumption_l_100km=10.0
        ),
        vehicle=SimpleNamespace(),
    )

    result = predictor.predict(_sample_trip())

    assert result.tahmin_l_100km == 10.0
    assert result.physics_only == 10.0


def test_get_physics_predictions_passes_flat_distance_and_route_analysis():
    predictor = EnsembleFuelPredictor()
    capture_model = _CapturePhysicsModel()
    predictor.physics_model = capture_model

    predictor._get_physics_predictions([_sample_trip()])

    route = capture_model.routes[0]
    assert route.flat_distance_km == 70.0
    assert route.route_analysis == _sample_trip()["rota_detay"]["route_analysis"]


def test_physics_predict_uses_route_analysis_segments_when_available():
    predictor = PhysicsBasedFuelPredictor()
    captured = {}

    def fake_predict_granular(
        segments, load_ton, is_empty_trip=False, historical_stats=None, **kwargs
    ):
        captured["segments"] = segments
        captured["kwargs"] = kwargs
        return _fuel_prediction()

    predictor.predict_granular = fake_predict_granular
    route = RouteConditions(
        distance_km=80.0,
        load_ton=15.0,
        ascent_m=300.0,
        descent_m=120.0,
        flat_distance_km=58.0,
        route_analysis={
            "motorway": {"flat": 50.0, "up": 4.0, "down": 0.0},
            "other": {"flat": 8.0, "up": 3.0, "down": 15.0},
        },
    )

    predictor.predict(route)

    segments = captured["segments"]
    assert sum(segment[0] for segment in segments) == pytest.approx(80000.0)
    assert any(
        segment[0] == pytest.approx(50000.0) and segment[2] == 0.0
        for segment in segments
    )


@pytest.mark.asyncio
async def test_train_general_model_saves_nested_registry_metrics(monkeypatch):
    service = EnsemblePredictorService()
    service._sefer_repo = SimpleNamespace(
        get_all_for_training=AsyncMock(
            return_value=[
                _sample_trip(arac_id=10, tank_kapasitesi=650) for _ in range(20)
            ]
        )
    )

    general_predictor = _TrainingPredictorStub(
        {
            "success": True,
            "sample_count": 20,
            "ensemble_r2": 0.81,
            "measurements": {"mae": 1.4, "rmse": 2.1, "physics_mae": 2.7},
            "metrics": {"gb_test_r2": 0.73},
        }
    )
    heavy_predictor = _TrainingPredictorStub(
        {
            "success": True,
            "sample_count": 20,
            "ensemble_r2": 0.79,
            "measurements": {"mae": 1.6, "rmse": 2.2, "physics_mae": 2.9},
            "metrics": {"gb_test_r2": 0.7},
        }
    )
    service.get_predictor = MagicMock(
        side_effect=lambda predictor_id: {
            0: general_predictor,
            10000: heavy_predictor,
        }[predictor_id]
    )

    saved_versions = []

    async def _fake_register(*, arac_id, predictor, result, model_path):
        saved_versions.append({"arac_id": arac_id, "result": result})

    monkeypatch.setattr(
        "v2.modules.prediction_ml.application.ensemble_service."
        "_register_model_version",
        _fake_register,
    )
    monkeypatch.setattr(
        "v2.modules.analytics_executive.public.get_analiz_repo",
        lambda: SimpleNamespace(save_model_params=AsyncMock(return_value=None)),
    )

    await service.train_general_model()

    general_version = next(item for item in saved_versions if item["arac_id"] == 0)
    assert general_version["result"]["measurements"]["mae"] == 1.4
    assert general_version["result"]["metrics"]["gb_test_r2"] == 0.73
