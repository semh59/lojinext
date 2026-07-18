"""
TIR Yakıt Takip - Ensemble Tahmin Modeli (Core)
LightGBM + XGBoost + GradientBoosting + RandomForest + Fizik Modeli

5-Model Ensemble Architecture:
Cold-start DEFAULT_WEIGHTS: physics=0.80, diğerleri her biri=0.05
Eğitim sonrası: DynamicWeightStrategy R²-normalize ile model bazlı ağırlık hesaplar.
Hesaplanan ağırlıklar <model_id>_meta.json içinde 'model_weights' alanına kaydedilir;
sonraki başlatmada meta.json'dan yüklenir → gerçek performans ağırlıkları kullanılır.

This module contains EnsembleFuelPredictor and its dependencies.
EnsemblePredictorService lives in ensemble_service.py.
"""

import hashlib
import threading
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.infrastructure.logging.logger import get_logger
from v2.modules.prediction_ml.domain.ensemble_strategy import (
    DynamicWeightStrategy,
    EnsembleStrategy,
)
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
    RouteConditions,
    VehicleSpecs,
)


class SecurityError(Exception):
    """Güvenlik ihlali durumunda fırlatılan istisna"""

    pass


# Sklearn importları (lazy loading ile)
try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.metrics import r2_score
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# XGBoost import (opsiyonel)
try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    xgb = None
    XGBOOST_AVAILABLE = False

# LightGBM import (opsiyonel)
try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    lgb = None
    LIGHTGBM_AVAILABLE = False


logger = get_logger(__name__)


@dataclass
class PredictionResult:
    """Tahmin sonucu"""

    tahmin_l_100km: float
    physics_only: float
    ml_correction: float
    confidence_low: float
    confidence_high: float
    physics_weight: float
    features_used: Dict[str, float]


