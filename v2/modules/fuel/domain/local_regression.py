"""
Basit yakıt tüketim regresyonu — scikit-learn tabanlı.

Eski el yapımı NumPy normal-equation implementasyonunun yerine geçer.
sklearn.linear_model.LinearRegression + StandardScaler kullanarak aynı
işi 6 satırda, bakım yükü sıfır ve doğrulama testleriyle yapıyor.

Bu modül yalnızca "lightweight fallback" olarak tutulmaktadır; asıl
tahmin pipeline'ı EnsembleFuelPredictor (prediction_ml modülü) üzerinden işler.
"""

from typing import Dict, Optional, Tuple

import numpy as np

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler

    _SKLEARN_OK = True
except ImportError:  # pragma: no cover
    _SKLEARN_OK = False


class LinearRegressionModel:
    """
    Yakıt tüketim doğrusal regresyonu.

    sklearn.linear_model.LinearRegression + StandardScaler kullanır.
    API, eski NumPy tabanlı implementasyonla geriye dönük uyumludur.
    """

    def __init__(self) -> None:
        self._is_fitted = False
        self.r_squared_score = 0.0
        self.n_samples = 0

        if _SKLEARN_OK:
            self._scaler = StandardScaler()
            self._model = LinearRegression()
        else:  # pragma: no cover
            self._scaler = None
            self._model = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """
        Modeli eğit.

        Args:
            X: Özellik matrisi (n_samples, n_features)
            y: Hedef vektör (n_samples,) — L/100km değerleri

        Returns:
            Dict: Eğitim sonuçları
        """
        if not _SKLEARN_OK:
            return {"success": False, "error": "scikit-learn kütüphanesi yüklü değil."}

        self.n_samples = len(y)
        if self.n_samples < 2:
            raise ValueError(
                f"Eğitim için en az 2 veri noktası gerekli; {self.n_samples} verildi."
            )

        X_scaled = self._scaler.fit_transform(X)
        self._model.fit(X_scaled, y)

        y_pred = self._model.predict(X_scaled)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        ss_res = np.sum((y - y_pred) ** 2)
        self.r_squared_score = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
        self._is_fitted = True

        return {
            "success": True,
            "r_squared": round(self.r_squared_score, 4),
            "sample_count": int(self.n_samples),
            "coefficients": {
                "intercept": float(self._model.intercept_),
                "weights": [round(float(c), 6) for c in self._model.coef_],
            },
            "scaling": {
                "mean": [round(float(m), 4) for m in self._scaler.mean_],
                "std": [round(float(s), 4) for s in self._scaler.scale_],
            },
        }

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        Tahmin üret.

        Args:
            X: Özellik matrisi (n_samples, n_features)

        Returns:
            Tuple[np.ndarray, Dict]: (Tahminler, Meta)
        """
        if not self._is_fitted:
            raise RuntimeError("Model henüz eğitilmedi.")

        X_scaled = self._scaler.transform(X)
        y_pred = self._model.predict(X_scaled)
        return y_pred, {"r_squared": self.r_squared_score, "scaled": True}

    # ------------------------------------------------------------------
    # Legacy compatibility (kullanılan yerleri kırmamak için)
    # ------------------------------------------------------------------

    @property
    def coefficients(self) -> Optional[np.ndarray]:
        if not self._is_fitted:
            return None
        return self._model.coef_

    @coefficients.setter
    def coefficients(self, value: np.ndarray) -> None:
        """Allow tests and legacy callers to inject coefficients directly."""
        self._model.coef_ = np.asarray(value)
        self._is_fitted = True

    @property
    def intercept(self) -> float:
        if not self._is_fitted:
            return 0.0
        return float(self._model.intercept_)

    @intercept.setter
    def intercept(self, value: float) -> None:
        """Allow tests and legacy callers to inject intercept directly."""
        self._model.intercept_ = float(value)
        self._is_fitted = True

    def get_scaling_params(self) -> Optional[Dict]:
        """Ölçekleme parametrelerini döndür (model kalıcılığı için)."""
        if not self._is_fitted:
            return None
        return {
            "mean": self._scaler.mean_.tolist(),
            "std": self._scaler.scale_.tolist(),
        }

    def set_scaling_params(self, params: Dict) -> None:
        """Kaydedilmiş ölçekleme parametrelerini yükle."""
        if not _SKLEARN_OK:
            return
        self._scaler.mean_ = np.array(params["mean"])
        self._scaler.scale_ = np.array(params["std"])
        self._scaler.var_ = np.array(params["std"]) ** 2
        self._scaler.n_features_in_ = len(params["mean"])
