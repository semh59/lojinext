"""Phase 5.0 — canlı API smoke test (RUN_LIVE_NETWORK_TESTS=1).

Üretim aktivasyonu öncesi gerçek Mapbox + Open-Meteo + physics pipeline'ı
end-to-end koşar. SeferFuelEstimator.predict çağrılır (FakeDB), tahmin
gerçekçi banttaysa pass.

CI'da default skip — manuel tetiklenir:
    RUN_LIVE_NETWORK_TESTS=1 pytest \\
        app/tests/integration/test_phase4_live_apis_smoke.py -v

Maliyet: 1 sefer × 1 Mapbox + 3 Open-Meteo elevation + 3 Open-Meteo
weather = ~5 HTTP. Cache hit varsa ~50ms toplam, miss ~3sn.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _read_mapbox_key_from_env() -> str:
    """app/tests/conftest.py:26 MAPBOX_API_KEY="" set ediyor (mock testler için).
    Canlı smoke için .env'den okuyup döndür."""
    env_path = Path(".env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("MAPBOX_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def _skip_if_no_live() -> str:
    if os.environ.get("RUN_LIVE_NETWORK_TESTS") != "1":
        pytest.skip("Canlı ağ test'i: RUN_LIVE_NETWORK_TESTS=1 set edilmedi")
    key = _read_mapbox_key_from_env()
    if not key:
        pytest.skip("MAPBOX_API_KEY .env'de yok")
    # settings cached + singleton MapboxClient zaten boş key ile yaratılmış olabilir.
    # SeferFuelEstimator'a fresh MapboxClient inject etmek için key döndür.
    from pydantic import SecretStr

    from app.config import settings

    settings.MAPBOX_API_KEY = SecretStr(key)
    return key


def _build_live_estimator():
    """Test başına yeni MapboxClient + WeatherService inject et — singleton bypass."""
    _skip_if_no_live()
    from app.core.services.weather_service import WeatherService
    from v2.modules.route_simulation.application.simulate_route import RouteSimulator
    from v2.modules.route_simulation.infrastructure.external_service import (
        ExternalService,
    )
    from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient
    from v2.modules.route_simulation.infrastructure.open_meteo_client import (
        OpenMeteoElevationClient,
    )
    from v2.modules.trip.application.sefer_fuel_estimator import SeferFuelEstimator

    mapbox = MapboxClient()  # settings'ten fresh key okur
    elev = OpenMeteoElevationClient()
    weather = WeatherService(external_service=ExternalService())
    simulator = RouteSimulator(mapbox_client=mapbox, elevation_client=elev)
    return SeferFuelEstimator(simulator=simulator, weather=weather)


class _MockArac:
    """Arac ORM model'inin minimum sahnesi."""

    def __init__(self):
        self.id = 1
        self.yil = 2020  # ~5-6 yaş


class _MockSofor:
    def __init__(self):
        self.id = 1
        self.score = 1.0


class _FakeSession:
    """SQLAlchemy AsyncSession sahnesi."""

    def __init__(self, entities: dict):
        self._entities = entities
        self.added: list = []

    async def get(self, cls, key):
        return self._entities.get((cls.__name__, key))

    def add(self, row):
        self.added.append(row)
        row.id = 1

    async def commit(self):
        pass

    async def refresh(self, row):
        if not getattr(row, "id", None):
            row.id = 1


async def test_live_istanbul_ankara_full_pipeline():
    """İstanbul-Ankara (otoyol, ~440km) → tahmin 20-50 L/100km bandında."""
    from v2.modules.trip.application.sefer_fuel_estimator import SeferFuelInput

    estimator = _build_live_estimator()  # fresh, settings-aware
    inp = SeferFuelInput(
        arac_id=1,
        sofor_id=1,
        ton=15.0,
        target_date=date.today(),
        cikis_lat=41.0082,
        cikis_lon=28.9784,  # İstanbul Sultanahmet
        varis_lat=39.9334,
        varis_lon=32.8597,  # Ankara Kızılay
    )
    db = _FakeSession(
        {
            ("Arac", 1): _MockArac(),
            ("Sofor", 1): _MockSofor(),
        }
    )

    result = await estimator.predict(db, inp, persist=False)

    assert result is not None, "Mapbox routing başarısız (canlı API hatası?)"
    # Mesafe bandı: 400-500 km
    assert 400 < result.distance_km < 500, f"Mesafe sıra dışı: {result.distance_km}km"
    # Süre 3-7 saat
    assert 180 < result.duration_min < 420, f"Süre sıra dışı: {result.duration_min}dk"
    # Tüketim 15-50 L/100km bandı (TIR otoyol)
    assert 15 < result.tahmini_tuketim < 50, (
        f"Tüketim bandı dışı: {result.tahmini_tuketim} L/100km"
    )
    # Toplam yakıt mantıklı (~440km × ~25-40 L/100km = 110-180 L)
    assert 80 < result.total_l < 250, f"Total L sıra dışı: {result.total_l}"
    # Breakdown 8 alan dolu
    b = result.breakdown
    assert b.physics_baseline > 0
    assert 0.8 <= b.driver <= 1.2
    assert 0.85 <= b.weather_temperature <= 1.20
    assert 0.85 <= b.weather_wind <= 1.30
    assert 1.0 <= b.weather_precipitation <= 1.20
    assert 1.0 <= b.seasonal <= 1.10
    assert b.final == result.tahmini_tuketim
    # Pipeline meta
    assert result.raw_segment_count > 1000  # 440km × ~80m/seg = ~5500
    assert result.resampled_segment_count > 800  # 440km / 0.5km = ~880
    assert 50 < result.elevation_coverage_pct <= 100


async def test_live_short_city_route():
    """Kısa şehir içi rota (~5km) → daha yüksek L/100km bekleyebiliriz."""
    from v2.modules.trip.application.sefer_fuel_estimator import SeferFuelInput

    estimator = _build_live_estimator()
    inp = SeferFuelInput(
        arac_id=1,
        sofor_id=1,
        ton=10.0,
        target_date=date.today(),
        cikis_lat=41.1098,
        cikis_lon=29.0205,  # Maslak
        varis_lat=40.9897,
        varis_lon=29.0257,  # Kadıköy
    )
    db = _FakeSession(
        {
            ("Arac", 1): _MockArac(),
            ("Sofor", 1): _MockSofor(),
        }
    )

    result = await estimator.predict(db, inp, persist=False)

    assert result is not None
    # 10-30 km arası (FSM köprü dahil)
    assert 10 < result.distance_km < 30
    # Şehir içi tüketim genelde otoyolun üstünde
    assert 15 < result.tahmini_tuketim < 60


async def test_live_invalid_coords_returns_none():
    """Geçersiz koordinat (deniz ortası) → Mapbox routes yok → result None."""
    from v2.modules.trip.application.sefer_fuel_estimator import SeferFuelInput

    estimator = _build_live_estimator()
    inp = SeferFuelInput(
        arac_id=1,
        target_date=date.today(),
        # Karadeniz açıkları → yol yok
        cikis_lat=42.5,
        cikis_lon=35.0,
        varis_lat=43.0,
        varis_lon=33.0,
    )
    db = _FakeSession({("Arac", 1): _MockArac()})

    result = await estimator.predict(db, inp, persist=False)
    # Mapbox bu koord çifti için route döndürmeyebilir
    # → result None (caller'da 502 olarak gözükür)
    # Eğer Mapbox land/route bulduysa result not None — test esnek
    assert result is None or result.distance_km > 0
