"""Feature D.4 — PredictionService integration-style tests (no real DB).

Calls the real `predict_consumption` with mid-level stubs:
- cross_module_client.get_vehicle -> stub (arac fetch is over HTTP now,
  since the Task 5 service extraction; ServiceUnitOfWork is only used for
  the D.4 health-input raw SQL query)
- ServiceUnitOfWork.session -> fake (backs fetch_health_input's raw SQL)
- get_seasonal_factor -> stub (a plain function in
  prediction_ml_service.domain.seasonal_factor now, not
  route_simulation.public.WeatherService)
- Ensemble prediction -> optional mock
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock

import pytest


# -- Fakes --------------------------------------------------------------
class _FakeSession:
    """Minimal SQL execute stub for fetch_health_input."""

    def __init__(self, last_periyodik, open_ariza=0, open_acil=0):
        self._row = {
            "last_periyodik": last_periyodik,
            "open_ariza": open_ariza,
            "open_acil": open_acil,
        }

    async def execute(self, *_args, **_kwargs):
        class _Result:
            def __init__(self, row):
                self._row = row

            def mappings(self):
                return _Mappings(self._row)

        return _Result(self._row)


class _Mappings:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class _FakeServiceUoW:
    def __init__(
        self,
        last_periyodik: Optional[datetime] = None,
        open_ariza: int = 0,
        open_acil: int = 0,
    ):
        self.session = _FakeSession(last_periyodik, open_ariza, open_acil)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None


@pytest.fixture
def _arac_dict():
    return {
        "id": 1,
        "plaka": "34 TST 1",
        "marka": "Test",
        "model": "X",
        "yil": 2020,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 32.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.52,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
        "maks_yuk_kapasitesi_kg": 26000,
        "aktif": True,
        "is_deleted": False,
    }


def _patch_dependencies(
    monkeypatch,
    uow_factory,
    arac_dict,
    *,
    weather_factor: float = 1.0,
    flag_enabled: bool = True,
):
    """Mocks PredictionService's indirect dependencies."""
    import prediction_ml_service.application.prediction_service as ps_mod
    from prediction_ml_service.infrastructure.service_uow import ServiceUnitOfWork

    uow_inst = uow_factory()
    monkeypatch.setattr(
        ServiceUnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)
    )
    monkeypatch.setattr(ServiceUnitOfWork, "__aexit__", AsyncMock(return_value=False))
    monkeypatch.setattr("app.config.settings.MAINTENANCE_FACTOR_ENABLED", flag_enabled)

    # Vehicle fetch is over HTTP now (cross_module_client), not a UoW repo.
    monkeypatch.setattr(
        ps_mod.cross_module_client,
        "get_vehicle",
        AsyncMock(return_value=arac_dict),
    )
    monkeypatch.setattr(
        ps_mod.cross_module_client,
        "get_runtime_float",
        AsyncMock(return_value=0.015),
    )

    # get_seasonal_factor is a plain module-level function now (used to be
    # route_simulation.public.WeatherService().get_seasonal_factor before
    # the extraction) -- patch the source module directly.
    monkeypatch.setattr(ps_mod, "get_seasonal_factor", lambda _d: weather_factor)

    # No-op the ensemble -> always take the physics-fallback path (cleaner test).
    async def _no_ensemble(*args, **kwargs):
        return None

    monkeypatch.setattr(ps_mod, "run_ensemble_prediction", _no_ensemble)


# -- Tests ----------------------------------------------------------------
async def test_predict_with_fresh_periyodik_applies_low_factor(monkeypatch, _arac_dict):
    """Last PERIYODIK 30 days ago -> maintenance_factor ~= 0.96 -> prediction drops."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeServiceUoW(last_periyodik=now - timedelta(days=30))

    _patch_dependencies(monkeypatch, _uow_factory, _arac_dict)

    from prediction_ml_service.application.prediction_service import (
        PredictionService,
    )

    svc = PredictionService()
    result = await svc.predict_consumption(
        arac_id=1,
        mesafe_km=100,
        ton=10,
        ascent_m=50,
        descent_m=50,
        flat_distance_km=100,
        use_ensemble=False,
        target_date=now.date(),
    )
    # Factor 0.96 should show up in faktorler
    assert "faktorler" in result
    assert result["faktorler"].get("maintenance_factor") == 0.96
    assert "Taze PERIYODIK" in result.get("explanation_summary", "")


async def test_predict_with_overdue_periyodik_increases_prediction(
    monkeypatch, _arac_dict
):
    """PERIYODIK overdue by 400 days -> factor 1.07 -> prediction rises."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeServiceUoW(last_periyodik=now - timedelta(days=400))

    _patch_dependencies(monkeypatch, _uow_factory, _arac_dict)

    from prediction_ml_service.application.prediction_service import (
        PredictionService,
    )

    svc = PredictionService()
    result = await svc.predict_consumption(
        arac_id=1,
        mesafe_km=100,
        ton=10,
        ascent_m=50,
        descent_m=50,
        flat_distance_km=100,
        use_ensemble=False,
        target_date=now.date(),
    )
    assert result["faktorler"].get("maintenance_factor") == 1.07
    assert "gecikti" in result.get("explanation_summary", "").lower()


async def test_predict_with_flag_off_no_factor_applied(monkeypatch, _arac_dict):
    """MAINTENANCE_FACTOR_ENABLED=False -> no factor applied, backward compatible."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeServiceUoW(last_periyodik=now - timedelta(days=400))

    _patch_dependencies(monkeypatch, _uow_factory, _arac_dict, flag_enabled=False)

    from prediction_ml_service.application.prediction_service import (
        PredictionService,
    )

    svc = PredictionService()
    result = await svc.predict_consumption(
        arac_id=1,
        mesafe_km=100,
        ton=10,
        ascent_m=50,
        descent_m=50,
        flat_distance_km=100,
        use_ensemble=False,
        target_date=now.date(),
    )
    # Flag off -> maintenance_factor not written into faktorler
    faktorler = result.get("faktorler", {})
    assert faktorler.get("maintenance_factor") is None


async def test_predict_with_open_acil_applies_higher_factor(monkeypatch, _arac_dict):
    """Fresh PERIYODIK (0.96) + open ACIL (x1.10) -> 0.96 x 1.10 = 1.056."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeServiceUoW(last_periyodik=now - timedelta(days=10), open_acil=1)

    _patch_dependencies(monkeypatch, _uow_factory, _arac_dict)

    from prediction_ml_service.application.prediction_service import (
        PredictionService,
    )

    svc = PredictionService()
    result = await svc.predict_consumption(
        arac_id=1,
        mesafe_km=100,
        ton=10,
        ascent_m=50,
        descent_m=50,
        flat_distance_km=100,
        use_ensemble=False,
        target_date=now.date(),
    )
    factor = result["faktorler"]["maintenance_factor"]
    assert 1.05 <= factor <= 1.06  # ~1.056 rounded