class EnsembleFuelPredictor:
    """
    Hibrit Ensemble Model (5 Model Kombinasyonu):
    1. Fizik bazlı base tahmin (%10)
    2. LightGBM - Kategorik feature handling (%15)
    3. XGBoost - Dominant gradient boosting (%55)
    4. GradientBoosting - Sklearn baseline (%10)
    5. RandomForest - Variance reduction (%10)

    Feature'lar (24 adet):
    Phase 2G (16): ton, ascent_m, descent_m, net_elevation,
      yuk_yogunlugu, zorluk, arac_yasi, yas_faktoru,
      mevsim_faktor, sofor_katsayisi,
      motorway_ratio, trunk_ratio, primary_ratio,
      residential_ratio, unclassified_ratio, flat_km
    Phase 5A TIR Physics (8): grade_gentle_ratio, grade_moderate_ratio,
      grade_steep_ratio, weight_x_gradient, stopgo_proxy,
      aero_speed_factor, engine_load_proxy, route_fatigue
    """

    FEATURE_NAMES = [
        "ton",
        "ascent_m",
        "descent_m",
        "net_elevation",
        "yuk_yogunlugu",
        "zorluk",
        "arac_yasi",
        "yas_faktoru",
        "mevsim_faktor",
        "sofor_katsayi",
        # Route Analysis Features (Phase 2G)
        "motorway_ratio",
        "trunk_ratio",
        "primary_ratio",
        "residential_ratio",
        "unclassified_ratio",
        "flat_km",
        # TIR Physics Features (Phase 5A - Refined)
        "grade_gentle_ratio",  # 0–2.5%
        "grade_moderate_ratio",  # 2.5–5.5%
        "grade_steep_ratio",  # 5.5%+
        "weight_x_gradient",  # ton × (ascent / (mesafe + 1))
        "stopgo_proxy",  # residential_ratio × sqrt(mesafe)
        "aero_speed_factor",  # motorway_ratio × Cd proxy
        "engine_load_proxy",  # (1 - flat_ratio)^1.3 × load_ratio
        "route_fatigue",  # proxy via duration
        "dorse_bos_agirlik",
        "dorse_lastik_sayisi",
        # Speed Profile Features (Phase 6A)
        "expected_avg_speed",  # weighted avg expected speed km/h
        "urban_speed_ratio",  # residential km / mesafe (stop-go proxy)
        "highway_speed_ratio",  # motorway + trunk ratio combined
    ]

    # Cold-start default: eğitim verisi olmadan fizik modeli en güvenilir kaynak.
    # Eğitim tamamlanınca DynamicWeightStrategy bu değerlerin üzerine yazar.
    DEFAULT_WEIGHTS = {
        "physics": 0.80,
        "lightgbm": 0.05,
        "xgboost": 0.05,
        "gb": 0.05,
        "rf": 0.05,
    }

    def __init__(
        self, vehicle_specs: VehicleSpecs = None, strategy: EnsembleStrategy = None
    ):
        import hashlib

        self._feature_hash = hashlib.sha256(
            "".join(self.FEATURE_NAMES).encode()
        ).hexdigest()[:16]
        # Set by load_model() from persisted metadata; None until a model is
        # actually loaded from disk (fresh/never-loaded predictor).
        self._loaded_feature_schema_hash: Optional[str] = None
        self._physics_version = "v5.2-hybrid"
        self.physics_model = PhysicsBasedFuelPredictor(vehicle_specs)
        self.weights = self.DEFAULT_WEIGHTS.copy()  # Instance-specific weights
        self.strategy = strategy if strategy is not None else DynamicWeightStrategy()

        # GradientBoosting
        if SKLEARN_AVAILABLE:
            self.gb_model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
            )

            self.rf_model = RandomForestRegressor(
                n_estimators=50, max_depth=6, random_state=42
            )

            self.scaler = StandardScaler()
        else:
            self.gb_model = None
            self.rf_model = None
            self.scaler = None
            logger.warning("sklearn not available, using physics-only model")

        # XGBoost
        if XGBOOST_AVAILABLE:
            self.xgb_model = xgb.XGBRegressor(
                n_estimators=50,  # Reduced from 200
                max_depth=2,  # Shallow depth to prevent overfitting
                learning_rate=0.05,  # Slower learning
                min_child_weight=2,  # Regularization
                subsample=0.7,
                colsample_bytree=0.7,
                objective="reg:squarederror",
                random_state=42,
                verbosity=0,
            )
            logger.info("XGBoost model initialized")
        else:
            self.xgb_model = None
            logger.warning("XGBoost not available, excluding from ensemble")

        # LightGBM
        if LIGHTGBM_AVAILABLE:
            self.lgb_model = lgb.LGBMRegressor(
                n_estimators=150,
                num_leaves=31,
                learning_rate=0.05,
                feature_fraction=0.8,
                bagging_fraction=0.8,
                bagging_freq=5,
                verbose=-1,
                random_state=42,
            )
            logger.info("LightGBM model initialized")
        else:
            self.lgb_model = None
            logger.warning("LightGBM not available, excluding from ensemble")

        self.is_trained = False
        self.physics_weight = self.weights.get("physics", 0.2)
        self.training_stats: Dict[str, Any] = {}
        self._feature_shape_warned = False
        self._model_lock = (
            threading.Lock()
        )  # Tahmin ve eğitim arasında senkronizasyon için

    @property
    def WEIGHTS(self) -> Dict[str, float]:
        """Legacy compatibility alias."""
        return self.weights

    def prepare_features(self, seferler: List[Dict]) -> np.ndarray:
        """
        Feature engineering — Tüm faktörleri çıkar.
        Phase 2G: Route analysis features (16)
        Phase 5A: TIR physics features (8) — Total: 24
        """
        import math

        features = []

        zorluk_map = {"Kolay": 1, "Normal": 2, "Zor": 3, "Çok Zor": 4}

        for s in seferler:
            # ── Base Features ──
            mesafe = float(s.get("mesafe_km", 0) or 0)
            ton = float(s.get("ton", 0) or 0)
            ascent = float(s.get("ascent_m", 0) or 0)
            descent = float(s.get("descent_m", 0) or 0)
            flat_km = float(s.get("flat_distance_km", 0) or 0)

            # Derived
            net_elevation = ascent - descent
            yuk_yogunlugu = ton / mesafe if mesafe > 0 else 0
            zorluk = zorluk_map.get(s.get("zorluk", "Normal"), 2)

            # Vehicle age
            arac_yasi = float(s.get("arac_yasi", 5) or 5)
            yas_faktoru = float(s.get("yas_faktoru", 1.0) or 1.0)

            # Season & driver
            mevsim_faktor = float(s.get("mevsim_faktor", 1.0) or 1.0)
            sofor_katsayi = float(s.get("sofor_katsayi", 1.0) or 1.0)

            # Dorse Features (Phase 4)
            dorse_bos_agirlik = float(s.get("dorse_bos_agirlik", 6500.0) or 6500.0)
            dorse_lastik_sayisi = float(s.get("dorse_lastik_sayisi", 6) or 6)

            # ── Route Analysis (Phase 2G) ──
            motorway_ratio = 0.0
            trunk_ratio = 0.0
            primary_ratio = 0.0
            residential_ratio = 0.0
            unclassified_ratio = 0.0

            rota_detay = s.get("rota_detay") or {}
            # Support both nested and flat format
            analysis = rota_detay.get("route_analysis") or rota_detay

            # Grade distribution defaults (Phase 5A)
            grade_gentle_ratio = 1.0  # Default: assume all gentle if no data
            grade_moderate_ratio = 0.0
            grade_steep_ratio = 0.0

            if analysis and mesafe > 0:

                def sum_km(cat_dict):
                    """Sum flat+up+down for a road category."""
                    if not cat_dict or not isinstance(cat_dict, dict):
                        return 0.0
                    return (
                        float(cat_dict.get("flat", 0))
                        + float(cat_dict.get("up", 0))
                        + float(cat_dict.get("down", 0))
                    )

                motorway_km = sum_km(analysis.get("motorway"))
                trunk_km = sum_km(analysis.get("trunk"))
                primary_km = sum_km(analysis.get("primary"))
                residential_km = sum_km(analysis.get("residential"))
                unclassified_km = sum_km(analysis.get("unclassified"))

                motorway_ratio = min(1.0, motorway_km / mesafe)
                trunk_ratio = min(1.0, trunk_km / mesafe)
                primary_ratio = min(1.0, primary_km / mesafe)
                residential_ratio = min(1.0, residential_km / mesafe)
                unclassified_ratio = min(1.0, unclassified_km / mesafe)

                # ── Grade Histogram (Phase 5A Refined) ──
                # gentle (0-2.5%), moderate (2.5-5.5%), steep (5.5%+)
                total_up_down = 0.0
                gentle_km = 0.0
                moderate_km = 0.0
                steep_km = 0.0

                for cat_name in [
                    "motorway",
                    "trunk",
                    "primary",
                    "residential",
                    "unclassified",
                    "other",
                ]:
                    cat = analysis.get(cat_name)
                    if not cat or not isinstance(cat, dict):
                        continue
                    up_km = float(cat.get("up", 0))
                    down_km = float(cat.get("down", 0))
                    cat_updown = up_km + down_km
                    total_up_down += cat_updown

                    if cat_name in ("motorway", "trunk"):
                        gentle_km += cat_updown
                    elif cat_name == "primary":
                        # Primary roads: ~70% moderate, ~30% gentle
                        moderate_km += cat_updown * 0.7
                        gentle_km += cat_updown * 0.3
                    else:
                        # Residential/Rural: ~50% steep, ~30% moderate, ~20% gentle
                        steep_km += cat_updown * 0.5
                        moderate_km += cat_updown * 0.3
                        gentle_km += cat_updown * 0.2

                total_graded = flat_km + total_up_down
                if total_graded > 0:
                    grade_gentle_ratio = min(1.0, (flat_km + gentle_km) / total_graded)
                    grade_moderate_ratio = min(1.0, moderate_km / total_graded)
                    grade_steep_ratio = min(1.0, steep_km / total_graded)

            # ── Speed Profile Features (Phase 6A) ──
            speed_map_reference = {
                "motorway": 85.0,
                "trunk": 75.0,
                "primary": 65.0,
                "secondary": 55.0,
                "residential": 40.0,
                "other": 50.0,
            }
            if analysis and mesafe > 0:
                weighted_speed = 0.0
                total_weighted = 0.0
                for road_cls, spd in speed_map_reference.items():
                    road_km = sum(
                        float((analysis.get(road_cls) or {}).get(k, 0) or 0)
                        for k in ("flat", "up", "down")
                    )
                    weighted_speed += spd * road_km
                    total_weighted += road_km
                expected_avg_speed = weighted_speed / max(total_weighted, 1.0)
                urban_speed_ratio = (
                    sum(
                        float((analysis.get("residential") or {}).get(k, 0) or 0)
                        for k in ("flat", "up", "down")
                    )
                    / mesafe
                )
                highway_speed_ratio = min(1.0, motorway_ratio + trunk_ratio)
            else:
                expected_avg_speed = 0.0
                urban_speed_ratio = 0.0
                highway_speed_ratio = 0.0

            # ── TIR Interaction Refinements (Phase 5A) ──

            # 1. Weight × Gradient: "ağır yük + rampa" (Stabilized)
            weight_x_gradient = ton * (ascent / (mesafe + 1.0))

            # 2. Stop-go proxy: Non-linear (Power law)
            # residential_ratio × sqrt(mesafe) — captures acceleration cycle intensity
            stopgo_proxy = residential_ratio * math.sqrt(mesafe)

            # 3. Aerodynamic speed factor: Cd proxy
            aero_speed_factor = motorway_ratio * (1.0 + trunk_ratio * 0.3)

            # 4. Engine load proxy: Exponential stress
            # (1 - flat_ratio)^1.3 × load_ratio
            non_flat_ratio = 1.0 - (flat_km / mesafe) if mesafe > 0 else 0
            load_ratio = ton / 26.0
            engine_load_proxy = (non_flat_ratio**1.3) * load_ratio

            # 5. Route Fatigue: duration proxy (Phase 5A Extra)
            duration_min = float(s.get("duration_min") or (mesafe / 70 * 60) or 0)
            route_fatigue = min(
                1.0, duration_min / 600.0
            )  # fatigue caps at 600 mins (10h)

            features.append(
                [
                    ton,
                    ascent,
                    descent,
                    net_elevation,
                    yuk_yogunlugu,
                    zorluk,
                    arac_yasi,
                    yas_faktoru,
                    mevsim_faktor,
                    sofor_katsayi,
                    motorway_ratio,
                    trunk_ratio,
                    primary_ratio,
                    residential_ratio,
                    unclassified_ratio,
                    flat_km,
                    grade_gentle_ratio,
                    grade_moderate_ratio,
                    grade_steep_ratio,
                    weight_x_gradient,
                    stopgo_proxy,
                    aero_speed_factor,
                    engine_load_proxy,
                    route_fatigue,
                    dorse_bos_agirlik,
                    dorse_lastik_sayisi,
                    expected_avg_speed,
                    urban_speed_ratio,
                    highway_speed_ratio,
                ]
            )

        return np.array(features)

    def _resolve_expected_feature_count(self) -> Optional[int]:
        """Infer expected feature count from fitted models/scaler metadata.

        Only returns a value when the attribute is a genuine numeric type
        (int, float, np.integer, etc.).  MagicMock objects implement __int__
        and would otherwise pass the int() guard — we reject them explicitly.
        """
        candidates = [
            getattr(self.scaler, "n_features_in_", None),
            getattr(self.gb_model, "n_features_in_", None),
            getattr(self.rf_model, "n_features_in_", None),
            getattr(self.xgb_model, "n_features_in_", None),
            getattr(self.lgb_model, "n_features_in_", None),
        ]
        for value in candidates:
            if value is None:
                continue
            # Only trust real numeric types — reject MagicMock and similar
            if not isinstance(value, (int, float, np.integer, np.floating)):
                continue
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return None

    @staticmethod
    def _extract_route_analysis(sefer: Dict) -> Optional[Dict]:
        rota_detay = sefer.get("rota_detay")
        if not isinstance(rota_detay, dict):
            return None
        route_analysis = rota_detay.get("route_analysis") or rota_detay
        return route_analysis if isinstance(route_analysis, dict) else None

    def _align_feature_matrix(self, X: np.ndarray) -> np.ndarray:
        """Backward-compatible feature shaping for persisted models."""
        expected = self._resolve_expected_feature_count()
        if expected is None:
            return X

        current = X.shape[1]
        if current == expected:
            return X

        if current > expected:
            # Runtime schema has MORE features than the persisted model was
            # trained on.  Silently truncating would cause silent prediction
            # corruption — raise so the caller falls back to physics-only
            # and the model is marked for retraining.
            self.is_trained = False
            raise RuntimeError(
                f"Feature schema mismatch: runtime has {current} features, "
                f"model was trained with {expected} features. "
                "Retrain the model to use the updated feature set."
            )

        # current < expected: runtime is missing columns the model requires.
        # Cannot fabricate missing features — raise so the caller can fall back.
        raise RuntimeError(f"Feature schema mismatch: {current} vs {expected}")

    def _get_physics_predictions(self, seferler: List[Dict]) -> np.ndarray:
        """Fizik modeli tahminleri"""
        predictions = []

        for s in seferler:
            route = RouteConditions(
                distance_km=float(s.get("mesafe_km", 0) or 0),
                load_ton=float(s.get("ton", 0) or 0),
                is_empty_trip=bool(s.get("is_empty_trip", False)),
                ascent_m=float(s.get("ascent_m", 0) or 0),
                descent_m=float(s.get("descent_m", 0) or 0),
                flat_distance_km=float(s.get("flat_distance_km", 0) or 0),
                route_analysis=self._extract_route_analysis(s),
            )
            # Apply dynamic specs to model if available in sefer dict
            if "dorse_bos_agirlik" in s:
                self.physics_model.vehicle.trailer_empty_weight_kg = s[
                    "dorse_bos_agirlik"
                ]
            if "dorse_lastik_direnci" in s:
                self.physics_model.vehicle.trailer_rolling_resistance = s[
                    "dorse_lastik_direnci"
                ]
            if "dorse_hava_direnci" in s:
                self.physics_model.vehicle.trailer_drag_contribution = s[
                    "dorse_hava_direnci"
                ]

            pred = self.physics_model.predict(route)
            predictions.append(pred.consumption_l_100km)

        return np.array(predictions)

    def fit(self, seferler: List[Dict], y_actual: Optional[np.ndarray] = None) -> Dict:
        """
        Model eğitimi

        1. Feature'ları hazırla
        2. Fizik tahminleri al
        3. Residual (hata) hesapla
        4. ML ile residual öğren
        5. Ağırlıkları belirle

        y_actual: gerçek tüketim değerleri (L/100km). None ise seferler içindeki
        'tuketim' alanından çıkarılır.
        """
        if y_actual is None:
            y_actual = np.array([float(s.get("tuketim") or 0.0) for s in seferler])
        if len(seferler) < 10:
            return {
                "success": False,
                "error": f"Yetersiz veri: {len(seferler)} sefer. En az 10 gerekli.",
            }

        if not SKLEARN_AVAILABLE:
            return {"success": False, "error": "sklearn kütüphanesi yüklü değil."}

        try:
            # LOCK SCOPE FIX: Tüm eğitim lock içinde - is_trained flag atomik güncellemesi
            with self._model_lock:
                self.is_trained = False  # Eğitim sırasında eski tahminleri engelle

                # ML Outlier Guard (Z-score > 3.0)
                if len(y_actual) > 20:
                    y_mean = np.mean(y_actual)
                    y_std = np.std(y_actual)
                    if y_std > 0:
                        z_scores = np.abs((y_actual - y_mean) / y_std)
                        mask = z_scores < 3.0
                        removed = int(len(y_actual) - np.sum(mask))
                        if removed > 0:
                            logger.info(
                                f"ML Outlier Guard: {removed} samples removed from training."
                            )
                            y_actual = y_actual[mask]
                            seferler = [s for i, s in enumerate(seferler) if mask[i]]

                # Temporal Weighting — eski veri düşük ağırlık, yeni veri yüksek
                from datetime import date as dt_date

                bugun = dt_date.today()
                # list while building, then rebound to an ndarray below; keep
                # the binding Any so the np.array reassignment and the
                # .min()/.max()/.mean() + fancy-indexing downstream type-check.
                sample_weights: Any = []
                for s in seferler:
                    tarih_str = s.get("tarih")
                    if tarih_str:
                        try:
                            if isinstance(tarih_str, str):
                                tarih = dt_date.fromisoformat(tarih_str)
                            elif isinstance(tarih_str, dt_date):
                                tarih = tarih_str
                            else:
                                tarih = bugun
                            ay_farki = max(0, (bugun - tarih).days / 30.0)
                            # Alpha: 0.1 (Phase 7 Request - Give 2025 much more weight than 2022)
                            weight = np.exp(-0.1 * ay_farki)
                        except (ValueError, TypeError):
                            weight = 0.5
                    else:
                        weight = 0.5

                    # NaN Guard for weight
                    if not np.isfinite(weight):
                        weight = 0.1

                    sample_weights.append(max(0.1, weight))  # Minimum %10 ağırlık
                sample_weights = np.array(sample_weights)
                logger.info(
                    f"Temporal Weighting: min={sample_weights.min():.2f}, "
                    f"max={sample_weights.max():.2f}, mean={sample_weights.mean():.2f}"
                )

                # Feature hazırla
                X = self.prepare_features(seferler)
                X_scaled = self.scaler.fit_transform(X)

                # Fizik tahminleri (Baseline L/100km)
                y_physics_raw = self._get_physics_predictions(seferler)

                # Age and seasonal effects stay in feature space; baseline stays raw.
                y_physics = np.array(y_physics_raw)

                # Database'den gelen 'tuketim' zaten L/100km formatında (Kritik Keşif)
                # Fix: 'tuketim' doğrudan kullanılıyor (Double Division bug engellendi)
                # Label-leak fix: val <= 0 ise satırı ATLA, fizik tahmini etiket olarak kullanma.
                valid_mask = np.array(
                    [float(y_actual[i] or 0.0) > 0 for i in range(len(seferler))]
                )
                if valid_mask.sum() < 10:
                    return {
                        "success": False,
                        "error": f"Geçerli tuketim değeri olan sefer sayısı yetersiz: {int(valid_mask.sum())} (min 10)",
                    }
                if valid_mask.sum() < len(seferler):
                    dropped = int(len(seferler) - valid_mask.sum())
                    logger.info(
                        "Label-leak guard: %d sefer tuketim=0/None olduğu için eğitimden çıkarıldı",
                        dropped,
                    )
                    seferler = [s for s, ok in zip(seferler, valid_mask) if ok]
                    y_actual = y_actual[valid_mask]
                    y_physics = y_physics[valid_mask]
                    sample_weights = sample_weights[valid_mask]

                y_norm = np.array([float(v) for v in y_actual])

                # Residual = Gerçek (L/100km) - Factored Physics (L/100km)
                residuals = y_norm - y_physics

                # Debug Logging
                if len(residuals) > 0:
                    logger.info(
                        f"ML FIT DEBUG [Vehicle]: y_norm mean={np.mean(y_norm):.2f}, y_phys mean={np.mean(y_physics):.2f}, resid mean={np.mean(residuals):.2f}"  # noqa: E501
                    )
                    logger.info(
                        f"ML FIT DEBUG [Vehicle]: y_norm range=[{np.min(y_norm):.2f}, {np.max(y_norm):.2f}], residuals std={np.std(residuals):.2f}"  # noqa: E501
                    )

                # Temporal sort: en eski veri önce — train/test sızıntısını önle
                # Veriyi tarihe göre sırala (sefer dict'indeki 'tarih' alanı kullanılır)
                from datetime import date as _dt_date

                def _parse_tarih(s):
                    t = s.get("tarih")
                    if isinstance(t, _dt_date):
                        return t
                    try:
                        return _dt_date.fromisoformat(str(t))
                    except Exception:
                        return _dt_date(2000, 1, 1)

                sort_indices = sorted(
                    range(len(seferler)), key=lambda i: _parse_tarih(seferler[i])
                )
                seferler = [seferler[i] for i in sort_indices]
                residuals = residuals[sort_indices]
                sample_weights = sample_weights[sort_indices]
                y_physics = y_physics[sort_indices]
                y_norm = y_norm[sort_indices]
                X = self.prepare_features(seferler)
                X_scaled = self.scaler.fit_transform(X)

                # Phase 3: Train/Test Split (Overfitting Guard)
                # 15+ örnek varsa dürüstlük için ayır, yoksa CV ile devam et
                use_split = len(residuals) >= 15
                if use_split:
                    # Temporal split — son %20'si test, öncesi train (sıralı olduğu garanti)
                    split_idx = int(len(residuals) * 0.8)
                    X_train, X_test = X_scaled[:split_idx], X_scaled[split_idx:]
                    y_train, y_test = residuals[:split_idx], residuals[split_idx:]
                    sw_train = sample_weights[:split_idx]
                    logger.info(
                        "Temporal split: train=%d (oldest→%.0f%%), test=%d (newest)",
                        split_idx,
                        80,
                        len(residuals) - split_idx,
                    )
                else:
                    X_train, y_train = X_scaled, residuals
                    X_test, y_test = X_scaled, residuals
                    sw_train = (
                        sample_weights if len(sample_weights) == len(X_train) else None
                    )

                # ML modelleri eğit (Training set üzerinde - Temporal Weighted)
                self.gb_model.fit(X_train, y_train, sample_weight=sw_train)
                self.rf_model.fit(X_train, y_train, sample_weight=sw_train)

                # Feature Importance (Explainability)
                # FEATURE_NAMES ile senkron (17 isim) — BUG-1 FIX
                importances = self.rf_model.feature_importances_
                feat_imp = {
                    name: round(float(imp), 4)
                    for name, imp in zip(self.FEATURE_NAMES, importances)
                }

                # XGBoost eğitimi
                xgb_r2 = 0.0
                if self.xgb_model is not None:
                    try:
                        self.xgb_model.fit(X_train, y_train, sample_weight=sw_train)
                        xgb_test_pred = self.xgb_model.predict(X_test)
                        xgb_r2 = (
                            r2_score(y_test, xgb_test_pred) if len(y_test) > 0 else 0
                        )
                    except Exception as exc:
                        logger.warning("XGBoost fit failed, skipping model: %s", exc)
                        xgb_r2 = 0.0

                # LightGBM eğitimi
                lgb_r2 = 0.0
                if LIGHTGBM_AVAILABLE and self.lgb_model is not None:
                    try:
                        self.lgb_model.fit(X_train, y_train, sample_weight=sw_train)
                        lgb_test_pred = self.lgb_model.predict(X_test)
                        lgb_r2 = (
                            r2_score(y_test, lgb_test_pred) if len(y_test) > 0 else 0
                        )
                    except MemoryError as exc:
                        logger.warning("LightGBM fit OOM, skipping model: %s", exc)
                        lgb_r2 = 0.0
                    except Exception as exc:
                        logger.warning("LightGBM fit failed, skipping model: %s", exc)
                        lgb_r2 = 0.0

                # Dürüst Test Skorları (GB & RF)
                gb_test_r2 = (
                    r2_score(y_test, self.gb_model.predict(X_test))
                    if len(y_test) > 0
                    else 0
                )
                rf_test_r2 = (
                    r2_score(y_test, self.rf_model.predict(X_test))
                    if len(y_test) > 0
                    else 0
                )

                # Cross-validation skorları (Training set üzerinde dürüstlük için)
                cv_folds = min(5, max(2, len(X_train) // 2))
                gb_cv_mean = 0.0
                if cv_folds >= 2:
                    gb_cv_scores = cross_val_score(
                        self.gb_model, X_train, y_train, cv=cv_folds, scoring="r2"
                    )
                    gb_cv_mean = np.mean(gb_cv_scores)

                # ---------------------------------------------------------
                # STRATEGY BASED WEIGHTING (Faz 2)
                # ---------------------------------------------------------
                # 1. Pozitif R2 skoru olan modelleri belirle
                metrics_for_strategy = {
                    "gb": {"r2": max(0, gb_test_r2)},
                    "rf": {"r2": max(0, rf_test_r2)},
                    "xgboost": {"r2": max(0, xgb_r2) if xgb_r2 else 0},
                    "lightgbm": {"r2": max(0, lgb_r2) if lgb_r2 else 0},
                }
                avail_models = ["gb", "rf", "xgboost", "lightgbm"]

                ml_weights = self.strategy.calculate_weights(
                    metrics_for_strategy, avail_models
                )

                base_physics_weight = 0.10
                ml_total_r2 = sum(m["r2"] for m in metrics_for_strategy.values())

                new_weights = {}
                if ml_total_r2 > 0:
                    # ML modelleri başarılı, kalan payı stratejinin döndüğü oranlarla dağıt
                    ml_share = 1.0 - base_physics_weight
                    new_weights["physics"] = base_physics_weight

                    for model in avail_models:
                        weight = ml_weights.get(model, 0.0) * ml_share
                        new_weights[model] = round(weight, 3)
                else:
                    # Hiçbir ML modeli başarılı değil -> Fallback to Physics
                    logger.warning(
                        "Dynamic Weighting: All ML models failed (R2<=0). Fallback to Physics."
                    )
                    new_weights = {
                        "physics": 1.0,
                        "gb": 0,
                        "rf": 0,
                        "xgboost": 0,
                        "lightgbm": 0,
                    }

                # Ağırlıkları normalize et (toplam = 1.0)
                total_w = sum(new_weights.values())
                if total_w > 0:
                    self.weights = {k: v / total_w for k, v in new_weights.items()}
                else:
                    self.weights = self.DEFAULT_WEIGHTS.copy()

                self.physics_weight = self.weights.get("physics", 1.0)

                # ---------------------------------------------------------
                # EXTENDED METRICS (Faz 2)
                # ---------------------------------------------------------
                # Test seti üzerinde Ensemble performansını ölç
                final_preds = []
                for i in range(len(X_test)):
                    # Get factored physics baseline for this test sample
                    p_physics = (
                        y_physics[len(y_train) + i] if use_split else y_physics[i]
                    )

                    weighted_res = 0.0
                    # GB
                    if self.weights.get("gb", 0) > 0:
                        weighted_res += (
                            self.weights["gb"] * self.gb_model.predict([X_test[i]])[0]
                        )
                    # RF
                    if self.weights.get("rf", 0) > 0:
                        weighted_res += (
                            self.weights["rf"] * self.rf_model.predict([X_test[i]])[0]
                        )
                    # XGB
                    if self.weights.get("xgboost", 0) > 0 and self.xgb_model:
                        weighted_res += (
                            self.weights["xgboost"]
                            * self.xgb_model.predict([X_test[i]])[0]
                        )
                    # LGBM
                    if self.weights.get("lightgbm", 0) > 0 and self.lgb_model:
                        weighted_res += (
                            self.weights["lightgbm"]
                            * self.lgb_model.predict([X_test[i]])[0]
                        )

                    final_preds.append(p_physics + weighted_res)

                final_preds = np.array(final_preds)  # type: ignore[assignment]

                # Metrik hesapla (Test seti: y_test = actual_residuals)
                # y_test = y_actual - y_physics
                # Bizim final_pred - p_physics = weighted_residual_sum
                # Hata = (p_physics + weighted_residual_sum) - (p_physics + y_test)
                #      = weighted_residual_sum - y_test

                y_true = y_physics[-len(y_test) :] + y_test
                errors = final_preds - y_true
                mae = np.mean(np.abs(errors))
                rmse = np.sqrt(np.mean(errors**2))

                # Ensemble R2 Score calculation
                ens_r2 = 0.0
                if SKLEARN_AVAILABLE:
                    try:
                        from sklearn.metrics import r2_score as r2_metrics_func

                        ens_r2 = r2_metrics_func(y_true, final_preds)
                    except Exception as e:
                        logger.warning(f"Could not calculate ensemble R2: {e}")

                mape = np.mean(np.abs(errors / np.maximum(np.abs(y_true), 1e-6))) * 100

                physics_mae = np.mean(np.abs(y_test))

                self.training_stats = {
                    "sample_count": len(seferler),
                    "test_size": len(y_test) if use_split else 0,
                    "ensemble_r2": round(float(ens_r2), 4),
                    "measurements": {
                        "mae": round(mae, 2),
                        "rmse": round(rmse, 2),
                        "mape": round(mape, 2),
                        "physics_mae": round(physics_mae, 2),
                    },
                    "metrics": {
                        "gb_test_r2": round(gb_test_r2, 3),
                        "rf_test_r2": round(rf_test_r2, 3),
                        "xgb_test_r2": round(float(xgb_r2), 3) if xgb_r2 else None,
                        "lgb_test_r2": round(float(lgb_r2), 3) if lgb_r2 else None,
                        "gb_cv_mean": round(float(gb_cv_mean), 3),
                    },
                    "feature_importance": feat_imp,
                    "model_weights": self.weights,
                    "is_honest_test": use_split,
                }

                # is_trained bayrağı lock içinde - RACE CONDITION FIX
                self.is_trained = True

            return {"success": True, **self.training_stats}

        except Exception as e:
            logger.error(f"Ensemble training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def predict(self, sefer: Dict) -> PredictionResult:
        """
        Tek sefer için tahmin.

        INPUT VALIDATION: Eksik veya hatalı veri kontrolü.
        """
        # INPUT VALIDATION: Zorunlu alan kontrolü
        mesafe = sefer.get("mesafe_km")
        if mesafe is None or (isinstance(mesafe, (int, float)) and mesafe <= 0):
            logger.warning(
                f"Geçersiz mesafe değeri: {mesafe}, varsayılan 100 kullanılıyor"
            )
            sefer = {**sefer, "mesafe_km": 100}

        # Physics prediction (always works)
        route = RouteConditions(
            distance_km=float(sefer.get("mesafe_km", 0) or 0),
            load_ton=float(sefer.get("ton", 0) or 0),
            is_empty_trip=bool(sefer.get("is_empty_trip", False)),  # Faz 3
            ascent_m=float(sefer.get("ascent_m", 0) or 0),
            descent_m=float(sefer.get("descent_m", 0) or 0),
            flat_distance_km=float(sefer.get("flat_distance_km", 0) or 0),
            route_analysis=self._extract_route_analysis(sefer),
        )

        # Apply dynamic trailer specs to model if available in sefer dict
        if "dorse_bos_agirlik" in sefer:
            self.physics_model.vehicle.trailer_empty_weight_kg = float(
                sefer["dorse_bos_agirlik"] or 6500.0
            )
        if "dorse_lastik_direnci" in sefer:
            self.physics_model.vehicle.trailer_rolling_resistance = float(
                sefer["dorse_lastik_direnci"] or 0.006
            )
        if "dorse_hava_direnci" in sefer:
            self.physics_model.vehicle.trailer_drag_contribution = float(
                sefer["dorse_hava_direnci"] or 0.13
            )

        physics_pred = self.physics_model.predict(route)
        physics_raw = physics_pred.consumption_l_100km

        # Araç yaşı ve mevsim faktörünü uygula (Baseline)
        yas_faktoru = float(sefer.get("yas_faktoru", 1.0) or 1.0)
        mevsim_faktor = float(sefer.get("mevsim_faktor", 1.0) or 1.0)
        physics_baseline = physics_raw
        physics_fallback = physics_raw * yas_faktoru * mevsim_faktor

        try:
            # Tahmin sırasında scaler ve modellerin değişmediğinden emin ol.
            with self._model_lock:
                if not self.is_trained or not SKLEARN_AVAILABLE:
                    try:
                        from app.infrastructure.monitoring.ml_probe import get_ml_probe

                        get_ml_probe().record_prediction(
                            model_id=str(getattr(self, "_model_id", "ensemble")),
                            used_fallback=True,
                        )
                    except Exception:
                        pass
                    return PredictionResult(
                        tahmin_l_100km=round(physics_fallback, 1),
                        physics_only=round(physics_fallback, 1),
                        ml_correction=0.0,
                        confidence_low=round(physics_fallback * 0.9, 1),
                        confidence_high=round(physics_fallback * 1.1, 1),
                        physics_weight=1.0,
                        features_used=sefer,
                    )

                X = self.prepare_features([sefer])
                X = self._align_feature_matrix(X)
                X_scaled = self.scaler.transform(X)

                gb_residual = self.gb_model.predict(X_scaled)[0]
                rf_residual = self.rf_model.predict(X_scaled)[0]
                xgb_residual = (
                    self.xgb_model.predict(X_scaled)[0] if self.xgb_model else 0.0
                )
                lgb_residual = (
                    self.lgb_model.predict(X_scaled)[0]
                    if (LIGHTGBM_AVAILABLE and self.lgb_model)
                    else 0.0
                )

                model_predictions = {
                    "physics": physics_baseline,
                    "gb": physics_baseline + gb_residual,
                    "rf": physics_baseline + rf_residual,
                }

                if self.xgb_model:
                    model_predictions["xgboost"] = physics_baseline + xgb_residual
                if self.lgb_model:
                    model_predictions["lightgbm"] = physics_baseline + lgb_residual

                active_model_keys = list(model_predictions.keys())
                total_weight = sum(self.weights.get(m, 0) for m in active_model_keys)
                safe_total_w = total_weight if total_weight > 0 else 1.0

                final = sum(
                    (self.weights.get(m, 0) / safe_total_w) * model_predictions[m]
                    for m in active_model_keys
                )
                ml_correction = final - physics_baseline

                if np.isnan(final) or np.isinf(final):
                    logger.warning(
                        f"NaN/Inf tahmin tespit edildi, physics-only fallback uygulanıyor | "
                        f"final={final}, physics={physics_baseline}, "
                        f"gb_res={gb_residual}, rf_res={rf_residual}, "
                        f"xgb_res={xgb_residual}, lgb_res={lgb_residual}"
                    )
                    try:
                        from app.infrastructure.monitoring.ml_probe import get_ml_probe

                        get_ml_probe().record_prediction(
                            model_id=str(getattr(self, "_model_id", "ensemble")),
                            used_fallback=True,
                        )
                    except Exception:
                        pass
                    return PredictionResult(
                        tahmin_l_100km=round(physics_fallback, 1),
                        physics_only=round(physics_fallback, 1),
                        ml_correction=0.0,
                        confidence_low=round(physics_fallback * 0.85, 1),
                        confidence_high=round(physics_fallback * 1.15, 1),
                        physics_weight=1.0,
                        features_used=sefer,
                    )

                all_preds = np.array(list(model_predictions.values()))
                # Honest 95% CI: 1.96 × inter-model std (ensemble disagreement proxy).
                # When std == 0 all models agree perfectly → interval collapses to 0.
                # A fixed percentage fallback would produce artificially wide intervals
                # even when models are in complete agreement — that is the old broken
                # behaviour this line intentionally avoids.
                inter_model_std = np.std(all_preds)
                uncertainty = 1.96 * inter_model_std

                try:
                    from app.infrastructure.monitoring.ml_probe import get_ml_probe

                    get_ml_probe().record_prediction(
                        model_id=str(getattr(self, "_model_id", "ensemble")),
                        used_fallback=False,
                    )
                except Exception:
                    pass

                return PredictionResult(
                    tahmin_l_100km=round(final, 1),
                    physics_only=round(physics_baseline, 1),
                    ml_correction=round(ml_correction, 2),
                    confidence_low=round(max(0.0, final - uncertainty), 1),
                    confidence_high=round(final + uncertainty, 1),
                    physics_weight=self.weights.get("physics", 0.2),
                    features_used={
                        **sefer,
                        "yas_faktoru": yas_faktoru,
                        "mevsim_faktor": mevsim_faktor,
                    },
                )
        except RuntimeError as exc:
            logger.error("Feature schema mismatch during predict: %s", exc)
            # Invalidate model so next call skips ML path until retrained.
            self.is_trained = False
            return PredictionResult(
                tahmin_l_100km=round(physics_fallback, 1),
                physics_only=round(physics_fallback, 1),
                ml_correction=0.0,
                confidence_low=round(physics_fallback * 0.9, 1),
                confidence_high=round(physics_fallback * 1.1, 1),
                physics_weight=1.0,
                features_used=sefer,
            )

    def explain_prediction(self, sefer: Dict) -> Dict:
        """
        Tahmin sonucunu açıkla (XAI - Explainable AI).
        Hassasiyet analizi (Sensitivity Analysis) kullanarak her feature'ın
        tahmin üzerindeki etkisini (L/100km delta) hesaplar.
        """
        # 1. Base tahmini al
        baseline_res = self.predict(sefer)
        base_val = baseline_res.tahmin_l_100km

        explanations = {}

        # 2. Önemli feature grupları üzerinde perturbasyon yap
        # Her feature'ı %10 artırıp/azaltıp tahmindeki değişime bakıyoruz (Simple Sensitivity)
        perturbation_targets = {
            "ton": "Yük",
            "ascent_m": "Yol Eğimi (Çıkış)",
            "zorluk": "Yol Zorluğu",
            "arac_yasi": "Araç Yaşı",
            "mevsim_faktor": "Mevsim Koşulları",
            "sofor_katsayi": "Sürücü Performansı",
            "motorway_ratio": "Otoyol Kullanımı",
            "stopgo_proxy": "Dur-Kalk Yoğunluğu",
        }

        for feature_key, display_name in perturbation_targets.items():
            if (
                feature_key not in sefer
                and feature_key not in baseline_res.features_used
            ):
                continue

            raw_val = baseline_res.features_used.get(feature_key, 0)

            # Değeri azaltmış gibi yapalım (etkiyi görmek için)
            test_sefer = sefer.copy()

            if feature_key == "zorluk":
                # Kategorik zorluk: Zor -> Normal, Normal -> Kolay
                current_zorluk = str(raw_val)
                z_map_inv = {
                    "Zor": "Normal",
                    "Çok Zor": "Zor",
                    "Normal": "Kolay",
                    "Kolay": "Kolay",
                }
                test_sefer[feature_key] = z_map_inv.get(current_zorluk, "Normal")
            else:
                # Sayısal değerler için %20 azaltma
                try:
                    val = float(raw_val)
                    test_sefer[feature_key] = val * 0.8
                except (ValueError, TypeError):
                    continue

            test_res = self.predict(test_sefer)
            delta = base_val - test_res.tahmin_l_100km

            # Etkiyi normalize et (Sadece anlamlı değişimleri raporla)
            if abs(delta) > 0.05:
                explanations[display_name] = round(delta, 2)

        # 3. Fizik motoru vs ML düzeltmesi bilgisini ekle
        explanations["ML Düzeltmesi"] = baseline_res.ml_correction

        return {
            "prediction": base_val,
            "unit": "L/100km",
            "contributions": explanations,
            "confidence": baseline_res.confidence_high - baseline_res.confidence_low,
        }

    def _calculate_checksum(self, filepath: str) -> str:
        """Dosya için SHA256 checksum hesapla"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def save_model(self, filepath: str):
        """Model parametrelerini kaydet (Güvenli Hibrit Format)"""
        if not self.is_trained:
            raise RuntimeError("Model eğitilmedi")

        import json

        import joblib

        base_path = Path(filepath).with_suffix("")

        # 1. Sklearn modelleri (Joblib - %100 Güvenlik için Checksum eklenecek)
        sklearn_file = f"{base_path}_sklearn.joblib"
        sklearn_data = {
            "gb_model": self.gb_model,
            "rf_model": self.rf_model,
            "xgb_model": self.xgb_model,
            "lgb_model": self.lgb_model,
            "scaler": self.scaler,
        }
        joblib.dump(sklearn_data, sklearn_file)

        # Checksum hesapla
        sklearn_checksum = self._calculate_checksum(sklearn_file)

        # 2. Native Modeller (Daha güvenli JSON formatı)
        if XGBOOST_AVAILABLE and self.xgb_model:
            # XGBRegressor'da save_model mevcuttur
            self.xgb_model.save_model(f"{base_path}_xgb.json")

        if LIGHTGBM_AVAILABLE and self.lgb_model:
            # LGBMRegressor'da save_model yoktur, booster üzerinden kaydedilir
            if hasattr(self.lgb_model, "booster_"):
                self.lgb_model.booster_.save_model(f"{base_path}_lgb.json")
            else:
                # Eğer henüz eğitilmemişse (fit çağrılmamışsa) booster_ oluşmaz
                logger.warning("LightGBM booster bulunamadı, JSON kaydedilemedi.")

        # 3. Metadata (JSON - Checksum buraya kaydedilir)
        metadata = {
            "physics_weight": self.physics_weight,
            "training_stats": self.training_stats,
            "is_trained": self.is_trained,
            "last_updated": date.today().isoformat(),
            "sklearn_checksum": sklearn_checksum,
            "model_weights": self.weights,  # Persist dynamic weights
            # 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 26): FEATURE_NAMES'in
            # SIRALI hash'i (bkz. __init__) — load_model bunu okuyup çalışma-zamanı
            # _feature_hash ile karşılaştırır. Eskiden sadece feature SAYISI
            # kontrol ediliyordu (_resolve_expected_feature_count); isim/sıra
            # değişip sayı aynı kalırsa sessiz feature-drift mümkündü.
            "feature_schema_hash": self._feature_hash,
        }
        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Ensemble model saved (hybrid) to {base_path} with checksum {sklearn_checksum[:8]}"
        )

    def load_model(self, filepath: str):
        """Model parametrelerini yükle (Güvenli SHA256 Doğrulamalı)"""
        import json

        import joblib

        base_path = Path(filepath).with_suffix("")

        # 1. Metadata yükle
        meta_file = Path(f"{base_path}_meta.json")
        if not meta_file.exists():
            raise FileNotFoundError(f"Metadata dosyası bulunamadı: {meta_file}")

        with open(meta_file, encoding="utf-8") as f:
            metadata = json.load(f)

        self.physics_weight = metadata["physics_weight"]
        self.training_stats = metadata["training_stats"]
        self.is_trained = metadata["is_trained"]
        self.weights = metadata.get(
            "model_weights", self.DEFAULT_WEIGHTS.copy()
        )  # Load weights
        # 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 26): persisted
        # feature-isim/sıra hash'i — çağıran (ensemble_service.get_predictor)
        # bunu güncel `self._feature_hash` ile karşılaştırıp sessiz feature
        # drift'i yakalar. None olması eski (bu alan eklenmeden önce
        # kaydedilmiş) bir model dosyası anlamına gelir — çağıran bunu
        # "karşılaştırılamaz" olarak ele almalı, yanlışlıkla mismatch değil.
        self._loaded_feature_schema_hash = metadata.get("feature_schema_hash")
        expected_checksum = metadata.get("sklearn_checksum")

        # 2. Sklearn modelleri yükle (GÜVENLİK KRİTİK: Checksum doğrulaması)
        sklearn_file = Path(f"{base_path}_sklearn.joblib")
        if sklearn_file.exists():
            # Checksum doğrula
            if expected_checksum:
                actual_checksum = self._calculate_checksum(str(sklearn_file))
                if actual_checksum != expected_checksum:
                    logger.error(
                        f"GÜVENLİK İHLALİ: Model dosyası checksum uyuşmazlığı! {sklearn_file}. Expected: {expected_checksum}, Actual: {actual_checksum}"  # noqa: E501
                    )
                    raise SecurityError(
                        "Model dosyası bozulmuş veya değiştirilmiş olabilir!"
                    )
            else:
                logger.warning(
                    f"Model yüklendi ancak checksum doğrulaması yapılamadı (metadata eksik): {sklearn_file}"
                )

            # joblib.load öncesi dosya boyutu kontrolü (DoS protection için çok büyük dosya engelleme)
            if sklearn_file.stat().st_size > 100 * 1024 * 1024:  # 100MB limit
                logger.error(
                    f"Güvenlik uyarısı: Model dosyası çok büyük! {sklearn_file}"
                )
                raise SecurityError(
                    "Model dosyası kabul edilebilir boyut limitini aşıyor."
                )

            sklearn_data = joblib.load(sklearn_file)
            self.gb_model = sklearn_data.get("gb_model", self.gb_model)
            self.rf_model = sklearn_data.get("rf_model", self.rf_model)
            self.xgb_model = sklearn_data.get("xgb_model", self.xgb_model)
            self.lgb_model = sklearn_data.get("lgb_model", self.lgb_model)
            self.scaler = sklearn_data.get("scaler", self.scaler)
            logger.debug(f"Sklearn models loaded and verified: {sklearn_file}")

        # 3. Native Modelleri yükle (JSON formatı doğal olarak daha güvenlidir)
        if XGBOOST_AVAILABLE and self.xgb_model is None:
            xgb_file = Path(f"{base_path}_xgb.json")
            if xgb_file.exists():
                import xgboost as xgb_lib

                self.xgb_model = xgb_lib.XGBRegressor()
                self.xgb_model.load_model(str(xgb_file))

        if LIGHTGBM_AVAILABLE and self.lgb_model is None:
            lgb_file = Path(f"{base_path}_lgb.json")
            if lgb_file.exists():
                import lightgbm as lgb_lib

                self.lgb_model = lgb_lib.LGBMRegressor()
                # If we are here, we are using the native JSON fallback
                # This part is more complex for LGBMRegressor wrapper,
                # but joblib above should have handled it in most cases.
                booster = lgb_lib.Booster(model_file=str(lgb_file))
                self.lgb_model._Booster = booster

        logger.info(f"Ensemble model loaded and verified from {base_path}")
        return {"success": True}
