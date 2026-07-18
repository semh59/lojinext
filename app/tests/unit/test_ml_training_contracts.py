from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.utils.sefer_status import SEFER_STATUS_TAMAMLANDI
from app.database.repositories.sefer_repo import SeferRepository
from v2.modules.analytics_executive.infrastructure.executive_read_models import (
    AnalizRepository,
)
from v2.modules.prediction_ml.application.ensemble_service import (
    EnsemblePredictorService,
)
from v2.modules.prediction_ml.domain.ensemble_core import PredictionResult

LEGACY_REAL_FLAG = "is" + "_real"


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


@pytest.mark.asyncio
async def test_sefer_repo_get_for_training_uses_fk_join_and_rich_route_columns():
    repo = SeferRepository()
    captured = {}

    async def fake_execute(query: str, params: dict):
        captured["query"] = query
        captured["params"] = params
        return []

    repo.execute_query = fake_execute

    await repo.get_for_training(17, limit=55)

    query = captured["query"]
    assert "LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id" in query
    assert "LOWER(s.cikis_yeri)" not in query
    assert "s.tarih" in query
    assert "s.arac_id" in query
    assert "COALESCE(s.rota_detay, l.route_analysis)" in query
    assert "COALESCE(s.otoban_mesafe_km, l.otoban_mesafe_km, 0.0)" in query
    assert "COALESCE(s.sehir_ici_mesafe_km, l.sehir_ici_mesafe_km, 0.0)" in query
    assert captured["params"] == {
        "arac_id": 17,
        "limit": 55,
        "completed_status": SEFER_STATUS_TAMAMLANDI,
    }


@pytest.mark.asyncio
async def test_analiz_repo_training_query_keeps_fk_join_without_synthetic_filters():
    repo = AnalizRepository()
    captured = {}

    async def fake_execute(query: str, params: dict):
        captured["query"] = query
        captured["params"] = params
        return []

    repo.execute_query = fake_execute

    await repo.get_training_seferler(9, limit=44)

    query = captured["query"]
    assert "LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id" in query
    assert "LOWER(s.cikis_yeri)" not in query
    assert "AND s.is_deleted = False" in query
    assert LEGACY_REAL_FLAG not in query
    assert captured["params"] == {
        "arac_id": 9,
        "limit": 44,
        "offset": 0,
        "completed_status": SEFER_STATUS_TAMAMLANDI,
    }


@pytest.mark.asyncio
async def test_train_for_vehicle_uses_each_trip_date_for_seasonal_factor(monkeypatch):
    service = EnsemblePredictorService()
    service._arac_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=_build_vehicle(12, yil=2019))
    )

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
    service._sefer_repo = SimpleNamespace(
        get_for_training=AsyncMock(return_value=trips)
    )

    predictor = _PredictorStub(fit_success=False)
    service.get_predictor = MagicMock(return_value=predictor)

    weather_calls = []

    def get_seasonal_factor(target_date: date) -> float:
        weather_calls.append(target_date)
        return 1.18 if target_date.month == 1 else 0.91

    monkeypatch.setattr(
        "app.core.services.weather_service.get_weather_service",
        lambda: SimpleNamespace(get_seasonal_factor=get_seasonal_factor),
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_driver_stats",
        AsyncMock(
            return_value=[
                SimpleNamespace(sofor_id=1, filo_karsilastirma=8),
                SimpleNamespace(sofor_id=2, filo_karsilastirma=14),
            ]
        ),
    )

    await service.train_for_vehicle(12)

    enriched_rows = predictor.fit_calls[0][0]
    assert weather_calls[:2] == [date(2024, 1, 15), date(2024, 7, 10)]
    assert enriched_rows[0]["mevsim_faktor"] == 1.18
    assert enriched_rows[1]["mevsim_faktor"] == 0.91


@pytest.mark.asyncio
async def test_predict_consumption_uses_dorse_repo_without_uow(monkeypatch):
    service = EnsemblePredictorService()
    service._arac_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=_build_vehicle(42, yil=2021))
    )
    service._dorse_repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value={
                "bos_agirlik_kg": 7200.0,
                "lastik_sayisi": 8,
                "dorse_lastik_direnc_katsayisi": 0.007,
                "dorse_hava_direnci": 0.14,
            }
        )
    )

    predictor = _PredictorStub(is_trained=True)
    service.get_predictor = MagicMock(return_value=predictor)

    monkeypatch.setattr(
        "app.core.services.weather_service.get_weather_service",
        lambda: SimpleNamespace(get_seasonal_factor=lambda _: 1.05),
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_driver_stats",
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


@pytest.mark.asyncio
async def test_predict_consumption_prefers_vehicle_class_fallback_before_general(
    monkeypatch,
):
    service = EnsemblePredictorService()
    service._arac_repo = SimpleNamespace(
        get_by_id=AsyncMock(
            return_value=_build_vehicle(
                99,
                yil=2020,
                tank_kapasitesi=650,
                maks_yuk_kapasitesi_kg=26000,
            )
        )
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
        "app.core.services.weather_service.get_weather_service",
        lambda: SimpleNamespace(get_seasonal_factor=lambda _: 1.0),
    )
    monkeypatch.setattr(
        "v2.modules.driver.public.get_driver_stats",
        AsyncMock(return_value=[]),
    )

    await service.predict_consumption(arac_id=99, mesafe_km=280.0, ton=19.0)

    assert heavy_fallback_predictor.predictions
    assert not general_predictor.predictions
    assert [call.args[0] for call in service.get_predictor.call_args_list[:2]] == [
        99,
        10000,
    ]


@pytest.mark.asyncio
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
    service._sefer_repo = SimpleNamespace(
        get_all_for_training=AsyncMock(return_value=heavy_trips + light_trips)
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
        "v2.modules.prediction_ml.application.ensemble_service."
        "_register_model_version",
        _fake_register,
    )
    monkeypatch.setattr(
        "v2.modules.analytics_executive.public.get_analiz_repo",
        lambda: SimpleNamespace(
            execute_query=AsyncMock(
                side_effect=AssertionError(
                    "raw SQL path should not be used for fallback training"
                )
            ),
            save_model_params=AsyncMock(
                side_effect=lambda arac_id, params: legacy_saves.append(
                    (arac_id, params)
                )
            ),
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
