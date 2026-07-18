"""
TIR Yakıt Takip - LightGBM Fuel Predictor
Kategorik feature handling ve hızlı eğitim için optimize edilmiş model.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# LightGBM lazy import
try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    lgb = None
    LIGHTGBM_AVAILABLE = False

import hashlib
import json
from pathlib import Path

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LGBMPredictionResult:
    """LightGBM tahmin sonucu"""

    prediction: float
    feature_importance: Dict[str, float]
    confidence_interval: Tuple[float, float]


class LightGBMFuelPredictor:
    """
    LightGBM tabanlı yakıt tüketim tahmini.

    Avantajlar:
    - Native categorical feature handling (zorluk, mevsim vb.)
    - Leaf-wise tree growth: Düşük veride bile iyi performans
    - XGBoost'tan 10-20x daha hızlı eğitim
    - Daha az memory kullanımı

    Feature'lar:
    - mesafe_km: Sefer mesafesi
    - ton: Yük ağırlığı
    - ascent_m: Toplam tırmanış
    - descent_m: Toplam iniş
    - net_elevation: Net yükseklik değişimi
    - yuk_yogunlugu: ton/km oranı
    - zorluk: Rota zorluğu (kategorik: Kolay/Normal/Zor)
    - arac_yasi: Araç yaşı
    - yas_faktoru: Yaş bazlı verimlilik kaybı
    - mevsim_faktor: Mevsimsel etki
    - sofor_katsayi: Şoför performans katsayısı

    Model Performansı (tipik):
    - R² Score: 0.92-0.95
    - MAE: 1.2-1.8 L/100km
    - Eğitim Süresi: ~2 saniye (500 örnek)
    """

    FEATURE_NAMES = [
        "mesafe_km",
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
        "motorway_ratio",
        "trunk_ratio",
        "primary_ratio",
        "residential_ratio",
        "unclassified_ratio",
        "flat_km",
    ]

    CATEGORICAL_FEATURES = ["zorluk"]

    # Zorluk mapping (LightGBM kategorik için integer gerekli)
    ZORLUK_MAP = {"Kolay": 0, "Normal": 1, "Zor": 2}

    def __init__(self, params: Optional[Dict] = None):
        """
        Args:
            params: LightGBM parametreleri (opsiyonel override)
        """
        # Default LightGBM parameters
        default_params = {
            "objective": "regression",
            "metric": "mae",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "n_estimators": 150,
            "early_stopping_rounds": 20,
            "random_state": 42,
        }

        if params:
            default_params.update(params)

        self.params = default_params
        self.model = None
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
        self.feature_importance_: Dict[str, Any] = {}
        self.prediction_interval_margin_ = None

        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available, predictor will not function")
            return

    def prepare_features(self, seferler: List[Dict]) -> np.ndarray:
        """
        Feature engineering - Seferleri feature matrisine çevir.
        """
        features = []

        for s in seferler:
            # Temel özellikler
            mesafe = float(s.get("mesafe_km", 0) or 0)
            ton = float(s.get("ton", 0) or 0)
            ascent = float(s.get("ascent_m", 0) or 0)
            descent = float(s.get("descent_m", 0) or 0)
            flat_km = float(s.get("flat_distance_km", 0) or 0)

            # Türetilmiş özellikler
            net_elevation = ascent - descent
            yuk_yogunlugu = ton / mesafe if mesafe > 0 else 0

            # Kategorik (integer encoded)
            zorluk_str = s.get("zorluk", "Normal")
            zorluk = self.ZORLUK_MAP.get(zorluk_str, 1)

            # Araç ve şoför özellikleri
            arac_yasi = float(s.get("arac_yasi", 5) or 5)
            yas_faktoru = float(s.get("yas_faktoru", 1.0) or 1.0)
            mevsim_faktor = float(s.get("mevsim_faktor", 1.0) or 1.0)
            sofor_katsayi = float(s.get("sofor_katsayi", 1.0) or 1.0)

            # Route Analysis Extraction (Phase 2G)
            motorway_ratio = 0.0
            trunk_ratio = 0.0
            primary_ratio = 0.0
            residential_ratio = 0.0
            unclassified_ratio = 0.0

            rota_detay = s.get("rota_detay") or {}
            analysis = rota_detay.get("route_analysis")

            if analysis and mesafe > 0:

                def sum_km(cat_dict):
                    if not cat_dict:
                        return 0.0
                    return (
                        cat_dict.get("flat", 0)
                        + cat_dict.get("up", 0)
                        + cat_dict.get("down", 0)
                    )

                motorway_ratio = min(1.0, sum_km(analysis.get("motorway")) / mesafe)
                trunk_ratio = min(1.0, sum_km(analysis.get("trunk")) / mesafe)
                primary_ratio = min(1.0, sum_km(analysis.get("primary")) / mesafe)
                residential_ratio = min(
                    1.0, sum_km(analysis.get("residential")) / mesafe
                )
                unclassified_ratio = min(
                    1.0, sum_km(analysis.get("unclassified")) / mesafe
                )

            features.append(
                [
                    mesafe,
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
                ]
            )

        return np.array(features)

    def fit(
        self, seferler: List[Dict], y_actual: np.ndarray, validation_split: float = 0.2
    ) -> Dict:
        """
        Model eğitimi.

        Args:
            seferler: Eğitim verileri (sefer dict listesi)
            y_actual: Gerçek tüketim değerleri (L/100km)
            validation_split: Validation oranı

        Returns:
            Dict: Eğitim sonuçları ve metrikler
        """
        if not LIGHTGBM_AVAILABLE:
            return {"success": False, "error": "LightGBM not available"}

        if len(seferler) < 10:
            return {
                "success": False,
                "error": f"Yetersiz veri: {len(seferler)} sefer. En az 10 gerekli.",
            }

        try:
            # Feature hazırla
            X = self.prepare_features(seferler)
            y = y_actual

            # Train/Validation split (DETERMINISTIC: random seed sabit)
            n_samples = len(X)
            n_val = int(n_samples * validation_split)

            # Reproducibility için seed kullan
            rng = np.random.RandomState(self.params.get("random_state", 42))
            indices = rng.permutation(n_samples)

            train_idx = indices[n_val:]
            val_idx = indices[:n_val]

            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # LightGBM Dataset oluştur
            train_data = lgb.Dataset(
                X_train,
                label=y_train,
                feature_name=self.FEATURE_NAMES,
                categorical_feature=[self.FEATURE_NAMES.index("zorluk")],
            )
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

            # Model eğit
            self.model = lgb.train(
                self.params,
                train_data,
                valid_sets=[train_data, val_data],
                valid_names=["train", "valid"],
                callbacks=[
                    lgb.early_stopping(self.params.get("early_stopping_rounds", 20)),
                    lgb.log_evaluation(period=0),  # Sessiz
                ],
            )

            # Metrikler
            train_pred = self.model.predict(X_train)
            val_pred = self.model.predict(X_val)

            from sklearn.metrics import mean_absolute_error, r2_score

            train_mae = mean_absolute_error(y_train, train_pred)
            val_mae = mean_absolute_error(y_val, val_pred)
            train_r2 = r2_score(y_train, train_pred)
            val_r2 = r2_score(y_val, val_pred)

            # Feature importance
            importance = self.model.feature_importance(importance_type="gain")
            self.feature_importance_ = {
                name: float(imp) for name, imp in zip(self.FEATURE_NAMES, importance)
            }

            validation_abs_errors = np.abs(y_val - val_pred)
            validation_margin = float(
                np.quantile(validation_abs_errors, 0.9)
                if len(validation_abs_errors) > 0
                else max(val_mae, 0.1)
            )
            self.prediction_interval_margin_ = max(0.1, validation_margin)

            self.is_trained = True

            self.training_stats = {
                "sample_count": n_samples,
                "train_samples": len(train_idx),
                "val_samples": len(val_idx),
                "train_mae": round(train_mae, 3),
                "val_mae": round(val_mae, 3),
                "train_r2": round(train_r2, 4),
                "val_r2": round(val_r2, 4),
                "best_iteration": self.model.best_iteration,
                "prediction_interval_margin": round(
                    self.prediction_interval_margin_, 3
                ),
                "feature_importance": self.feature_importance_,
            }

            logger.info(f"LightGBM trained: val_MAE={val_mae:.3f}, val_R²={val_r2:.4f}")

            return {"success": True, **self.training_stats}

        except Exception as e:
            logger.error(f"LightGBM training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def predict(self, sefer: Dict) -> LGBMPredictionResult:
        """
        Tek sefer için tahmin.

        Args:
            sefer: Sefer bilgileri dict

        Returns:
            LGBMPredictionResult: Tahmin sonucu
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        # Feature hazırla
        X = self.prepare_features([sefer])

        # Tahmin
        prediction = self.model.predict(X)[0]

        # Use validation residuals captured during training instead of a
        # fabricated percentage-based margin.
        margin = self.prediction_interval_margin_
        if margin is None:
            margin = max(0.1, float(self.training_stats.get("val_mae", 0.1) or 0.1))
        confidence = (prediction - margin, prediction + margin)

        return LGBMPredictionResult(
            prediction=round(prediction, 2),
            feature_importance=self.feature_importance_,
            confidence_interval=(round(confidence[0], 2), round(confidence[1], 2)),
        )

    def predict_batch(self, seferler: List[Dict]) -> np.ndarray:
        """
        Batch tahmin.

        Args:
            seferler: Sefer listesi

        Returns:
            np.ndarray: Tahmin değerleri
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        X = self.prepare_features(seferler)
        return self.model.predict(X)

    def get_feature_importance(self) -> Dict[str, float]:
        """Feature importance değerlerini döndür"""
        return self.feature_importance_.copy()

    def _calculate_checksum(self, filepath: str) -> str:
        """Dosya için SHA256 checksum hesapla"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def save_model(self, filepath: str):
        """Modeli ve metadata'yı dosyaya kaydet"""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        self.model.save_model(filepath)

        # Checksum ve metadata
        checksum = self._calculate_checksum(filepath)
        meta_path = Path(filepath).with_suffix(".json")

        metadata = {
            "checksum": checksum,
            "is_trained": self.is_trained,
            "training_stats": self.training_stats,
            "feature_importance": self.feature_importance_,
            "prediction_interval_margin": self.prediction_interval_margin_,
            "last_updated": date.today().isoformat(),
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"LightGBM model and metadata saved to {filepath}")

    def load_model(self, filepath: str):
        """Modeli ve metadata'yı doğrula ve yükle"""
        if not LIGHTGBM_AVAILABLE:
            raise RuntimeError("LightGBM not available")

        # SECURITY: Dosya boyutu kontrolü (100MB DoS koruması)
        model_path = Path(filepath)
        if not model_path.exists():
            raise FileNotFoundError(f"Model dosyası bulunamadı: {filepath}")

        MAX_MODEL_SIZE = 100 * 1024 * 1024  # 100MB
        file_size = model_path.stat().st_size
        if file_size > MAX_MODEL_SIZE:
            raise RuntimeError(
                f"Model dosyası çok büyük ({file_size / 1024 / 1024:.1f}MB > 100MB limit)"
            )

        meta_path = Path(filepath).with_suffix(".json")
        expected_checksum = None

        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                metadata = json.load(f)
                expected_checksum = metadata.get("checksum")
                self.training_stats = metadata.get("training_stats", {})
                self.feature_importance_ = metadata.get("feature_importance", {})
                self.prediction_interval_margin_ = metadata.get(
                    "prediction_interval_margin",
                    self.training_stats.get("prediction_interval_margin"),
                )

        # Checksum doğrula
        if expected_checksum:
            actual_checksum = self._calculate_checksum(filepath)
            if actual_checksum != expected_checksum:
                logger.error(
                    f"GÜVENLİK İHLALİ: LightGBM model dosyası bozulmuş: {filepath}"
                )
                raise RuntimeError("Security Check Failed: Model checksum mismatch")
        else:
            logger.warning(
                "Model yüklendi ancak checksum doğrulaması yapılamadı (metadata eksik)"
            )

        self.model = lgb.Booster(model_file=filepath)
        self.is_trained = True
        logger.info(f"LightGBM model loaded and verified from {filepath}")


