"""
TIR Yakıt Takip - Gelişmiş Fizik Tabanlı Yakıt Tahmin Motoru
Enerji formülleri + ML hibrit yaklaşım
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Prometheus counter — gracefully no-ops if prometheus_client not installed.
# Typed Any because the real Counter and the _Noop fallback are not related.
_physics_outlier_counter: Any
try:
    from prometheus_client import Counter as _PCounter

    _physics_outlier_counter = _PCounter(
        "physics_prediction_outlier_total",
        "Physics predictions exceeding MAX_REALISTIC_L_100KM clamp threshold",
    )
except Exception:

    class _Noop:  # pragma: no cover
        def inc(self):
            pass

    _physics_outlier_counter = _Noop()


@dataclass
class VehicleSpecs:
    """Araç teknik özellikleri"""

    empty_weight_kg: float = 8000  # Tractor only (Standard)
    trailer_empty_weight_kg: float = 6500  # Trailer only (Standard)
    drag_coefficient: float = 0.52  # Tractor only Cd
    trailer_drag_contribution: float = 0.13  # Trailer contribution to Cd
    frontal_area_m2: float = 8.2
    rolling_resistance: float = 0.007
    # Faz 7 — payload duyarlılığı literatüre kalibre edildi.
    # Düz yol marjinal duyarlılık = 64.13 × trailer_rolling_resistance L/100km/ton
    # (türetme: ΔF=1000·g·rr, ΔE/100km=ΔF·1e5; fuel=ΔE/eff/45.8/0.835).
    # Hedef 0.473 L/100km/ton (DAF XF480: 19.3t→33.0, 2.6t→25.1 L/100km @79km/h;
    # ICCT 40t long-haul baseline 33.1 ile uyumlu) → rr = 0.473/64.13 = 0.00738.
    # Eski 0.006 yalnız 0.385 L/100km/ton veriyordu (yük etkisi eksik tahmin).
    trailer_rolling_resistance: float = 0.00738
    engine_efficiency: float = 0.40
    fuel_density_kg_l: float = 0.835
    fuel_energy_mj_kg: float = 45.8
    engine_power_w: float = 400_000.0  # Euro 6 TIR nominal shaft power

    def __post_init__(self):
        if self.engine_efficiency <= 0:
            raise ValueError("Engine efficiency must be greater than 0")
        if self.fuel_density_kg_l <= 0:
            raise ValueError("Fuel density must be greater than 0")


@dataclass
class RouteConditions:
    """Rota koşulları"""

    distance_km: float
    load_ton: float
    is_empty_trip: bool = False  # Faz 3: Boş sefer bayrağı
    ascent_m: float = 0  # Toplam tırmanış (metre)
    descent_m: float = 0  # Toplam iniş (metre)
    flat_distance_km: float = 0  # Düz yol mesafesi (km)
    avg_speed_kmh: float = 70  # Ortalama hız
    road_quality: float = 1.0  # Yol kalitesi faktörü (1.0 = normal)
    weather_factor: float = 1.0  # Hava durumu faktörü (1.0 = normal)
    # Phase 5A: Grade distribution (% of climb at each band) - Refined
    grade_gentle_pct: float = 0.8  # 0–2.5% grade (motorway/trunk)
    grade_moderate_pct: float = 0.15  # 2.5–5.5% grade (primary roads)
    grade_steep_pct: float = 0.05  # 5.5%+ grade (mountain passes)
    # Phase 5A: Stop-go proxy
    stopgo_cycles_per_100km: float = 5.0
    # Phase 6: Road type distribution
    otoyol_ratio: float = 0.6
    devlet_yolu_ratio: float = 0.3
    sehir_ici_ratio: float = 0.1
    arac_yasi: int = 5  # Araç yaşı (Gravity Recovery hesabı için)
    route_analysis: Optional[Dict[str, Dict[str, float]]] = None


@dataclass
class FuelPrediction:
    """Yakıt tahmin sonucu"""

    total_liters: float
    consumption_l_100km: float
    energy_breakdown: Dict[str, float]
    confidence_range: Tuple[float, float]
    # Mixed-type metadata (float metrikler + "model" gibi str/bool bayraklar).
    factors_used: Dict[str, Any]
    insight: Optional[str] = None


class PhysicsBasedFuelPredictor:
    """
    Fizik tabanlı yakıt tüketim tahmini.
    """

    # Fiziksel sabitler
    GRAVITY = 9.81  # m/s²
    AIR_DENSITY = 1.225  # kg/m³ (deniz seviyesi)
    MAX_REALISTIC_L_100KM = 65.0
    MIN_REALISTIC_L_100KM = 15.0

    def __init__(self, vehicle: VehicleSpecs = None):
        self.vehicle = vehicle if vehicle else VehicleSpecs()

    def _equilibrium_speed_ms(
        self,
        nominal_v_ms: float,
        grade_pct: float,
        total_mass_kg: float,
    ) -> float:
        """
        Solve for the truck speed where engine power equals total road resistance.

        On steep upgrades a loaded TIR cannot sustain highway speed: the required
        power (drag + rolling + climbing) exceeds the engine limit and the truck
        slows to an equilibrium. Solves P(v) = (k_drag×v² + F_resid)×v = P_engine
        via 24-step binary search (converges to < 0.01 m/s error).

        Downhill / flat (grade ≤ 0): gravity assist — nominal speed maintained.
        """
        if grade_pct <= 0.0:
            return nominal_v_ms

        combined_cd = (
            self.vehicle.drag_coefficient + self.vehicle.trailer_drag_contribution
        )
        k_drag = 0.5 * self.AIR_DENSITY * combined_cd * self.vehicle.frontal_area_m2

        # Simplified combined rolling resistance
        f_roll = (
            total_mass_kg
            * self.GRAVITY
            * (
                (
                    self.vehicle.rolling_resistance
                    + self.vehicle.trailer_rolling_resistance
                )
                / 2.0
            )
        )
        f_climb = total_mass_kg * self.GRAVITY * (grade_pct / 100.0)
        f_resid = f_roll + f_climb

        p_engine = self.vehicle.engine_power_w

        # Fast path: nominal speed is achievable within engine power
        if (k_drag * nominal_v_ms**2 + f_resid) * nominal_v_ms <= p_engine:
            return nominal_v_ms

        # Binary search for equilibrium speed
        lo, hi = 5.0, nominal_v_ms
        for _ in range(24):
            mid = (lo + hi) * 0.5
            if (k_drag * mid**2 + f_resid) * mid < p_engine:
                lo = mid
            else:
                hi = mid

        return max(lo, 5.0)  # floor at ~18 km/h

    @staticmethod
    def _get_gravity_recovery(arac_yasi: int) -> float:
        """Araç yaşına göre dinamik Gravity Recovery faktörü."""
        if arac_yasi <= 3:
            return 0.90
        elif arac_yasi <= 6:
            return 0.80
        elif arac_yasi <= 10:
            return 0.68
        return 0.60

    def _build_segments(
        self, route: RouteConditions
    ) -> List[Tuple[float, float, float]]:
        analysis = (
            route.route_analysis if isinstance(route.route_analysis, dict) else None
        )
        speed_map = {
            "motorway": route.avg_speed_kmh,
            "trunk": route.avg_speed_kmh * 0.9,
            "primary": route.avg_speed_kmh * 0.8,
            "secondary": route.avg_speed_kmh * 0.65,
            "tertiary": route.avg_speed_kmh * 0.55,
            "residential": route.avg_speed_kmh * 0.55,
            "unclassified": route.avg_speed_kmh * 0.7,
            "other": route.avg_speed_kmh * 0.75,
        }

        # Path 1: joint road×grade distribution — preferred summary mode when present.
        # Grade midpoints give calibrated elevation per segment; scale_up/scale_down
        # anchors total elevation to the known ascent_m / descent_m.
        _GRADE_MID = {
            "downhill_steep": -10.0,
            "downhill_moderate": -5.5,
            "flat": 0.0,
            "uphill_moderate": 5.5,
            "uphill_steep": 10.0,
        }
        distributions = (analysis or {}).get("distributions") if analysis else None
        road_grade: Any = (
            (distributions or {}).get("road_grade") if distributions else {}
        )
        if road_grade:
            raw: List[Tuple[float, float, float]] = []
            for key, pct in road_grade.items():
                if not pct:
                    continue
                parts = key.split("+", 1)
                if len(parts) != 2:
                    continue
                road_cls, grade_cls = parts
                dist_m = route.distance_km * 1000.0 * pct / 100.0
                speed_ms = speed_map.get(road_cls, route.avg_speed_kmh) / 3.6
                delta_h = dist_m * _GRADE_MID.get(grade_cls, 0.0) / 100.0
                raw.append((dist_m, speed_ms, delta_h))

            if raw:
                raw_ascent = sum(d for _, _, d in raw if d > 0)
                raw_descent = abs(sum(d for _, _, d in raw if d < 0))
                s_up = route.ascent_m / raw_ascent if raw_ascent > 0 else 1.0
                s_dn = route.descent_m / raw_descent if raw_descent > 0 else 1.0
                return [
                    (dm, vm, dh * s_up if dh > 0 else dh * s_dn if dh < 0 else 0.0)
                    for dm, vm, dh in raw
                ]

        # Path 2: road-category km breakdown (flat/up/down per road class)
        if analysis:
            total_up_km = sum(
                float((cat or {}).get("up", 0) or 0) for cat in analysis.values()
            )
            total_down_km = sum(
                float((cat or {}).get("down", 0) or 0) for cat in analysis.values()
            )
            segments: List[Tuple[float, float, float]] = []

            for cat_name, cat in analysis.items():
                if not isinstance(cat, dict):
                    continue
                speed_ms = speed_map.get(cat_name, route.avg_speed_kmh) / 3.6
                flat_km = float(cat.get("flat", 0) or 0)
                up_km = float(cat.get("up", 0) or 0)
                down_km = float(cat.get("down", 0) or 0)

                if flat_km > 0:
                    segments.append((flat_km * 1000, speed_ms, 0.0))
                if up_km > 0:
                    climb_share = up_km / total_up_km if total_up_km > 0 else 0.0
                    segments.append(
                        (up_km * 1000, speed_ms * 0.85, route.ascent_m * climb_share)
                    )
                if down_km > 0:
                    descent_share = (
                        down_km / total_down_km if total_down_km > 0 else 0.0
                    )
                    segments.append(
                        (down_km * 1000, speed_ms, -route.descent_m * descent_share)
                    )

            covered_km = sum(segment[0] for segment in segments) / 1000.0
            if route.distance_km > covered_km:
                segments.append(
                    (
                        (route.distance_km - covered_km) * 1000,
                        route.avg_speed_kmh / 3.6,
                        0.0,
                    )
                )
            if segments:
                return segments

        flat_km = min(max(route.flat_distance_km, 0.0), max(route.distance_km, 0.0))
        remaining_km = max(route.distance_km - flat_km, 0.0)
        total_grade = max(route.ascent_m + route.descent_m, 0.0)
        climb_share = (route.ascent_m / total_grade) if total_grade > 0 else 0.5
        up_km = remaining_km * climb_share if route.ascent_m > 0 else 0.0
        down_km = (
            remaining_km - up_km
            if route.descent_m > 0
            else max(0.0, remaining_km - up_km)
        )

        segments = []
        if flat_km > 0:
            segments.append((flat_km * 1000, route.avg_speed_kmh / 3.6, 0.0))
        if up_km > 0:
            segments.append(
                (up_km * 1000, route.avg_speed_kmh * 0.85 / 3.6, route.ascent_m)
            )
        if down_km > 0:
            segments.append(
                (down_km * 1000, route.avg_speed_kmh / 3.6, -route.descent_m)
            )

        if segments:
            return segments

        return [
            (route.distance_km * 0.6 * 1000, route.avg_speed_kmh / 3.6, 0.0),
            (
                route.distance_km * 0.2 * 1000,
                route.avg_speed_kmh * 0.8 / 3.6,
                route.ascent_m,
            ),
            (
                route.distance_km * 0.2 * 1000,
                route.avg_speed_kmh / 3.6,
                -route.descent_m,
            ),
        ]

    def predict(
        self, route: RouteConditions, historical_stats: Optional[Dict] = None
    ) -> FuelPrediction:
        """Simple prediction with legacy summary mode"""
        p2p_sim = self._build_segments(route)
        return self.predict_granular(
            p2p_sim,
            route.load_ton,
            route.is_empty_trip,
            historical_stats=historical_stats,
            arac_yasi=route.arac_yasi,
        )

    def predict_granular(
        self,
        segments: List[Tuple[float, float, float]],
        load_ton: float,
        is_empty_trip: bool = False,
        historical_stats: Optional[Dict] = None,
        **kwargs,
    ) -> FuelPrediction:
        """
        Calculate fuel consumption using point-to-point energy integration.
        segments: List of (distance_m, velocity_ms, elevation_diff_m)
        """
        effective_load = 0.0 if is_empty_trip else load_ton
        total_mass = (
            self.vehicle.empty_weight_kg
            + self.vehicle.trailer_empty_weight_kg
            + (effective_load * 1000)
        )
        arac_yasi = kwargs.get("arac_yasi", 5)

        # Segment-tractive model (flag): fiziksel-doğru per-segment yol.
        # Flag kapalıyken eski aggregate davranış korunur (rollback).
        from app.config import settings

        if settings.USE_SEGMENT_TRACTIVE_MODEL:
            return self.predict_segment_tractive(
                segments,
                total_mass_kg=total_mass,
                arac_yasi=arac_yasi,
                silent_outlier_log=kwargs.get("silent_outlier_log", False),
            )

        e_rolling_total = 0.0
        e_air_total = 0.0
        e_climb_total = 0.0
        e_descent_total = 0.0
        total_dist_km = 0.0

        for dist_m, v_ms, delta_h in segments:
            if dist_m <= 0:
                continue

            # Grade-corrected speed: a loaded TIR cannot sustain highway speed on
            # steep upgrades. Correcting v here fixes the drag term (∝ v²) without
            # touching climbing energy (E = m×g×Δh, speed-independent).
            grade_pct = (delta_h / dist_m) * 100.0
            if grade_pct > 0.5:
                v_ms = self._equilibrium_speed_ms(v_ms, grade_pct, total_mass)

            # Deadband for precision noise
            deadband = 0.3 if v_ms < 15 else (1.0 if v_ms > 22 else 0.5)
            h_eff = delta_h if abs(delta_h) >= deadband else 0.0

            total_dist_km += dist_m / 1000.0

            # 1. Rolling Resistance (Split Tractor/Trailer)
            tractor_mass = self.vehicle.empty_weight_kg
            trailer_and_load_mass = self.vehicle.trailer_empty_weight_kg + (
                effective_load * 1000
            )

            f_roll_tractor = (
                tractor_mass * self.GRAVITY * self.vehicle.rolling_resistance
            )
            f_roll_trailer = (
                trailer_and_load_mass
                * self.GRAVITY
                * self.vehicle.trailer_rolling_resistance
            )
            f_roll = f_roll_tractor + f_roll_trailer
            e_rolling_total += f_roll * dist_m

            # 2. Air Drag (Combined Cd)
            combined_cd = (
                self.vehicle.drag_coefficient + self.vehicle.trailer_drag_contribution
            )
            f_air = (
                0.5
                * self.AIR_DENSITY
                * combined_cd
                * self.vehicle.frontal_area_m2
                * (v_ms**2)
            )
            e_air_total += f_air * dist_m

            # 3. Grade resistance
            f_grade = total_mass * self.GRAVITY * (h_eff / dist_m if dist_m > 0 else 0)
            if f_grade > 0:
                e_climb_total += f_grade * dist_m * 1.05
            else:
                recovery_efficiency = self._get_gravity_recovery(arac_yasi)
                e_descent_total += abs(f_grade) * dist_m * recovery_efficiency

        total_energy_mj = (
            e_rolling_total + e_air_total + e_climb_total - e_descent_total
        ) / 1e6
        total_energy_mj = max(0.1, total_energy_mj)

        fuel_energy_needed_mj = total_energy_mj / self.vehicle.engine_efficiency
        fuel_mass_kg = fuel_energy_needed_mj / self.vehicle.fuel_energy_mj_kg
        fuel_liters = fuel_mass_kg / self.vehicle.fuel_density_kg_l

        if not np.isfinite(fuel_liters):
            fuel_liters = 0.0
        consumption_l_100km = (
            (fuel_liters / total_dist_km * 100) if total_dist_km > 0 else 0.0
        )

        # Out-of-range guard: log and count rather than silently clamp.
        # Per-segment çağrılarda (örn. simulate_segment 500m bucket) lokal
        # L/100km doğal olarak route ortalamasından sapar; caller log'u
        # `silent_outlier_log=True` ile kapatabilir.
        if consumption_l_100km > self.MAX_REALISTIC_L_100KM:
            if not kwargs.get("silent_outlier_log", False):
                logger.warning(
                    "physics_prediction_outlier: %.1f l/100km exceeds MAX_REALISTIC=%.0f "
                    "(dist=%.0f km). Clamping — check input data quality.",
                    consumption_l_100km,
                    self.MAX_REALISTIC_L_100KM,
                    total_dist_km,
                )
                _physics_outlier_counter.inc()
            consumption_l_100km = self.MAX_REALISTIC_L_100KM
            fuel_liters = (consumption_l_100km * total_dist_km) / 100

        # Dynamic Insights
        total_raw = e_rolling_total + e_air_total + e_climb_total
        safe_total = max(1.0, total_raw)
        climb_ratio = e_climb_total / safe_total
        drag_ratio = e_air_total / safe_total

        insight = None
        cl_thr = (
            historical_stats["climb_mean"] + 2 * historical_stats.get("climb_std", 0.1)
            if (historical_stats and "climb_mean" in historical_stats)
            else 0.4
        )
        if climb_ratio > cl_thr:
            diff = int((climb_ratio - cl_thr) * 100)
            insight = f"Dik rampalar tüketimi beklentinin %{diff} üzerinde artırdı"

        dr_thr = (
            historical_stats["drag_mean"] + 2 * historical_stats.get("drag_std", 0.05)
            if (historical_stats and "drag_mean" in historical_stats)
            else 0.6
        )
        if not insight and drag_ratio > dr_thr:
            insight = "Yüksek hız/rüzgar direnci tüketim limitlerini zorladı"

        if not insight and e_descent_total > e_climb_total * 0.8:
            insight = "Sürekli iniş; gravity recovery ile maksimum tasarruf"

        return FuelPrediction(
            total_liters=round(fuel_liters, 2),
            consumption_l_100km=round(consumption_l_100km, 2),
            energy_breakdown={
                "yuvarlanma": round(e_rolling_total / safe_total * 100, 1),
                "hava_direnci": round(e_air_total / safe_total * 100, 1),
                "tirmanis": round(e_climb_total / safe_total * 100, 1),
                "ini_yardimi": round(e_descent_total / safe_total * 100, 1),
            },
            insight=insight,
            confidence_range=(
                round(fuel_liters * 0.92, 1),
                round(fuel_liters * 1.08, 1),
            ),
            factors_used={
                "total_mass_kg": total_mass,
                "distance_km": round(total_dist_km, 2),
                "dynamic_thresholds": historical_stats is not None,
            },
        )

    def predict_segment_tractive(
        self,
        segments: List[Tuple[float, float, float]],
        total_mass_kg: float,
        arac_yasi: int = 5,
        **kwargs,
    ) -> FuelPrediction:
        """Fiziksel-doğru per-segment tractive yakıt.

        Her segment bağımsız: tractive enerji (rolling + air + İŞARETLİ grade),
        sıfır-taban (iniş kredisi route'a yayılmaz), zaman-bazlı parazit base.
        Gravity recovery YOK — dizel TIR'da enerji deposu yok; dik inişte
        propulsion 0'a düşer (fuel-cut), aksesuar tabanı kalır.

        segments: List of (distance_m, velocity_ms, elevation_diff_m).
        """
        from app.config import settings

        lhv_j_per_l = (
            self.vehicle.fuel_energy_mj_kg * self.vehicle.fuel_density_kg_l * 1e6
        )
        eta_prop = settings.PHYSICS_ENGINE_BSFC * settings.PHYSICS_DRIVELINE_EFF
        eta_aux = settings.PHYSICS_ENGINE_BSFC
        p_par_w = settings.PHYSICS_PARASITIC_KW * 1000.0
        grade_cap = settings.PHYSICS_GRADE_CLAMP_PCT / 100.0
        # Efektif Cd·A (m²) — kalibre edilebilir. Eski model Cd×alan'ı yerine
        # tek katsayı (VECTO non-aero TIR 6-8). f_air = ½·ρ·CdA·v².
        cda = settings.PHYSICS_DRAG_CDA_M2
        # Rolling split: tractor sabit + (trailer_empty + load) trailer rr.
        # trailer_rolling_resistance (Faz 7: 0.00738) payload duyarlılığını taşır.
        trailer_and_load = total_mass_kg - self.vehicle.empty_weight_kg
        f_roll = (
            self.vehicle.empty_weight_kg
            * self.GRAVITY
            * self.vehicle.rolling_resistance
            + trailer_and_load * self.GRAVITY * self.vehicle.trailer_rolling_resistance
        )

        fuel_l = 0.0
        total_km = 0.0
        for dist_m, v_ms, delta_h in segments:
            if dist_m <= 0:
                continue
            total_km += dist_m / 1000.0
            grade = max(-grade_cap, min(grade_cap, delta_h / dist_m))
            f_air = 0.5 * self.AIR_DENSITY * cda * (v_ms**2)
            f_grade = total_mass_kg * self.GRAVITY * grade
            f_trac = f_roll + f_air + f_grade
            e_prop = max(0.0, f_trac) * dist_m
            fuel_l += e_prop / (eta_prop * lhv_j_per_l)
            t_s = dist_m / max(v_ms, 1.0)
            fuel_l += (p_par_w * t_s) / (eta_aux * lhv_j_per_l)

        if not np.isfinite(fuel_l):
            fuel_l = 0.0
        cons = (fuel_l / total_km * 100.0) if total_km > 0 else 0.0

        if cons > self.MAX_REALISTIC_L_100KM:
            if not kwargs.get("silent_outlier_log", False):
                logger.warning(
                    "tractive_outlier: %.1f l/100km > MAX_REALISTIC=%.0f (dist=%.0f km)",
                    cons,
                    self.MAX_REALISTIC_L_100KM,
                    total_km,
                )
                _physics_outlier_counter.inc()
            cons = self.MAX_REALISTIC_L_100KM
            fuel_l = cons * total_km / 100.0

        return FuelPrediction(
            total_liters=round(fuel_l, 2),
            consumption_l_100km=round(cons, 2),
            energy_breakdown={},
            confidence_range=(round(fuel_l * 0.92, 1), round(fuel_l * 1.08, 1)),
            factors_used={
                "total_mass_kg": total_mass_kg,
                "distance_km": round(total_km, 2),
                "model": "tractive",
            },
        )

    def calibrate_with_historical(self, predictions: list, actuals: list) -> Dict:
        """Geçmiş verilerle modeli kalibre et."""
        if len(predictions) < 5:
            return {"error": "Minimum 5 veri noktası gerekli"}
        error_ratios = np.array(actuals) / np.maximum(
            np.abs(np.array(predictions)), 1e-6
        )
        return {
            "calibration_factor": round(np.mean(error_ratios), 4),
            "std_deviation": round(np.std(error_ratios), 4),
            "sample_count": len(predictions),
            "recommendation": "Motor verimliliğini güncelle"
            if abs(np.mean(error_ratios) - 1.0) > 0.1
            else "Model kalibre",
        }


class HybridFuelPredictor:
    """Hibrit yaklaşım: Fizik + ML kombinasyonu"""

    def __init__(self, vehicle: VehicleSpecs = None):
        self.physics_model = PhysicsBasedFuelPredictor(vehicle)
        self.correction_factor = 1.0
        self.historical_errors: List[float] = []

    def predict(self, route: RouteConditions) -> FuelPrediction:
        base = self.physics_model.predict(route)
        corrected_liters = base.total_liters * self.correction_factor
        corrected_cons = (
            (corrected_liters / route.distance_km * 100)
            if route.distance_km > 0
            else 0.0
        )
        margin = corrected_liters * 0.08
        return FuelPrediction(
            total_liters=round(corrected_liters, 1),
            consumption_l_100km=round(corrected_cons, 1),
            energy_breakdown=base.energy_breakdown,
            insight=base.insight,
            confidence_range=(
                round(corrected_liters - margin, 1),
                round(corrected_liters + margin, 1),
            ),
            factors_used={
                **base.factors_used,
                "correction_factor": self.correction_factor,
            },
        )

    def learn_from_actual(self, prediction: float, actual: float):
        """Gerçek değerden öğren (Outlier Guard: ±50%)."""
        ratio = actual / max(abs(prediction), 1e-6)
        if 0.5 < ratio < 1.5:
            self.historical_errors.append(ratio)
        if len(self.historical_errors) >= 5:
            if len(self.historical_errors) > 20:
                self.historical_errors = self.historical_errors[-20:]
            self.correction_factor = float(np.mean(self.historical_errors))
