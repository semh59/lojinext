"""Split out of app/tests/unit/test_ml_training_contracts.py (Task 5,
2026-08-04) -- the EnsemblePredictorService tests moved here with the new
service's code; the SeferRepository/AnalizRepository query-construction
tests stayed on the main backend (they don't touch prediction_ml at all)."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from prediction_ml_service.application.ensemble_service import (
    EnsemblePredictorService,
)
from prediction_ml_service.domain.ensemble_core import PredictionResult

pytestmark = pytest.mark.unit


def _build_vehicle(
    arac_id: int,
    *,
    yil: int = 2020,
    tank_kapasitesi: int = 600,
    maks_yuk_kapasitesi_kg: int = 26000,
) -> dict:
    return {
        "id": arac_id,
        "plaka": f"34ABC{arac_id:03d}",
        "marka": "Ford",
        "model": "Cargo",
        "yil": yil,
        "tank_kapasitesi": tank_kapasitesi,
        "maks_yuk_kapasitesi_kg": maks_yuk_kapasitesi_kg,
        "hedef_tuketim": 32.0,
        "aktif": True,
    }


def _build_trip(
    idx: int,
    *,
    arac_id: int,
    tarih,
    tank_kapasitesi: int = 600,
    maks_yuk_kapasitesi_kg: int = 26000,
    sofor_id: int = 1,
) -> dict:
    return {
        "id": idx,
        "arac_id": arac_id,
        "tarih": tarih,
        "mesafe_km": 300 + idx,
        "ton": 18.0,
        "tuketim": 33.0 + idx,
        "sofor_id": sofor_id,
        "ascent_m": 240.0,
        "descent_m": 180.0,
        "flat_distance_km": 250.0,
        "zorluk": "Normal",
        "rota_detay": {
            "route_analysis": {
                "motorway": {"flat": 180.0, "up": 10.0, "down": 5.0},
                "other": {"flat": 70.0, "up": 0.0, "down": 0.0},
            }
        },
        "tank_kapasitesi": tank_kapasitesi,
        "maks_yuk_kapasitesi_kg": maks_yuk_kapasitesi_kg,
    }


class _PredictorStub:
    def __init__(self, *, is_trained: bool = True, fit_success: bool = True):
        self.is_trained = is_trained
        self.fit_success = fit_success
        self.fit_calls: list = []
        self.predictions: list = []
        self.saved_paths: list = []

    def fit(self, seferler, y_values):
        self.fit_calls.append((seferler, y_values))
        return {
            "success": self.fit_success,
            "sample_count": len(seferler),
            "physics_mae": 0.1,
            "metrics": {"gb_test_r2": 0.82},
        }

    def predict(self, sefer):
        self.predictions.append(sefer)
        return PredictionResult(
            tahmin_l_100km=31.5,
            physics_only=30.8,
            ml_correction=0.7,
            confidence_low=29.0,
            confidence_high=34.0,
            physics_weight=0.6,
            features_used=sefer,
        )

    def save_model(self, path: str):
        self.saved_paths.append(path)


async def test_train_for_vehicle_uses_each_trip_date_for_seasonal_factor(monkeypatch):
    service = EnsemblePredictorService()

    trips = []
    for idx in range(10):
        trips.append(
            _build_trip(
                idx,
                arac_id=12,
                tarih="2024-01-15" if idx % 2 == 0 else date(2024, 7, 10),
                sofor_id=1 if idx % 2 == 0 else 2,
            )
        )

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_vehicle",
        AsyncMock(return_value=_build_vehicle(12, yil=2019)),
    )
    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_training_data",
        AsyncMock(return_value=trips),
    )

    predictor = _PredictorStub(fit_success=False)
    service.get_predictor = MagicMock(return_value=predictor)

    weather_calls = []

    def fake_get_seasonal_factor(target_date: date) -> float:
        weather_calls.append(target_date)
        return 1.18 if target_date.month == 1 else 0.91

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.get_seasonal_factor",
        fake_get_seasonal_factor,
    )
    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_driver_stats",
        AsyncMock(
            return_value=[
                {"sofor_id": 1, "filo_karsilastirma": 8},
                {"sofor_id": 2, "filo_karsilastirma": 14},
            ]
        ),
    )

    await service.train_for_vehicle(12)

    enriched_rows = predictor.fit_calls[0][0]
    assert weather_calls[:2] == [date(2024, 1, 15), date(2024, 7, 10)]
    assert enriched_rows[0]["mevsim_faktor"] == 1.18
    assert enriched_rows[1]["mevsim_faktor"] == 0.91


async def test_predict_consumption_uses_dorse_data_from_cross_module_client(
    monkeypatch,
):
    service = EnsemblePredictorService()

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_vehicle",
        AsyncMock(return_value=_build_vehicle(42, yil=2021)),
    )
    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_trailer",
        AsyncMock(
            return_value={
                "bos_agirlik_kg": 7200.0,
                "lastik_sayisi": 8,
                "dorse_lastik_direnc_katsayisi": 0.007,
                "dorse_hava_direnci": 0.14,
            }
        ),
    )

    predictor = _PredictorStub(is_trained=True)
    service.get_predictor = MagicMock(return_value=predictor)

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.get_seasonal_factor",
        lambda _: 1.05,
    )
    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_driver_stats",
        AsyncMock(return_value=[]),
    )

    result = await service.predict_consumption(
        arac_id=42,
        mesafe_km=320.0,
        ton=20.0,
        dorse_id=7,
    )

    assert result["success"] is True
    assert predictor.predictions[0]["dorse_bos_agirlik"] == 7200.0
    assert predictor.predictions[0]["dorse_lastik_sayisi"] == 8


async def test_predict_consumption_prefers_vehicle_class_fallback_before_general(
    monkeypatch,
):
    service = EnsemblePredictorService()

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_vehicle",
        AsyncMock(
            return_value=_build_vehicle(
                99,
                yil=2020,
                tank_kapasitesi=650,
                maks_yuk_kapasitesi_kg=26000,
            )
        ),
    )

    vehicle_predictor = _PredictorStub(is_trained=False)
    heavy_fallback_predictor = _PredictorStub(is_trained=True)
    general_predictor = _PredictorStub(is_trained=True)

    predictor_map = {
        99: vehicle_predictor,
        10000: heavy_fallback_predictor,
        0: general_predictor,
    }
    service.get_predictor = MagicMock(
        side_effect=lambda predictor_id: predictor_map[predictor_id]
    )

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.get_seasonal_factor",
        lambda _: 1.0,
    )
    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_driver_stats",
        AsyncMock(return_value=[]),
    )

    await service.predict_consumption(arac_id=99, mesafe_km=280.0, ton=19.0)

    assert heavy_fallback_predictor.predictions
    assert not general_predictor.predictions
    assert [call.args[0] for call in service.get_predictor.call_args_list[:2]] == [
        99,
        10000,
    ]


async def test_train_general_model_trains_class_specific_fallback_models(monkeypatch):
    service = EnsemblePredictorService()
    heavy_trips = [
        _build_trip(
            idx,
            arac_id=100 + idx,
            tarih="2024-01-15",
            tank_kapasitesi=650,
            maks_yuk_kapasitesi_kg=26000,
        )
        for idx in range(10)
    ]
    light_trips = [
        _build_trip(
            idx + 20,
            arac_id=200 + idx,
            tarih="2024-07-15",
            tank_kapasitesi=150,
            maks_yuk_kapasitesi_kg=5000,
        )
        for idx in range(10)
    ]

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.get_all_training_data",
        AsyncMock(return_value=heavy_trips + light_trips),
    )

    general_predictor = _PredictorStub(is_trained=True)
    heavy_predictor = _PredictorStub(is_trained=True)
    light_predictor = _PredictorStub(is_trained=True)
    predictor_map = {
        0: general_predictor,
        10000: heavy_predictor,
        10002: light_predictor,
    }
    service.get_predictor = MagicMock(
        side_effect=lambda predictor_id: predictor_map[predictor_id]
    )

    saved_versions = []
    legacy_saves = []

    async def _fake_register(*, arac_id, predictor, result, model_path):
        saved_versions.append({"arac_id": arac_id})

    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service._register_model_version",
        _fake_register,
    )
    monkeypatch.setattr(
        "prediction_ml_service.application.ensemble_service.cross_module_client.save_model_params",
        AsyncMock(
            side_effect=lambda arac_id, params: legacy_saves.append((arac_id, params))
        ),
    )

    result = await service.train_general_model()

    assert result["success"] is True
    assert general_predictor.fit_calls
    assert heavy_predictor.fit_calls
    assert light_predictor.fit_calls
    assert any(item["arac_id"] == 10000 for item in saved_versions)
    assert any(item["arac_id"] == 10002 for item in saved_versions)
    assert any(arac_id == 10000 for arac_id, _ in legacy_saves)
    assert any(arac_id == 10002 for arac_id, _ in legacy_saves)
