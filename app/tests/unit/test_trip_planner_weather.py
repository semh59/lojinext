"""Feature C.2 — TripPlannerEngine._weather_impact wrapper testleri.

`_weather_impact` 4 dış bağımlılığı sarar:
  1. guzergah_id'nin var olması
  2. UnitOfWork().lokasyon_repo.get_by_id ile koordinat çekme
  3. container.weather_service.get_trip_impact_analysis çağrısı
  4. Sonucun parse edilmesi

Her başarısızlık dalı nötr (1.0) döner — planlama akışı bloklanmasın.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

import pytest


class _FakeLokasyonRepo:
    def __init__(self, row: Optional[Dict[str, Any]]) -> None:
        self._row = row

    async def get_by_id(self, guzergah_id: int) -> Optional[Dict[str, Any]]:
        return self._row


class _FakeUoWWithLokasyon:
    def __init__(self, row: Optional[Dict[str, Any]]) -> None:
        self.lokasyon_repo = _FakeLokasyonRepo(row)
        self.session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


class _FakeWeatherService:
    def __init__(self, *, result: Dict[str, Any] | Exception) -> None:
        self._result = result

    async def get_trip_impact_analysis(
        self, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _patch_container_weather(monkeypatch, weather_service):
    """get_container().weather_service'i fake ile değiştir."""
    fake = type("FakeContainer", (), {})()
    fake.weather_service = weather_service
    monkeypatch.setattr("v2.modules.platform_infra.public.get_container", lambda: fake)


def _make_engine():
    from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine

    return TripPlannerEngine(prediction_service=None)


def _make_input(guzergah_id: Optional[int] = None):
    from v2.modules.ai_assistant.domain.planner_scoring import PlanInput

    return PlanInput(
        cikis_yeri="A",
        varis_yeri="B",
        mesafe_km=100,
        tarih=date.today(),
        guzergah_id=guzergah_id,
    )


# ── Test cases ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_weather_no_guzergah_id_returns_neutral():
    """guzergah_id verilmediğinde DB ve weather hiç çağrılmaz."""
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(None))
    assert impact == 1.0


@pytest.mark.asyncio
async def test_weather_lokasyon_not_found_returns_neutral(monkeypatch):
    monkeypatch.setattr(
        "v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork",
        lambda: _FakeUoWWithLokasyon(None),
    )
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(42))
    assert impact == 1.0


@pytest.mark.asyncio
async def test_weather_missing_coords_returns_neutral(monkeypatch):
    """Koordinat alanlarından biri NULL ise nötr."""
    incomplete = {
        "cikis_lat": 39.9,
        "cikis_lon": 32.85,
        "varis_lat": None,
        "varis_lon": None,
    }
    monkeypatch.setattr(
        "v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork",
        lambda: _FakeUoWWithLokasyon(incomplete),
    )
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(42))
    assert impact == 1.0


@pytest.mark.asyncio
async def test_weather_success_returns_fuel_impact_factor(monkeypatch):
    full = {
        "cikis_lat": 39.9,
        "cikis_lon": 32.85,
        "varis_lat": 41.0,
        "varis_lon": 29.0,
    }
    monkeypatch.setattr(
        "v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork",
        lambda: _FakeUoWWithLokasyon(full),
    )
    _patch_container_weather(
        monkeypatch,
        _FakeWeatherService(result={"success": True, "fuel_impact_factor": 1.08}),
    )
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(42))
    assert impact == pytest.approx(1.08)


@pytest.mark.asyncio
async def test_weather_service_failure_returns_neutral(monkeypatch):
    """WeatherService success=False döndürürse nötr."""
    full = {
        "cikis_lat": 39.9,
        "cikis_lon": 32.85,
        "varis_lat": 41.0,
        "varis_lon": 29.0,
    }
    monkeypatch.setattr(
        "v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork",
        lambda: _FakeUoWWithLokasyon(full),
    )
    _patch_container_weather(
        monkeypatch,
        _FakeWeatherService(result={"success": False, "error": "geocoding failed"}),
    )
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(42))
    assert impact == 1.0


@pytest.mark.asyncio
async def test_weather_exception_returns_neutral(monkeypatch):
    """WeatherService exception fırlatırsa nötr — akış bloklanmasın."""
    full = {
        "cikis_lat": 39.9,
        "cikis_lon": 32.85,
        "varis_lat": 41.0,
        "varis_lon": 29.0,
    }
    monkeypatch.setattr(
        "v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork",
        lambda: _FakeUoWWithLokasyon(full),
    )
    _patch_container_weather(
        monkeypatch,
        _FakeWeatherService(result=RuntimeError("OpenMeteo timeout")),
    )
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(42))
    assert impact == 1.0


@pytest.mark.asyncio
async def test_weather_null_fuel_impact_returns_neutral(monkeypatch):
    """fuel_impact_factor null → nötr (Pydantic'in çatlamasını engelle)."""
    full = {
        "cikis_lat": 39.9,
        "cikis_lon": 32.85,
        "varis_lat": 41.0,
        "varis_lon": 29.0,
    }
    monkeypatch.setattr(
        "v2.modules.shared_kernel.infrastructure.unit_of_work.UnitOfWork",
        lambda: _FakeUoWWithLokasyon(full),
    )
    _patch_container_weather(
        monkeypatch,
        _FakeWeatherService(result={"success": True, "fuel_impact_factor": None}),
    )
    engine = _make_engine()
    impact = await engine._weather_impact(_make_input(42))
    assert impact == 1.0