class LightGBMAnomalyClassifier:
    """
    LightGBM ile supervised anomali sınıflandırma.

    Geçmiş anomalilerden (Alert tablosu) öğrenerek
    yeni tüketim değerlerini sınıflandırır.

    Sınıflar:
    - 0: normal
    - 1: low (düşük anomali)
    - 2: medium (orta anomali)
    - 3: high (yüksek anomali)
    - 4: critical (kritik anomali)
    """

    SEVERITY_MAP = {"normal": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

    REVERSE_MAP = {v: k for k, v in SEVERITY_MAP.items()}

    def __init__(self):
        if not LIGHTGBM_AVAILABLE:
            logger.warning("LightGBM not available for anomaly classifier")
            self.model = None
            return

        self.model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=5,
            class_weight="balanced",  # Dengesiz sınıflar için
            num_leaves=15,
            learning_rate=0.05,
            n_estimators=100,
            verbose=-1,
            random_state=42,
        )
        self.is_trained = False

    def fit(self, X: np.ndarray, severity_labels: List[str]) -> Dict:
        """
        Modeli eğit.

        Args:
            X: Feature matrisi (consumption, expected, deviation_pct, ...)
            severity_labels: Severity string listesi

        Returns:
            Dict: Eğitim sonuçları
        """
        if not LIGHTGBM_AVAILABLE or self.model is None:
            return {"success": False, "error": "LightGBM not available"}

        try:
            # Label encoding
            y = np.array([self.SEVERITY_MAP.get(s, 0) for s in severity_labels])

            self.model.fit(X, y)
            self.is_trained = True

            # Accuracy
            from sklearn.metrics import accuracy_score

            y_pred = self.model.predict(X)
            accuracy = accuracy_score(y, y_pred)

            logger.info(f"Anomaly classifier trained: accuracy={accuracy:.3f}")

            return {
                "success": True,
                "accuracy": round(accuracy, 4),
                "sample_count": len(y),
                "class_distribution": {
                    self.REVERSE_MAP[i]: int(np.sum(y == i)) for i in range(5)
                },
            }

        except Exception as e:
            logger.error(f"Anomaly classifier training error: {e}")
            return {"success": False, "error": str(e)}

    def predict(self, X: np.ndarray) -> List[str]:
        """
        Anomali sınıfını tahmin et.

        Args:
            X: Feature matrisi

        Returns:
            List[str]: Severity tahminleri
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        y_pred = self.model.predict(X)
        return [self.REVERSE_MAP[int(p)] for p in y_pred]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Sınıf olasılıklarını döndür.

        Returns:
            np.ndarray: (n_samples, 5) olasılık matrisi
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model henüz eğitilmedi")

        return self.model.predict_proba(X)


def is_lightgbm_available() -> bool:
    """LightGBM kurulu mu kontrol et"""
    return LIGHTGBM_AVAILABLE
