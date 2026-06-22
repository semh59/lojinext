from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.prediction_service as prediction_service_module
from app.services.prediction_service import PredictionService


class DummyUnitOfWork:
    def __init__(self, *, vehicle=None, driver=None, trailer=None):
        self.arac_repo = MagicMock()
        self.sofor_repo = MagicMock()
        self.dorse_repo = MagicMock()
        self.arac_repo.get_by_id = AsyncMock(return_value=vehicle or {})
        self.sofor_repo.get_by_id = AsyncMock(return_value=driver)
        self.dorse_repo.get_by_id = AsyncMock(return_value=trailer)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePhysicsPredictor:
    def __init__(self, specs):
        self.specs = specs

    def predict(self, route, historical_stats=None):
        return SimpleNamespace(consumption_l_100km=20.0, insight="physics-baseline")

    def predict_granular(
        self, granular_nodes, ton, bos_sefer, historical_stats=None, arac_yasi=0
    ):
        return SimpleNamespace(consumption_l_100km=20.0, insight="physics-baseline")


def _vehicle_payload():
    return {
        "id": 1,
        "bos_agirlik_kg": 8200,
        "hava_direnc_katsayisi": 0.52,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "yil": 2022,
    }


@pytest.mark.asyncio
async def test_predict_consumption_normalizes_nested_route_analysis(monkeypatch):
    uow = DummyUnitOfWork(vehicle=_vehicle_payload(), driver={"score": 0.5})
    ensemble_service = SimpleNamespace(
        predict_consumption=AsyncMock(
            return_value={
                "success": True,
                "tahmin_l_100km": 29.4,
                "guven_araligi": (27.0, 31.8),
                "confidence_score": 0.65,
                "ml_correction": 1.7,
                "champion": "ensemble",
                "challenger": "physics",
                "model_version": "ensemble-v2",
            }
        )
    )

    monkeypatch.setattr(prediction_service_module, "UnitOfWork", lambda: uow)
    monkeypatch.setattr(
        prediction_service_module,
        "PhysicsBasedFuelPredictor",
        FakePhysicsPredictor,
    )

    service = PredictionService()
    service.ensemble_service = ensemble_service
    service.weather_service = SimpleNamespace(get_seasonal_factor=lambda _: 1.0)
    service._log_prediction_to_ai = AsyncMock()

    result = await service.predict_consumption(
        arac_id=1,
        mesafe_km=100.0,
        ton=10.0,
        sofor_id=7,
        route_analysis={
            "weather_factor": 1.11,
            "route_analysis": {
                "ratios": {"otoyol": 0.72, "devlet_yolu": 0.2, "sehir_ici": 0.08},
                "motorway": {"flat": 72.0, "up": 0.0, "down": 0.0},
            },
        },
    )

    assert result["tahmini_tuketim"] == 29.4
    assert result["warning_level"] == "GREEN"
    assert result["faktorler"]["otoyol_ratio"] == 0.72

    route_analysis = ensemble_service.predict_consumption.await_args.kwargs[
        "route_analysis"
    ]
    assert route_analysis["weather_factor"] == 1.11
    assert route_analysis["ratios"]["otoyol"] == 0.72
    assert "route_analysis" not in route_analysis


@pytest.mark.asyncio
async def test_predict_consumption_missing_confidence_fails_closed(monkeypatch):
    uow = DummyUnitOfWork(vehicle=_vehicle_payload(), driver={"score": 0.5})
    ensemble_service = SimpleNamespace(
        predict_consumption=AsyncMock(
            return_value={
                "success": True,
                "tahmin_l_100km": 31.0,
                "guven_araligi": (28.0, 34.0),
                "ml_correction": 2.2,
                "champion": "ensemble",
                "challenger": "physics",
                "model_version": "ensemble-v2",
            }
        )
    )

    monkeypatch.setattr(prediction_service_module, "UnitOfWork", lambda: uow)
    monkeypatch.setattr(
        prediction_service_module,
        "PhysicsBasedFuelPredictor",
        FakePhysicsPredictor,
    )

    service = PredictionService()
    service.ensemble_service = ensemble_service
    service.weather_service = SimpleNamespace(get_seasonal_factor=lambda _: 1.0)
    service._log_prediction_to_ai = AsyncMock()

    result = await service.predict_consumption(
        arac_id=1,
        mesafe_km=100.0,
        ton=10.0,
        sofor_id=7,
        use_ensemble=True,
        route_analysis={
            "ratios": {"otoyol": 0.7, "devlet_yolu": 0.2, "sehir_ici": 0.1}
        },
    )

    assert result["warning_level"] == "RED"
    assert result["fallback_triggered"] is True
    assert result["model_used"] == "physics_fallback"
    assert result["confidence_score"] == 0.0
    assert result["tahmini_tuketim"] == 22.0


@pytest.mark.asyncio
async def test_train_xgboost_model_uses_current_training_keys():
    service = PredictionService()
    service.ensemble_service = SimpleNamespace(
        train_for_vehicle=AsyncMock(
            return_value={
                "success": True,
                "ensemble_r2": 0.67,
                "sample_count": 123,
                "metrics": {"gb_test_r2": 0.5},
            }
        )
    )

    result = await service.train_xgboost_model(arac_id=5)

    assert result["status"] == "success"
    assert result["r2_score"] == 0.67
    assert result["sample_count"] == 123
    assert result["metrics"]["gb_test_r2"] == 0.5
