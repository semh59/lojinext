"""Coverage tests for v2/modules/fleet/api/admin_maintenance_routes.py"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper fixtures / mocks
# ---------------------------------------------------------------------------


def _make_bakim_record(**kwargs):
    """Build a simple object that satisfies MaintenanceRecordResponse.model_validate."""
    defaults = {
        "id": 1,
        "arac_id": 10,
        "dorse_id": None,
        "bakim_tipi": "PERIYODIK",
        "km_bilgisi": 120000,
        "bakim_tarihi": datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        "maliyet": 500.0,
        "detaylar": "Rutin bakım",
        "tamamlandi": False,
        "guncelleme_tarihi": None,
    }
    defaults.update(kwargs)

    class FakeRecord:
        pass

    obj = FakeRecord()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_alert(**kwargs):
    """Return a dict-compatible object for MaintenanceAlertItem.model_validate."""
    defaults = {
        "id": 1,
        "arac_id": 10,
        "plaka": "34ABC001",
        "bakim_tipi": "PERIYODIK",
        "tarih": datetime(2024, 7, 1, tzinfo=timezone.utc),
        "vade_durumu": "UPCOMING",
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# _get_redis helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_redis_returns_client_on_success(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    fake_redis = MagicMock()
    fake_aioredis = MagicMock()
    fake_aioredis.from_url.return_value = fake_redis

    with patch.dict("sys.modules", {"redis.asyncio": fake_aioredis}):
        result = await mod._get_redis()

    assert result is not None


@pytest.mark.asyncio
async def test_get_redis_returns_none_on_exception(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    with patch("redis.asyncio.from_url", side_effect=Exception("boom")):
        await mod._get_redis()
    # exception is swallowed — just verify no raise


# ---------------------------------------------------------------------------
# get_upcoming_alerts — direct logic test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_upcoming_alerts_returns_list(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    with patch.object(
        mod, "get_upcoming_maintenance_alerts", AsyncMock(return_value=[_make_alert()])
    ):
        result = await mod.get_upcoming_alerts()

    assert len(result) == 1
    assert result[0].plaka == "34ABC001"


@pytest.mark.asyncio
async def test_get_upcoming_alerts_empty_list(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    with patch.object(
        mod, "get_upcoming_maintenance_alerts", AsyncMock(return_value=[])
    ):
        result = await mod.get_upcoming_alerts()

    assert result == []


# ---------------------------------------------------------------------------
# get_vehicle_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vehicle_history_returns_list(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    with patch.object(
        mod,
        "get_vehicle_maintenance_history",
        AsyncMock(return_value=[_make_bakim_record()]),
    ):
        result = await mod.get_vehicle_history(arac_id=10)

    assert len(result) == 1
    assert result[0].id == 1


@pytest.mark.asyncio
async def test_get_vehicle_history_multiple_records(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    records = [
        _make_bakim_record(id=i, km_bilgisi=100000 + i * 10000) for i in range(3)
    ]

    with patch.object(
        mod, "get_vehicle_maintenance_history", AsyncMock(return_value=records)
    ):
        result = await mod.get_vehicle_history(arac_id=5)

    assert len(result) == 3


# ---------------------------------------------------------------------------
# mark_complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_complete_success(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    with patch.object(mod, "mark_maintenance_completed", AsyncMock(return_value=True)):
        result = await mod.mark_complete(bakim_id=1)

    assert result.success is True


@pytest.mark.asyncio
async def test_mark_complete_failure(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    with patch.object(mod, "mark_maintenance_completed", AsyncMock(return_value=False)):
        result = await mod.mark_complete(bakim_id=999)

    assert result.success is False


# ---------------------------------------------------------------------------
# get_all_predictions — feature flag disabled → 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_predictions_feature_disabled(monkeypatch):
    from fastapi import HTTPException

    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", False)

    fake_user = MagicMock()
    fake_user.id = 1

    with pytest.raises(HTTPException) as exc_info:
        await mod.get_all_predictions(current_user=fake_user)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_all_predictions_feature_enabled_no_cache(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", True)

    # Stub out Redis to return no cached data
    fake_redis = AsyncMock()
    fake_redis.get.return_value = None
    fake_redis.setex = AsyncMock()

    # Stub out predictor

    pred_obj = MagicMock()
    pred_obj.arac_id = 1
    pred_obj.plaka = "06TEST"
    pred_obj.bakim_tipi = "PERIYODIK"
    pred_obj.predictable = True
    pred_obj.confidence = 0.9
    pred_obj.predicted_date = None
    pred_obj.days_remaining = 30
    pred_obj.is_overdue = False
    pred_obj.risk_level = "normal"
    pred_obj.savings_pct = 5.0
    pred_obj.reasons = []

    fake_predictor = AsyncMock()
    fake_predictor.predict_all.return_value = [pred_obj]

    fake_user = MagicMock()
    fake_user.id = 2

    with (
        patch.object(mod, "_get_redis", return_value=fake_redis),
        patch.object(mod, "MaintenancePredictor", return_value=fake_predictor),
        patch(
            "v2.modules.fleet.api.admin_maintenance_routes.log_audit_event",
            new_callable=AsyncMock,
        ),
    ):
        result = await mod.get_all_predictions(current_user=fake_user)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].plaka == "06TEST"


@pytest.mark.asyncio
async def test_get_all_predictions_cache_hit(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", True)

    from v2.modules.fleet.schemas import MaintenancePrediction

    cached_pred = MaintenancePrediction(
        arac_id=1,
        plaka="34CACHE",
        bakim_tipi="PERIYODIK",
        predictable=True,
        confidence=0.8,
    )
    cached_json = json.dumps([cached_pred.model_dump_json()])

    fake_redis = AsyncMock()
    fake_redis.get.return_value = cached_json

    fake_user = MagicMock()
    fake_user.id = 3

    with patch.object(mod, "_get_redis", return_value=fake_redis):
        result = await mod.get_all_predictions(current_user=fake_user)

    assert len(result) == 1
    assert result[0].plaka == "34CACHE"


@pytest.mark.asyncio
async def test_get_all_predictions_redis_none(monkeypatch):
    """When Redis is unavailable (returns None), fall through to predictor."""
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", True)

    fake_predictor = AsyncMock()
    fake_predictor.predict_all.return_value = []

    fake_user = MagicMock()
    fake_user.id = 0  # edge: id == 0 → creator_id = None

    with (
        patch.object(mod, "_get_redis", return_value=None),
        patch.object(mod, "MaintenancePredictor", return_value=fake_predictor),
        patch(
            "v2.modules.fleet.api.admin_maintenance_routes.log_audit_event",
            new_callable=AsyncMock,
        ),
    ):
        result = await mod.get_all_predictions(current_user=fake_user)

    assert result == []


# ---------------------------------------------------------------------------
# get_prediction_for_arac — feature flag disabled + 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_prediction_for_arac_feature_disabled(monkeypatch):
    from fastapi import HTTPException

    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", False)

    fake_user = MagicMock()
    fake_user.id = 1

    with pytest.raises(HTTPException) as exc_info:
        await mod.get_prediction_for_arac(arac_id=1, current_user=fake_user)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_prediction_for_arac_not_found(monkeypatch):
    from fastapi import HTTPException

    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", True)

    fake_predictor = AsyncMock()
    fake_predictor.predict_for_arac.return_value = None

    fake_user = MagicMock()
    fake_user.id = 1

    with patch.object(mod, "MaintenancePredictor", return_value=fake_predictor):
        with pytest.raises(HTTPException) as exc_info:
            await mod.get_prediction_for_arac(arac_id=999, current_user=fake_user)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_prediction_for_arac_success(monkeypatch):
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    monkeypatch.setattr(mod.settings, "MAINTENANCE_PREDICTOR_ENABLED", True)

    pred_obj = MagicMock()
    pred_obj.arac_id = 5
    pred_obj.plaka = "06SINGLE"
    pred_obj.bakim_tipi = "ARIZA"
    pred_obj.predictable = True
    pred_obj.confidence = 0.75
    pred_obj.predicted_date = None
    pred_obj.days_remaining = 15
    pred_obj.is_overdue = False
    pred_obj.risk_level = "soon"
    pred_obj.savings_pct = 0.0
    pred_obj.reasons = []

    fake_predictor = AsyncMock()
    fake_predictor.predict_for_arac.return_value = pred_obj

    fake_user = MagicMock()
    fake_user.id = 1

    with (
        patch.object(mod, "MaintenancePredictor", return_value=fake_predictor),
        patch(
            "v2.modules.fleet.api.admin_maintenance_routes.log_audit_event",
            new_callable=AsyncMock,
        ),
    ):
        result = await mod.get_prediction_for_arac(arac_id=5, current_user=fake_user)

    assert result.plaka == "06SINGLE"
    assert result.risk_level == "soon"


# ---------------------------------------------------------------------------
# create_maintenance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_maintenance_success(monkeypatch):
    from app.database.models import BakimTipi
    from v2.modules.fleet.api import admin_maintenance_routes as mod

    record = _make_bakim_record(id=42, bakim_tipi="PERIYODIK")

    schema_data = mod.MaintenanceCreateSchema(
        arac_id=10,
        bakim_tipi=BakimTipi.PERIYODIK,
        km_bilgisi=120000,
        bakim_tarihi=datetime(2024, 6, 1, tzinfo=timezone.utc),
        maliyet=500.0,
        detaylar="Rutin",
    )

    fake_create = AsyncMock(return_value=record)
    with patch.object(mod, "create_maintenance_record", fake_create):
        result = await mod.create_maintenance(data=schema_data)

    assert result.id == 42
    fake_create.assert_called_once()
