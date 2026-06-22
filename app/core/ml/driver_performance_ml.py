"""
TIR Yakıt Takip - LightGBM Şoför Performans ML Modeli
Şoför verimlilik sıralaması ve performans tahmini
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

# LightGBM lazy import
try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    lgb = None
    LIGHTGBM_AVAILABLE = False

# sklearn lazy import
try:
    from sklearn.metrics import mean_absolute_error, r2_score

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DriverScorePrediction:
    """Şoför performans tahmin sonucu"""

    predicted_score: float
    rank: int
    percentile: float
    efficiency_grade: str  # A, B, C, D, F
    confidence: float
    feature_importance: Dict[str, float]


class DriverPerformanceML:
    """
    LightGBM tabanlı şoför performans ML modeli.

    Özellikler:
    1. Verimlilik Skoru Tahmini (Regresyon)
    2. Şoför Sıralaması (Ranking)
    3. Performans Sınıflandırması (A/B/C/D/F)

    Features:
    - Toplam sefer sayısı
    - Toplam km
    - Ortalama tüketim
    - Filo karşılaştırma (%)
    - En iyi/kötü tüketim oranı
    - Trend (improving/stable/declining)
    - Güzergah çeşitliliği
    - Boş sefer oranı
    """

    FEATURE_NAMES = [
        "toplam_sefer",
        "toplam_km",
        "ort_tuketim",
        "filo_karsilastirma",
        "tuketim_tutarliligi",
        "trend_encoded",
        "guzergah_cesitliligi",
        "bos_sefer_orani",
        "km_per_sefer",
        "ton_per_km",
    ]

    GRADE_THRESHOLDS = {"A": 85, "B": 70, "C": 55, "D": 40, "F": 0}

    def __init__(self):
        if LIGHTGBM_AVAILABLE:
            self.regressor = lgb.LGBMRegressor(
                objective="regression",
                num_leaves=15,
                learning_rate=0.05,
                n_estimators=100,
                min_child_samples=3,
                verbose=-1,
                random_state=42,
            )
            self.ranker = lgb.LGBMRanker(
                objective="lambdarank",
                num_leaves=15,
                learning_rate=0.05,
                n_estimators=100,
                verbose=-1,
                random_state=42,
            )
            self.is_trained = False
            self.ranker_trained = False
            self.feature_importance = {}
            logger.info("DriverPerformanceML initialized with LightGBM")
        else:
            self.regressor = None
            self.ranker = None
            self.is_trained = False
            self.ranker_trained = False
            logger.warning("LightGBM not available, DriverPerformanceML disabled")

    def prepare_features(self, driver_stats: List[Dict]) -> np.ndarray:
        """
        Şoför istatistiklerinden feature matrisi oluştur.

        Args:
            driver_stats: Şoför istatistikleri listesi

        Returns:
            np.ndarray: (n_drivers, n_features) feature matrisi
        """
        features = []

        for stats in driver_stats:
            toplam_sefer = int(stats.get("toplam_sefer", 0) or 0)
            toplam_km = float(stats.get("toplam_km", 0) or 0)
            ort_tuketim = float(stats.get("ort_tuketim", 32.0) or 32.0)
            filo_karsilastirma = float(stats.get("filo_karsilastirma", 0) or 0)

            en_iyi = float(stats.get("en_iyi_tuketim", ort_tuketim) or ort_tuketim)
            en_kotu = float(stats.get("en_kotu_tuketim", ort_tuketim) or ort_tuketim)

            # Formül iyileştirildi: Ortalama tüketime göre uç değerlerin yayılımı
            # Mantıksal Hata Fix: en_iyi/en_kotu yerine (kotu-iyi)/ort kullanılarak daha anlamlı bir tutarsızlık puanı üretilir  # noqa: E501
            # Güvenli bölme: ort_tuketim sıfır ise inf oluşmasını engelle
            safe_ort_tuketim = max(ort_tuketim, 1e-6)
            tuketim_tutarliligi = abs(en_kotu - en_iyi) / safe_ort_tuketim

            # Trend encoding
            trend = stats.get("trend", "stable")
            trend_map = {"improving": 1, "stable": 0, "declining": -1}
            trend_encoded = trend_map.get(trend, 0)

            guzergah_sayisi = int(stats.get("guzergah_sayisi", 1) or 1)
            bos_sefer = int(stats.get("bos_sefer_sayisi", 0) or 0)
            bos_sefer_orani = bos_sefer / toplam_sefer if toplam_sefer > 0 else 0

            km_per_sefer = toplam_km / toplam_sefer if toplam_sefer > 0 else 0

            toplam_ton = float(stats.get("toplam_ton", 0) or 0)
            ton_per_km = toplam_ton / toplam_km * 1000 if toplam_km > 0 else 0

            # NOT: Bu hesaplamalar sadece tamamlanmış seferler üzerinden yapıldığı için
            # "Survival Bias" riski taşır. Sefer iptalleri veya kaza gibi negatif durumlar
            # şoför skorunu düşürmelidir ancak mevcut schema sadece başarılı seferleri tutar.
            features.append(
                [
                    toplam_sefer,
                    toplam_km / 1000,  # Bin km
                    ort_tuketim,
                    filo_karsilastirma,
                    tuketim_tutarliligi,
                    trend_encoded,
                    guzergah_sayisi,
                    bos_sefer_orani,
                    km_per_sefer / 100,  # 100 km
                    ton_per_km,
                ]
            )

        return np.array(features, dtype=np.float32)

    def train(self, driver_stats: List[Dict], performance_scores: List[float]) -> Dict:
        """
        Model eğitimi.

        Args:
            driver_stats: Şoför istatistikleri
            performance_scores: Gerçek performans puanları (0-100)

        Returns:
            Dict: Eğitim sonuçları
        """
        if not LIGHTGBM_AVAILABLE or self.regressor is None:
            return {"success": False, "error": "LightGBM not available"}

        if len(driver_stats) < 5:
            return {
                "success": False,
                "error": f"Yetersiz veri: {len(driver_stats)} şoför. En az 5 gerekli.",
            }

        try:
            X = self.prepare_features(driver_stats)
            y = np.array(performance_scores, dtype=np.float32)

            # Regressor eğit
            self.regressor.fit(X, y)

            # Metrikler
            y_pred = self.regressor.predict(X)
            mae = mean_absolute_error(y, y_pred)
            r2 = r2_score(y, y_pred)

            # Feature importance
            importances = self.regressor.feature_importances_
            self.feature_importance = {
                name: round(float(imp), 4)
                for name, imp in zip(self.FEATURE_NAMES, importances)
            }

            self.is_trained = True

            logger.info(f"DriverPerformanceML trained: MAE={mae:.3f}, R²={r2:.4f}")

            return {
                "success": True,
                "mae": round(mae, 3),
                "r2": round(r2, 4),
                "sample_count": len(y),
                "feature_importance": self.feature_importance,
            }

        except Exception as e:
            logger.error(f"Training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def train_ranker(self, driver_stats: List[Dict], rankings: List[int]) -> Dict:
        """
        LightGBM Ranker eğitimi.

        Args:
            driver_stats: Şoför istatistikleri
            rankings: Şoför sıralamaları (1 = en iyi)

        Returns:
            Dict: Eğitim sonuçları
        """
        if not LIGHTGBM_AVAILABLE or self.ranker is None:
            return {"success": False, "error": "LightGBM not available"}

        if len(driver_stats) < 5:
            return {
                "success": False,
                "error": f"Yetersiz veri: {len(driver_stats)} şoför.",
            }

        try:
            X = self.prepare_features(driver_stats)
            y = np.array(rankings, dtype=np.float32)

            # Tüm veri tek bir grup
            group = [len(y)]

            self.ranker.fit(X, y, group=group)
            self.ranker_trained = True

            logger.info("DriverPerformanceML Ranker trained")

            return {"success": True, "sample_count": len(y)}

        except Exception as e:
            logger.error(f"Ranker training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def predict_score(self, driver_stats: Dict) -> DriverScorePrediction:
        """
        Tek şoför için performans skoru tahmin et.

        Args:
            driver_stats: Şoför istatistikleri

        Returns:
            DriverScorePrediction
        """
        if not self.is_trained or self.regressor is None:
            # Fallback: basit hesaplama
            filo_karsilastirma = float(driver_stats.get("filo_karsilastirma", 0) or 0)
            base_score = 50 + filo_karsilastirma
            return DriverScorePrediction(
                predicted_score=max(0, min(100, base_score)),
                rank=0,
                percentile=50.0,
                efficiency_grade=self._get_grade(base_score),
                confidence=0.3,
                feature_importance={},
            )

        X = self.prepare_features([driver_stats])
        predicted_score = float(self.regressor.predict(X)[0])
        predicted_score = max(0, min(100, predicted_score))

        return DriverScorePrediction(
            predicted_score=round(predicted_score, 1),
            rank=0,  # Ranking ayrı hesaplanmalı
            percentile=0.0,
            efficiency_grade=self._get_grade(predicted_score),
            confidence=0.8 if self.is_trained else 0.3,
            feature_importance=self.feature_importance,
        )

    def predict_batch(
        self, driver_stats_list: List[Dict]
    ) -> List[DriverScorePrediction]:
        """
        Toplu şoför performans tahmini ve sıralama.

        Args:
            driver_stats_list: Şoför istatistikleri listesi

        Returns:
            List[DriverScorePrediction]: Tahmin sonuçları
        """
        if not driver_stats_list:
            return []

        predictions = []

        for stats in driver_stats_list:
            pred = self.predict_score(stats)
            predictions.append(pred)

        # Sıralama hesapla
        scores = [p.predicted_score for p in predictions]
        sorted_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )

        for rank, idx in enumerate(sorted_indices, 1):
            predictions[idx] = DriverScorePrediction(
                predicted_score=predictions[idx].predicted_score,
                rank=rank,
                percentile=round((1 - rank / len(predictions)) * 100, 1),
                efficiency_grade=predictions[idx].efficiency_grade,
                confidence=predictions[idx].confidence,
                feature_importance=predictions[idx].feature_importance,
            )

        return predictions

    def _get_grade(self, score: float) -> str:
        """Puana göre grade belirle."""
        for grade, threshold in self.GRADE_THRESHOLDS.items():
            if score >= threshold:
                return grade
        return "F"

    def get_model_status(self) -> Dict:
        """Model durumu."""
        return {
            "lightgbm_available": LIGHTGBM_AVAILABLE,
            "regressor_trained": self.is_trained,
            "ranker_trained": self.ranker_trained,
            "feature_importance": self.feature_importance,
        }


# Singleton (Thread-Safe Double-Checked Locking)
import threading  # noqa: E402

_driver_ml = None
_driver_ml_lock = threading.Lock()


def get_driver_performance_ml() -> DriverPerformanceML:
    """Thread-safe singleton erişimi"""
    global _driver_ml
    if _driver_ml is None:
        with _driver_ml_lock:
            if _driver_ml is None:  # Double-checked locking
                _driver_ml = DriverPerformanceML()
    return _driver_ml
