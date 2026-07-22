"""SeferFuelEstimator — sefer kayıt akışı için tek doğruluk kaynağı (Phase 4.3).

Sefer ekranı → tek endpoint → tek tahmin. Arkada:
  Mapbox segments + Open-Meteo elevation + Open-Meteo weather + physics +
  adjustment factors → route_simulations persist

Pipeline:

    SeferFuelInput
        │
        ├─ 1. Resource Loading (UoW): arac/sofor/dorse + health_input
        ├─ 2. Route Resolution: lokasyon_id → coords, veya ad-hoc
        ├─ 3. Physics + segment + elevation (RouteSimulator.simulate)
        ├─ 4. Weather samples (route midpoints) — P4.1
        ├─ 5. Adjustment factors (driver + age + maintenance + weather*3 + seasonal) — P4.2
        ├─ 6. ML correction (cold start: physics_weight=1.0, ensemble bypass)
        └─ 7. Persist route_simulations + return SeferFuelEstimate

Plan: docs/superpowers/plans/2026-05-30-phase4-fuel-estimator-plan.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as dt_date
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from app.config import settings
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.fleet.public import Dorse
from v2.modules.location.public import Lokasyon
from v2.modules.platform_infra.public import AsyncSessionLocal, get_logger
from v2.modules.prediction_ml.public import (
    combine_factors,
    weather_precipitation_factor,
    weather_temperature_factor,
    weather_wind_factor,
)
from v2.modules.route_simulation.public import RouteSegment, RouteSimulation

if TYPE_CHECKING:
    from v2.modules.driver.public import Sofor

from v2.modules.route_simulation.public import (
    RouteSimulator,
    SimulationResult,
    WeatherSample,
    WeatherService,
    get_route_simulator,
)

logger = get_logger(__name__)


# ── Dataclass'lar ────────────────────────────────────────────────────────


@dataclass
class SeferFuelInput:
    """Sefer ekranından gelen tahmin girdileri."""

    arac_id: int
    target_date: dt_date
    ton: float = 0.0
    sofor_id: Optional[int] = None
    dorse_id: Optional[int] = None
    bos_sefer: bool = False
    # Route — biri zorunlu (lokasyon_id veya 4 koord)
    lokasyon_id: Optional[int] = None
    cikis_lat: Optional[float] = None
    cikis_lon: Optional[float] = None
    varis_lat: Optional[float] = None
    varis_lon: Optional[float] = None
    segment_length_m: int = 500


@dataclass
class FactorBreakdown:
    """Tahminin parçalarını UI/debug için raporlar."""

    physics_baseline: float  # L/100km
    driver: float = 1.0  # multiplier
    vehicle_age: float = 1.0
    maintenance: float = 1.0
    weather_temperature: float = 1.0
    weather_wind: float = 1.0
    weather_precipitation: float = 1.0
    seasonal: float = 1.0
    ml_correction_weight: float = 0.0  # cold start = 0
    final: float = 0.0  # L/100km


@dataclass
class SeferFuelEstimate:
    """Servisin döndürdüğü sonuç paketi."""

    tahmini_tuketim: float  # L/100km (sefer.tahmini_tuketim'e yazılır)
    total_l: float  # final × distance
    distance_km: float
    duration_min: float
    simulation_id: Optional[int]  # route_simulations.id (None = persist atlandı)
    breakdown: FactorBreakdown
    elevation_coverage_pct: float = 0.0
    raw_segment_count: int = 0
    resampled_segment_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_legacy_prediction_dict(self) -> Dict[str, Any]:
        """Eski ``predict_consumption`` dict shape'ine adapter (Phase 4.4).

        SeferWriteService ``_extract_prediction_values`` helper'ı eski
        format'a göre yazılmış. Bu helper sayesinde sefer akışı
        değişikliği minimum: SeferFuelEstimator → bu dict → mevcut helper.
        """
        return {
            "tahmini_tuketim": self.tahmini_tuketim,
            "tahmin_l_100km": self.tahmini_tuketim,
            "physics_only": self.breakdown.physics_baseline,
            "ml_correction": round(
                self.tahmini_tuketim - self.breakdown.physics_baseline, 2
            ),
            "physics_weight": 1.0 - self.breakdown.ml_correction_weight,
            "confidence_low": round(self.tahmini_tuketim * 0.9, 1),
            "confidence_high": round(self.tahmini_tuketim * 1.1, 1),
            "factors_used": {
                "physics_baseline": self.breakdown.physics_baseline,
                "driver": self.breakdown.driver,
                "vehicle_age": self.breakdown.vehicle_age,
                "maintenance": self.breakdown.maintenance,
                "weather_temperature": self.breakdown.weather_temperature,
                "weather_wind": self.breakdown.weather_wind,
                "weather_precipitation": self.breakdown.weather_precipitation,
                "seasonal": self.breakdown.seasonal,
                "ml_correction_weight": self.breakdown.ml_correction_weight,
                "final": self.breakdown.final,
                "source": "SeferFuelEstimator",
            },
            "simulation_id": self.simulation_id,
            "distance_km": self.distance_km,
            "duration_min": self.duration_min,
            "total_l": self.total_l,
        }


# ── Estimator ────────────────────────────────────────────────────────────


class SeferFuelEstimator:
    """Sefer kayıt akışı için tek doğruluk kaynağı yakıt tahmini."""

    # ML cold-start: physics ağırlığı 1.0 → ensemble bypass.
    # Phase 5 kalibrasyondan sonra dinamik (vehicle.physics_weight'ten okunur).
    DEFAULT_PHYSICS_WEIGHT = 1.0

    def __init__(
        self,
        simulator: Optional[RouteSimulator] = None,
        weather: Optional[WeatherService] = None,
    ) -> None:
        self._simulator = simulator or get_route_simulator()
        self._weather = weather or WeatherService()

    async def predict(
        self,
        inp: SeferFuelInput,
        *,
        persist: bool = True,
        session: Any = None,
    ) -> Optional[SeferFuelEstimate]:
        """Sefer için yakıt tahmini.

        Args:
            inp: SeferFuelInput.
            persist: True → route_simulations + route_segments insert.
            session: Mevcut AsyncSession (UoW'dan) geçilirse commit caller'a ait
                     → sefer ve simülasyon aynı transaction'da atomik. None ise
                     bağımsız session açılır (backfill, test vb.).

        Returns:
            SeferFuelEstimate (None → Mapbox routing başarısız veya invalid input).
        """
        # 1 + 2: Load entities and resolve route — release DB before external IO.
        async with AsyncSessionLocal() as db:
            arac, sofor, dorse = await self._load_entities(db, inp)
            if arac is None:
                logger.warning("SeferFuelEstimator: arac %s bulunamadı", inp.arac_id)
                return None
            cikis_lon, cikis_lat, varis_lon, varis_lat = await self._resolve_route(
                db, inp
            )
            maintenance_factor = await self._fetch_maintenance_factor(db, arac.id)
        # DB connection released — external IO follows without holding a pool slot.

        if cikis_lon is None:
            logger.warning("SeferFuelEstimator: rota koordinatları çözülemedi")
            return None

        # 3. Physics + segment + elevation (external IO: Mapbox + Open-Meteo)
        ton = 0.0 if inp.bos_sefer else inp.ton
        arac_yasi = self._derive_arac_yasi(arac)
        sim_result = await self._simulator.simulate(
            cikis_lon=cikis_lon,
            cikis_lat=cikis_lat,
            varis_lon=varis_lon,
            varis_lat=varis_lat,
            ton=ton,
            arac_yasi=arac_yasi,
            target_length_km=inp.segment_length_m / 1000.0,
        )
        if sim_result is None:
            logger.warning(
                "SeferFuelEstimator: Mapbox routing unavailable for arac=%s",
                inp.arac_id,
            )
            return None

        physics_baseline = sim_result.summary.avg_l_per_100km

        # 4. Weather samples (external IO: Open-Meteo)
        weather_samples = await self._fetch_weather_samples(sim_result)

        # 5. Adjustment factors (CPU only)
        breakdown = self._compute_factors(
            physics_baseline=physics_baseline,
            sofor=sofor,
            arac=arac,
            weather_samples=weather_samples,
            target_date=inp.target_date,
            maintenance_factor=maintenance_factor,
        )

        # 6. ML correction — cold start bypass (Phase 5'te aktif)
        # final = physics_weight × physics_adjusted + (1-pw) × ml_estimate
        # Şu an pw=1.0, ensemble bypass.
        physics_adjusted = physics_baseline * combine_factors(
            driver=breakdown.driver,
            vehicle_age=breakdown.vehicle_age,
            maintenance=breakdown.maintenance,
            weather_temperature=breakdown.weather_temperature,
            weather_wind=breakdown.weather_wind,
            weather_precipitation=breakdown.weather_precipitation,
            seasonal=breakdown.seasonal,
        )
        breakdown.final = round(physics_adjusted, 2)

        # 7. Total ve persist — new DB connection only when needed.
        distance_km = sim_result.summary.total_km
        total_l = round(breakdown.final * distance_km / 100.0, 2)
        duration_min = round(sim_result.summary.total_eta_sec / 60.0, 1)

        simulation_id: Optional[int] = None
        if persist:
            simulation_id = await self._persist(
                inp=inp,
                sim=sim_result,
                breakdown=breakdown,
                distance_km=distance_km,
                total_l=total_l,
                duration_min=duration_min,
                arac_yasi=arac_yasi,
                session=session,
            )

        return SeferFuelEstimate(
            tahmini_tuketim=breakdown.final,
            total_l=total_l,
            distance_km=distance_km,
            duration_min=duration_min,
            simulation_id=simulation_id,
            breakdown=breakdown,
            elevation_coverage_pct=sim_result.elevation_coverage_pct,
            raw_segment_count=sim_result.raw_segment_count,
            resampled_segment_count=sim_result.resampled_segment_count,
            meta={
                "arac_id": inp.arac_id,
                "sofor_id": inp.sofor_id,
                "lokasyon_id": inp.lokasyon_id,
                "ton": inp.ton,
                "arac_yasi": arac_yasi,
                "bos_sefer": inp.bos_sefer,
            },
        )

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _load_entities(
        self, db: Any, inp: SeferFuelInput
    ) -> Tuple[Optional[Arac], Optional[Sofor], Optional[Dorse]]:
        from v2.modules.driver.public import Sofor

        arac: Optional[Arac] = await db.get(Arac, inp.arac_id) if inp.arac_id else None
        sofor = await db.get(Sofor, inp.sofor_id) if inp.sofor_id else None
        dorse = await db.get(Dorse, inp.dorse_id) if inp.dorse_id else None
        return arac, sofor, dorse

    async def _resolve_route(
        self, db: Any, inp: SeferFuelInput
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """lokasyon_id varsa lokasyon koordlarını al; yoksa ad-hoc."""
        if inp.lokasyon_id is not None:
            lok: Optional[Lokasyon] = await db.get(Lokasyon, inp.lokasyon_id)
            if lok is None:
                return None, None, None, None
            if (
                lok.cikis_lat is None
                or lok.cikis_lon is None
                or lok.varis_lat is None
                or lok.varis_lon is None
            ):
                return None, None, None, None
            return lok.cikis_lon, lok.cikis_lat, lok.varis_lon, lok.varis_lat

        # Ad-hoc
        if (
            inp.cikis_lon is None
            or inp.cikis_lat is None
            or inp.varis_lon is None
            or inp.varis_lat is None
        ):
            return None, None, None, None
        return inp.cikis_lon, inp.cikis_lat, inp.varis_lon, inp.varis_lat

    async def _fetch_weather_samples(
        self, sim: SimulationResult
    ) -> List[Optional[WeatherSample]]:
        """Route boundary coords'tan weather samples — orta noktayla yetin."""
        coords = sim.boundary_coords
        if not coords:
            return []
        # En fazla 3 nokta yeterli: başlangıç + orta + son (hava güzergah
        # boyunca lineer değişir). Aşırı çağrı yapmamak için.
        sampling: List[Tuple[float, float]] = []
        if len(coords) >= 1:
            sampling.append(coords[0])
        if len(coords) >= 3:
            sampling.append(coords[len(coords) // 2])
        if len(coords) >= 2:
            sampling.append(coords[-1])
        try:
            return await self._weather.get_route_weather_samples(sampling)
        except Exception as exc:
            logger.warning("Weather samples failed (non-fatal): %s", exc)
            # Weather fetch failure degrades the estimate silently: temp/wind/
            # precip adjustment factors fall back to neutral (1.0). Record it on
            # the same probe as its elevation sibling so ops can alarm on a rate
            # instead of grepping WARNING lines.
            from v2.modules.platform_infra.public import record_silent_fallback

            record_silent_fallback(
                "open_meteo_weather_failed", error=type(exc).__name__
            )
            return []

    def _derive_arac_yasi(self, arac: Optional[Arac]) -> int:
        """Arac modelinden yas çıkar — DB yoksa fallback 5.

        `araclar` tablosunda `uretim_tarihi` kolonu hiç yok (sadece `yil`) —
        önceki implementasyon var-olmayan bir kolonu okuyordu ve bu yüzden
        canlıda HER araç için sessizce 5'e düşüyordu (Tier B madde 12).
        `entities/models.py::Arac.yas` ile aynı tek kaynağa (`yil`) hizalandı.
        """
        if arac is None:
            return 5
        yil = getattr(arac, "yil", None)
        if yil is None:
            return 5
        years = dt_date.today().year - yil
        return max(0, years)

    async def _fetch_maintenance_factor(self, db: Any, arac_id: int) -> float:
        """Bakım/arıza verisinden yakıt çarpanı (D.4).

        Flag kapalı veya hata → 1.0 (nötr). ``no_history_factor=1.0`` ile
        PERIYODIK kaydı olmayan araç (şu an çoğu) tam 1.0 = bugünkü davranışla
        birebir → p51/tahmin kayması YOK; sadece gerçek açık ARIZA/ACIL +
        tamamlanmış PERIYODIK sinyali faktörü oynatır.
        """
        if not settings.MAINTENANCE_FACTOR_ENABLED:
            return 1.0
        try:
            from types import SimpleNamespace

            from v2.modules.prediction_ml.public import (
                compute_maintenance_factor,
                fetch_health_input,
            )

            health = await fetch_health_input(SimpleNamespace(session=db), arac_id)
            return compute_maintenance_factor(health, no_history_factor=1.0).factor
        except Exception as e:  # tahmini asla bozma
            logger.warning("maintenance_factor hesaplanamadı: %s", e)
            return 1.0

    def _compute_factors(
        self,
        *,
        physics_baseline: float,
        sofor: Optional[Sofor],
        arac: Optional[Arac],
        weather_samples: List[Optional[WeatherSample]],
        target_date: dt_date,
        maintenance_factor: float = 1.0,
    ) -> FactorBreakdown:
        """Adjustment factors hesabı (driver/age/maintenance/weather*3/seasonal)."""
        # Driver — predict_consumption:677 formülü reuse
        s_score = float(sofor.score) if (sofor and sofor.score) else 1.0
        driver_factor = max(0.8, min(1.2, 1.0 + (1.0 - s_score) * 0.2))

        # Age — Arac.yas_faktoru benzer formül (ORM model'de property yok)
        arac_yasi = self._derive_arac_yasi(arac)
        if arac_yasi <= 2:
            age_factor = 0.98
        elif arac_yasi <= 5:
            age_factor = 1.0
        elif arac_yasi <= 10:
            age_factor = 1.02 + (arac_yasi - 5) * 0.005
        else:
            age_factor = 1.05 + (arac_yasi - 10) * 0.01
        age_factor = min(1.15, age_factor)

        # Maintenance (D.4) — caller'dan inject edilir (_fetch_maintenance_factor).
        # Flag kapalı / veri yok → 1.0 (nötr); gerçek açık ARIZA/ACIL + PERIYODIK
        # sinyali olan araçta devreye girer.

        # Weather — sample listesini ortalama
        avg_temp: Optional[float] = self._avg(
            [s.temperature_2m for s in weather_samples if s]
        )
        avg_wind: Optional[float] = self._avg(
            [s.wind_speed_10m for s in weather_samples if s]
        )
        avg_wind_dir: Optional[float] = self._avg(
            [s.wind_direction_10m for s in weather_samples if s]
        )
        avg_precip: Optional[float] = self._avg(
            [s.precipitation for s in weather_samples if s]
        )
        # snowfall samples'ta yoksa varsayılan 0
        snow_vals = [
            s.snowfall for s in weather_samples if s and s.snowfall is not None
        ]
        avg_snow = (sum(snow_vals) / len(snow_vals)) if snow_vals else None

        wt_factor = weather_temperature_factor(avg_temp)
        ww_factor = weather_wind_factor(
            wind_speed_kmh=avg_wind,
            wind_bearing_deg=avg_wind_dir,
            segment_bearing_deg=None,  # P4.4'te sefer rotasının yönü hesaplanır
        )
        wp_factor = weather_precipitation_factor(avg_precip, snowfall_cm=avg_snow)

        # Seasonal — WeatherService mevcut formülü
        seasonal_factor = self._weather.get_seasonal_factor(target_date)

        return FactorBreakdown(
            physics_baseline=round(physics_baseline, 2),
            driver=round(driver_factor, 3),
            vehicle_age=round(age_factor, 3),
            maintenance=round(maintenance_factor, 3),
            weather_temperature=round(wt_factor, 3),
            weather_wind=round(ww_factor, 3),
            weather_precipitation=round(wp_factor, 3),
            seasonal=round(seasonal_factor, 3),
            ml_correction_weight=0.0,
            final=0.0,  # caller dolduracak
        )

    @staticmethod
    def _avg(values: List[Optional[float]]) -> Optional[float]:
        clean = [v for v in values if v is not None]
        return (sum(clean) / len(clean)) if clean else None

    async def _persist(
        self,
        *,
        inp: SeferFuelInput,
        sim: SimulationResult,
        breakdown: FactorBreakdown,
        distance_km: float,
        total_l: float,
        duration_min: float,
        arac_yasi: int,
        session: Any = None,
    ) -> int:
        """route_simulations + route_segments insert. simulation_id döner.

        session verilirse flush+refresh yapılır (commit caller'a bırakılır → atomik).
        session=None ise bağımsız AsyncSessionLocal açılır ve commit edilir.
        """
        row = RouteSimulation(
            lokasyon_id=inp.lokasyon_id,
            cikis_lat=sim.boundary_coords[0][1] if sim.boundary_coords else 0.0,
            cikis_lon=sim.boundary_coords[0][0] if sim.boundary_coords else 0.0,
            varis_lat=sim.boundary_coords[-1][1] if sim.boundary_coords else 0.0,
            varis_lon=sim.boundary_coords[-1][0] if sim.boundary_coords else 0.0,
            ton=inp.ton,
            arac_yasi=arac_yasi,
            target_length_km=inp.segment_length_m / 1000.0,
            raw_segment_count=sim.raw_segment_count,
            resampled_segment_count=sim.resampled_segment_count,
            elevation_coverage_pct=sim.elevation_coverage_pct,
            total_km=distance_km,
            total_l=total_l,
            avg_l_per_100km=breakdown.final,
            total_eta_sec=sim.summary.total_eta_sec,
            total_ascent_m=sim.summary.total_ascent_m,
            total_descent_m=sim.summary.total_descent_m,
            created_at=datetime.now(timezone.utc),
        )
        # Segment değerleri salt-fizik (RouteSimulator çıktısı). Header total_l
        # ise combine_factors düzeltmesini içerir. Tutarlılık için aynı çarpanı
        # segment bazına uygula → Σ sim_l_total == route_simulations.total_l.
        physics_total = sim.summary.total_l
        adj_factor = total_l / physics_total if physics_total > 0 else 1.0

        for i, seg in enumerate(sim.summary.segments):
            mid_lon: Optional[float] = None
            mid_lat: Optional[float] = None
            if i + 1 < len(sim.boundary_coords):
                mid_lon = (
                    sim.boundary_coords[i][0] + sim.boundary_coords[i + 1][0]
                ) / 2.0
                mid_lat = (
                    sim.boundary_coords[i][1] + sim.boundary_coords[i + 1][1]
                ) / 2.0
            row.segments.append(
                RouteSegment(
                    seq=i,
                    length_km=seg.length_km,
                    grade_pct=seg.grade_pct,
                    road_class=seg.road_class or None,
                    maxspeed_kmh=seg.maxspeed_kmh,
                    traffic_speed_kmh=seg.traffic_speed_kmh,
                    congestion=seg.congestion,
                    sim_speed_kmh=seg.sim_speed_kmh,
                    sim_l_per_100km=round(seg.sim_l_per_100km * adj_factor, 4),
                    sim_l_total=round(seg.sim_l_total * adj_factor, 4),
                    eta_sec=seg.eta_sec,
                    mid_lon=mid_lon,
                    mid_lat=mid_lat,
                )
            )
        if session is not None:
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return int(row.id)
        async with AsyncSessionLocal() as db:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return int(row.id)


# ── Singleton getter ─────────────────────────────────────────────────────

_default_estimator: Optional[SeferFuelEstimator] = None


def get_sefer_fuel_estimator() -> SeferFuelEstimator:
    """Lazy singleton."""
    global _default_estimator
    if _default_estimator is None:
        _default_estimator = SeferFuelEstimator()
    return _default_estimator


__all__ = [
    "SeferFuelInput",
    "SeferFuelEstimate",
    "FactorBreakdown",
    "SeferFuelEstimator",
    "get_sefer_fuel_estimator",
]
