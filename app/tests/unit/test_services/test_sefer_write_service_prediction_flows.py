from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.services.weather_service as weather_module
import v2.modules.prediction_ml.public as prediction_module
from app.database.unit_of_work import UnitOfWork
from v2.modules.trip.application import (
    add_trip,
    bulk_add_trips,
    return_trip,
    update_trip,
)
from v2.modules.trip.schemas import SeferCreate, SeferUpdate


class DummyUnitOfWork:
    def __init__(self):
        self.sefer_repo = MagicMock()
        self.arac_repo = MagicMock()
        # bulk_add_sefer artık arac master'dan bos_agirlik_kg pre-fetch yapıyor
        # (ck_net_kg_calc constraint: net = dolu - bos). MagicMock awaitable
        # değil → AsyncMock olarak override et.
        self.arac_repo.get_all = AsyncMock(return_value=[])
        self.arac_repo.get_by_ids = AsyncMock(return_value={})
        self.sofor_repo = MagicMock()
        self.sofor_repo.get_by_ids = AsyncMock(return_value={})
        # AUDIT-041: bulk_add_sefer aktif sofor doğrulaması için get_all çağırır.
        self.sofor_repo.get_all = AsyncMock(return_value=[])
        self.lokasyon_repo = MagicMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.session = MagicMock()
        self.session.add = MagicMock()
        self.session.flush = AsyncMock()
        # AUDIT-041: sefer_no benzersizlik kontrolü session.execute(...).fetchall() çağırır.
        self.session.execute = AsyncMock(
            return_value=MagicMock(fetchall=MagicMock(return_value=[]))
        )
        self.sefer_repo.get_existing_sefer_nos = AsyncMock(return_value=set())

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _prediction_payload(
    *,
    tuketim: float,
    litre: float,
    model_used: str = "ensemble",
    model_version: str = "ensemble-v2",
    confidence_score: float = 0.82,
):
    return {
        "tahmini_tuketim": tuketim,
        "tahmini_litre": litre,
        "prediction_liters": litre + 100.0,
        "model_used": model_used,
        "model_version": model_version,
        "confidence_score": confidence_score,
        "status": "success",
        "warning_level": "GREEN",
        "fallback_triggered": False,
        "faktorler": {"weather_factor": 1.08},
        "explanation_summary": "contract-ok",
    }


def _route_metadata():
    return {
        "id": 7,
        "cikis_yeri": "Istanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 120.0,
        "ascent_m": 320.0,
        "descent_m": 180.0,
        "flat_distance_km": 25.0,
        "route_analysis": {
            "ratios": {"otoyol": 0.72, "devlet_yolu": 0.2, "sehir_ici": 0.08}
        },
        "otoban_mesafe_km": 86.4,
        "sehir_ici_mesafe_km": 9.6,
        "cikis_lat": 41.0082,
        "cikis_lon": 28.9784,
        "varis_lat": 39.9334,
        "varis_lon": 32.8597,
    }


def _patch_prediction(monkeypatch, payload):
    prediction_service = SimpleNamespace(
        predict_consumption=AsyncMock(return_value=payload)
    )
    monkeypatch.setattr(
        prediction_module,
        "get_prediction_service",
        lambda: prediction_service,
    )
    return prediction_service


@pytest.mark.asyncio
async def test_add_sefer_persists_canonical_prediction_contract(monkeypatch):
    uow = DummyUnitOfWork()
    route_metadata = _route_metadata()

    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
    uow.sefer_repo.has_active_trip = AsyncMock(return_value=False)
    uow.sefer_repo.add = AsyncMock(return_value=101)
    uow.sefer_repo.refresh_stats_mv = AsyncMock()
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": True, "bos_agirlik_kg": 8200}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value={"aktif": True})
    uow.lokasyon_repo.get_by_id = AsyncMock(return_value=route_metadata)

    prediction_service = _patch_prediction(
        monkeypatch, _prediction_payload(tuketim=32.4, litre=38.9)
    )
    weather_service = SimpleNamespace(
        get_trip_impact_analysis=AsyncMock(
            return_value={"success": True, "fuel_impact_factor": 1.08}
        )
    )

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))
    monkeypatch.setattr(
        weather_module,
        "get_weather_service",
        lambda: weather_service,
    )

    data = SeferCreate(
        tarih=date(2026, 3, 19),
        saat="09:30",
        arac_id=1,
        sofor_id=2,
        guzergah_id=7,
        dorse_id=3,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=120.0,
        net_kg=12000,
        bos_agirlik_kg=8200,
        dolu_agirlik_kg=20200,
        durum="Planlandı",
        bos_sefer=False,
        is_round_trip=False,
    )

    sefer_id = await add_trip.add_sefer(data, user_id=44)

    assert sefer_id == 101
    create_kwargs = uow.sefer_repo.add.await_args.kwargs
    assert create_kwargs["tahmini_tuketim"] == 32.4
    assert create_kwargs["tahmin_meta"]["tahmini_litre"] == 38.9
    assert create_kwargs["tahmin_meta"]["model_used"] == "ensemble"
    assert create_kwargs["tahmin_meta"]["input_quality"]["route_available"] is True
    assert (
        create_kwargs["tahmin_meta"]["input_quality"]["weather_factor_applied"] is True
    )

    route_analysis = prediction_service.predict_consumption.await_args.kwargs[
        "route_analysis"
    ]
    assert route_analysis["weather_factor"] == 1.08
    assert route_analysis["ratios"]["otoyol"] == 0.72


