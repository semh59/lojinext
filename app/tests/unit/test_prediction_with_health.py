"""Feature D.4 — PredictionService entegrasyon-tarzı testleri (DB'siz).

Gerçek `predict_consumption`'ı orta-seviye stub'larla çağırır:
- UnitOfWork → FakeUoW (arac fetch + fetch_health_input)
- WeatherService → stub
- Ensemble prediction → opsiyonel mock
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork


# ── Fakes ────────────────────────────────────────────────────────────────
class _FakeAracRepo:
    def __init__(self, arac_dict: Optional[Dict[str, Any]]) -> None:
        self._arac = arac_dict

    async def get_by_id(self, _id: int):
        if self._arac is None:
            return None
        from types import SimpleNamespace

        # SimpleNamespace because predict_consumption does raw.__dict__
        return SimpleNamespace(**self._arac)


class _FakeSession:
    """fetch_health_input için minimum SQL execute stub."""

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


class _FakeUoW:
    def __init__(
        self,
        arac_dict: Optional[Dict[str, Any]] = None,
        last_periyodik: Optional[datetime] = None,
        open_ariza: int = 0,
        open_acil: int = 0,
    ):
        self.arac_repo = _FakeAracRepo(arac_dict)
        self.sofor_repo = _FakeAracRepo(None)  # generic empty repo
        self.dorse_repo = _FakeAracRepo(None)
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
    *,
    weather_factor: float = 1.0,
    flag_enabled: bool = True,
):
    """PredictionService'in indirect bağımlılıklarını mocka tabi tutar."""
    import v2.modules.prediction_ml.application.prediction_service as ps_mod

    uow_inst = uow_factory()
    monkeypatch.setattr(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst))
    monkeypatch.setattr(UnitOfWork, "__aexit__", AsyncMock(return_value=False))
    monkeypatch.setattr("app.config.settings.MAINTENANCE_FACTOR_ENABLED", flag_enabled)

    class _FakeWeatherService:
        def get_seasonal_factor(self, _d):
            return weather_factor

    monkeypatch.setattr(ps_mod, "WeatherService", _FakeWeatherService)

    # Ensemble'ı no-op → her zaman physics fallback path'i (cleaner test)
    async def _no_ensemble(*args, **kwargs):
        return None

    monkeypatch.setattr(
        ps_mod,
        "run_ensemble_prediction",
        _no_ensemble,
    )


# ── Tests ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_predict_with_fresh_periyodik_applies_low_factor(monkeypatch, _arac_dict):
    """Son 30 gün PERIYODIK → maintenance_factor ≈ 0.96 → tahmin düşer."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeUoW(
            arac_dict=_arac_dict,
            last_periyodik=now - timedelta(days=30),
        )

    _patch_dependencies(monkeypatch, _uow_factory)

    from v2.modules.prediction_ml.application.prediction_service import (
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
    # Factor 0.96 → faktorler'de görünmeli
    assert "faktorler" in result
    assert result["faktorler"].get("maintenance_factor") == 0.96
    assert "Taze PERIYODIK" in result.get("explanation_summary", "")


@pytest.mark.asyncio
async def test_predict_with_overdue_periyodik_increases_prediction(
    monkeypatch, _arac_dict
):
    """400 gün PERIYODIK → factor 1.07 → tahmin yükselir."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeUoW(
            arac_dict=_arac_dict,
            last_periyodik=now - timedelta(days=400),
        )

    _patch_dependencies(monkeypatch, _uow_factory)

    from v2.modules.prediction_ml.application.prediction_service import (
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


@pytest.mark.asyncio
async def test_predict_with_flag_off_no_factor_applied(monkeypatch, _arac_dict):
    """MAINTENANCE_FACTOR_ENABLED=False → factor uygulanmaz, geri uyumlu."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeUoW(
            arac_dict=_arac_dict,
            last_periyodik=now - timedelta(days=400),
        )

    _patch_dependencies(monkeypatch, _uow_factory, flag_enabled=False)

    from v2.modules.prediction_ml.application.prediction_service import (
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
    # Flag kapalı → maintenance_factor faktorler'e yazılmaz
    faktorler = result.get("faktorler", {})
    assert faktorler.get("maintenance_factor") is None


@pytest.mark.asyncio
async def test_predict_with_open_acil_applies_higher_factor(monkeypatch, _arac_dict):
    """Taze PERIYODIK (0.96) + açık ACIL (×1.10) → 0.96 × 1.10 = 1.056."""
    now = datetime.now(timezone.utc)

    def _uow_factory():
        return _FakeUoW(
            arac_dict=_arac_dict,
            last_periyodik=now - timedelta(days=10),
            open_acil=1,
        )

    _patch_dependencies(monkeypatch, _uow_factory)

    from v2.modules.prediction_ml.application.prediction_service import (
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
    assert 1.05 <= factor <= 1.06  # ≈1.056 yuvarlanmış
