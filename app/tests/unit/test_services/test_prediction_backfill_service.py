"""PredictionBackfillService unit testleri (estimator + uow mock'lu)."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.services.prediction_backfill_service import PredictionBackfillService

pytestmark = pytest.mark.unit


def _sefer_dict(sid: int) -> dict:
    return {
        "id": sid,
        "arac_id": 1,
        "sofor_id": 2,
        "dorse_id": None,
        "ton": 15.0,
        "net_kg": 15000,
        "tarih": date(2026, 6, 1),
        "bos_sefer": False,
        "guzergah_id": 7,
    }


def _make_uow(ids, sefer_lookup):
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.sefer_repo = MagicMock()
    uow.sefer_repo.get_ids_missing_prediction = AsyncMock(return_value=ids)
    uow.sefer_repo.get_by_id = AsyncMock(side_effect=lambda sid: sefer_lookup.get(sid))
    uow.sefer_repo.update = AsyncMock(return_value=True)
    uow.commit = AsyncMock()
    return uow


async def test_backfill_fills_predictions():
    uow = _make_uow([10], {10: _sefer_dict(10)})
    estimate = SimpleNamespace(
        tahmini_tuketim=32.5,
        simulation_id=99,
        to_legacy_prediction_dict=lambda: {
            "tahmini_tuketim": 32.5,
            "simulation_id": 99,
        },
    )
    estimator = MagicMock()
    estimator.predict = AsyncMock(return_value=estimate)

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 1, "filled": 1, "failed": 0, "skipped": 0}
    uow.sefer_repo.update.assert_awaited_once()
    _, kwargs = uow.sefer_repo.update.await_args
    assert kwargs["tahmini_tuketim"] == 32.5
    assert kwargs["route_simulation_id"] == 99


async def test_backfill_skips_when_estimator_returns_none():
    uow = _make_uow([10], {10: _sefer_dict(10)})
    estimator = MagicMock()
    estimator.predict = AsyncMock(return_value=None)  # Mapbox çözememe vs.

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 1, "filled": 0, "failed": 0, "skipped": 1}
    uow.sefer_repo.update.assert_not_awaited()


async def test_backfill_skips_sefer_already_filled_by_another_worker():
    """2026-07-01 prod-grade denetimi P0 #4 — ikincil savunma: broker
    visibility_timeout yanlış-hizalanması (veya worker crash/restart) yüzünden
    aynı sefer_id listesi iki worker'a redelivered olabilir. Bu durumda ikinci
    worker, sefer zaten doldurulmuşsa (tahmini_tuketim != None) dış IO
    (Mapbox/Open-Meteo) çağrısı yapmadan atlamalı — hem maliyet israfını hem
    duplike route_simulations satırını önler.
    """
    sefer = _sefer_dict(10)
    sefer["tahmini_tuketim"] = 28.4  # başka bir worker zaten doldurmuş
    uow = _make_uow([10], {10: sefer})
    estimator = MagicMock()
    estimator.predict = AsyncMock()

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 1, "filled": 0, "failed": 0, "skipped": 1}
    estimator.predict.assert_not_awaited()
    uow.sefer_repo.update.assert_not_awaited()


async def test_backfill_counts_failure_without_aborting_batch():
    uow = _make_uow([10, 11], {10: _sefer_dict(10), 11: _sefer_dict(11)})
    estimate = SimpleNamespace(
        tahmini_tuketim=30.0,
        simulation_id=1,
        to_legacy_prediction_dict=lambda: {"tahmini_tuketim": 30.0},
    )
    estimator = MagicMock()
    # İlk sefer patlar, ikinci başarılı → batch devam eder.
    estimator.predict = AsyncMock(side_effect=[RuntimeError("boom"), estimate])

    svc = PredictionBackfillService(uow=uow, estimator=estimator, throttle_s=0.0)
    result = await svc.backfill(limit=50)

    assert result == {"processed": 2, "filled": 1, "failed": 1, "skipped": 0}