@pytest.mark.asyncio
async def test_update_sefer_reprediction_uses_current_route_details(monkeypatch):
    uow = DummyUnitOfWork()
    current_sefer = {
        "id": 55,
        "durum": "Planlandı",
        "arac_id": 1,
        "sofor_id": 2,
        "dorse_id": 3,
        "tarih": date(2026, 3, 19),
        "mesafe_km": 120.0,
        "net_kg": 12000,
        "bos_sefer": False,
        "ascent_m": 320.0,
        "descent_m": 180.0,
        "flat_distance_km": 25.0,
        "rota_detay": {
            "ratios": {"otoyol": 0.61, "devlet_yolu": 0.24, "sehir_ici": 0.15}
        },
        "otoban_mesafe_km": 73.2,
        "sehir_ici_mesafe_km": 18.0,
        "bos_agirlik_kg": 8200,
        "dolu_agirlik_kg": 20200,
    }

    uow.sefer_repo.get_by_id = AsyncMock(return_value=current_sefer)
    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
    uow.sefer_repo.has_active_trip = AsyncMock(return_value=False)
    uow.sefer_repo.update_sefer = AsyncMock(return_value=True)
    prediction_service = _patch_prediction(
        monkeypatch,
        _prediction_payload(
            tuketim=29.8,
            litre=35.8,
            model_used="physics",
            model_version="physics-v2.0",
            confidence_score=0.55,
        ),
    )

    success = await update_trip.update_sefer_uow(
        uow,
        55,
        SeferUpdate(net_kg=15000),
        user_id=99,
    )

    assert success is True
    update_kwargs = uow.sefer_repo.update_sefer.await_args.kwargs
    assert update_kwargs["id"] == 55
    assert update_kwargs["tahmini_tuketim"] == 29.8
    assert update_kwargs["tahmin_meta"]["model_used"] == "physics"
    assert update_kwargs["tahmin_meta"]["tahmini_litre"] == 35.8
    assert update_kwargs["tahmin_meta"]["input_quality"]["route_available"] is True

    route_analysis = prediction_service.predict_consumption.await_args.kwargs[
        "route_analysis"
    ]
    assert route_analysis["ratios"]["otoyol"] == 0.61


@pytest.mark.asyncio
async def test_bulk_add_sefer_persists_canonical_prediction_contract(monkeypatch):
    uow = DummyUnitOfWork()
    route_metadata = _route_metadata()

    uow.lokasyon_repo.get_benzersiz_lokasyonlar = AsyncMock(
        return_value=["Istanbul", "Ankara"]
    )
    uow.lokasyon_repo.get_all = AsyncMock(return_value=[route_metadata])
    uow.lokasyon_repo.find_closest_match = AsyncMock(
        side_effect=lambda value, **_: value
    )
    uow.sefer_repo.bulk_create = AsyncMock(return_value=[201])
    uow.sefer_repo.refresh_stats_mv = AsyncMock()
    # AUDIT-041: satırın işlenmesi (atlanmaması) için arac_id=1/sofor_id=2 aktif olmalı.
    uow.arac_repo.get_all = AsyncMock(
        return_value=[{"id": 1, "bos_agirlik_kg": 8200, "aktif": True}]
    )
    uow.sofor_repo.get_all = AsyncMock(return_value=[{"id": 2, "aktif": True}])

    prediction_service = _patch_prediction(
        monkeypatch,
        _prediction_payload(
            tuketim=30.5,
            litre=36.6,
            model_used="ensemble",
            model_version="ensemble-v3",
            confidence_score=0.77,
        ),
    )

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))

    payload = [
        SeferCreate(
            tarih=date(2026, 3, 19),
            saat="11:15",
            arac_id=1,
            sofor_id=2,
            dorse_id=3,
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=120.0,
            net_kg=11000,
            bos_agirlik_kg=8200,
            dolu_agirlik_kg=19200,
            durum="Tamamlandı",
        )
    ]

    created = await bulk_add_trips.bulk_add_sefer(payload)

    assert created == 1
    batch_items = uow.sefer_repo.bulk_create.await_args.args[0]
    assert batch_items[0]["tahmini_tuketim"] == 30.5
    assert batch_items[0]["tahmin_meta"]["model_version"] == "ensemble-v3"
    assert batch_items[0]["tahmin_meta"]["tahmini_litre"] == 36.6

    route_analysis = prediction_service.predict_consumption.await_args.kwargs[
        "route_analysis"
    ]
    assert route_analysis["ratios"]["otoyol"] == 0.72


@pytest.mark.asyncio
async def test_create_return_trip_persists_canonical_prediction_contract(monkeypatch):
    uow = DummyUnitOfWork()
    uow.sefer_repo.add = AsyncMock(return_value=301)

    prediction_service = _patch_prediction(
        monkeypatch,
        _prediction_payload(
            tuketim=27.0,
            litre=24.3,
            model_used="physics",
            model_version="physics-v2.0",
            confidence_score=0.63,
        ),
    )

    data = SeferCreate(
        tarih=date(2026, 3, 19),
        saat="16:20",
        arac_id=1,
        sofor_id=2,
        guzergah_id=7,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=90.0,
        net_kg=12000,
        bos_agirlik_kg=8200,
        dolu_agirlik_kg=20200,
        durum="Planlandı",
        is_round_trip=True,
        return_net_kg=0,
    )
    route_details = {
        "route_analysis": {
            "ratios": {"otoyol": 0.5, "devlet_yolu": 0.3, "sehir_ici": 0.2}
        },
        "otoban_mesafe_km": 45.0,
        "sehir_ici_mesafe_km": 18.0,
    }

    await return_trip.build_return_trip(
        uow,
        data,
        date(2026, 3, 20),
        88,
        weather_factor=1.11,
        route_details=route_details,
        user_id=5,
    )

    create_kwargs = uow.sefer_repo.add.await_args.kwargs
    assert create_kwargs["tahmini_tuketim"] == 27.0
    assert create_kwargs["tahmin_meta"]["tahmini_litre"] == 24.3
    assert create_kwargs["tahmin_meta"]["model_used"] == "physics"
    assert (
        create_kwargs["tahmin_meta"]["input_quality"]["weather_factor_applied"] is True
    )

    route_analysis = prediction_service.predict_consumption.await_args.kwargs[
        "route_analysis"
    ]
    assert route_analysis["weather_factor"] == 1.11
    assert route_analysis["ratios"]["otoyol"] == 0.5


@pytest.mark.asyncio
async def test_add_sefer_does_not_mark_weather_factor_when_weather_is_unavailable(
    monkeypatch,
):
    uow = DummyUnitOfWork()
    route_metadata = _route_metadata()

    uow.sefer_repo.get_by_sefer_no = AsyncMock(return_value=None)
    uow.sefer_repo.has_active_trip = AsyncMock(return_value=False)
    uow.sefer_repo.add = AsyncMock(return_value=501)
    uow.sefer_repo.refresh_stats_mv = AsyncMock()
    uow.arac_repo.get_by_id = AsyncMock(
        return_value={"aktif": True, "bos_agirlik_kg": 8200}
    )
    uow.sofor_repo.get_by_id = AsyncMock(return_value={"aktif": True})
    uow.lokasyon_repo.get_by_id = AsyncMock(return_value=route_metadata)

    prediction_service = _patch_prediction(
        monkeypatch, _prediction_payload(tuketim=31.7, litre=38.0)
    )
    weather_service = SimpleNamespace(
        get_trip_impact_analysis=AsyncMock(
            return_value={
                "success": False,
                "error_code": "SERVICE_UNAVAILABLE",
                "error": "Weather data is currently unavailable.",
            }
        )
    )

    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))
    monkeypatch.setattr(
        weather_module,
        "get_weather_service",
        lambda: weather_service,
    )

    data = SeferCreate(
        tarih=date(2026, 3, 20),
        saat="08:15",
        arac_id=1,
        sofor_id=2,
        guzergah_id=7,
        dorse_id=3,
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=120.0,
        net_kg=12000,
        bos_agirlik_kg=8200,
        dolu_agirlik_kg=20200,
        durum="Planlandı",
        bos_sefer=False,
        is_round_trip=False,
    )

    await add_trip.add_sefer(data, user_id=55)

    create_kwargs = uow.sefer_repo.add.await_args.kwargs
    assert (
        create_kwargs["tahmin_meta"]["input_quality"]["weather_factor_applied"] is False
    )

    route_analysis = prediction_service.predict_consumption.await_args.kwargs[
        "route_analysis"
    ]
    assert "weather_factor" not in route_analysis
