"""
TIR Yakıt Takip - Kalman Filter Online Learning
Her yeni gözlem ile modeli güncelle (batch eğitim gerektirmez)
"""

import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.append(str(Path(__file__).parent.parent.parent))
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class KalmanState:
    """Kalman Filter durumu"""

    # State vector: [base_consumption, load_factor, elevation_factor, age_factor]
    state: np.ndarray = field(
        default_factory=lambda: np.array([32.0, 0.12, 0.008, 0.015])
    )
    # Covariance matrix (4x4)
    P: np.ndarray = field(default_factory=lambda: np.eye(4) * 5.0)
    # Observation count
    n_observations: int = 0
    # Last update timestamp
    last_update: Optional[datetime] = None


class KalmanFuelEstimator:
    """
    Basitleştirilmiş Kalman Filter yakıt tüketimi tahmini.

    State Vector (4 parametre):
    - state[0]: Base consumption (L/100km) - sabit mesafe için
    - state[1]: Load factor (L/100km per ton)
    - state[2]: Elevation factor (L/100km per 100m ascent)
    - state[3]: Age factor (L/100km per vehicle year)

    Model:
    consumption = state[0] + state[1]*ton + state[2]*ascent + state[3]*age

    Online learning: Her yeni sefer verisi ile güncellenir.
    """

    # Process noise (Q) - state'in zamanla ne kadar değişebileceği
    Q_DIAG = np.array([0.01, 0.001, 0.0001, 0.0005])

    # Measurement noise (R) - gözlem gürültüsü
    R = 4.0  # L/100km variance

    def __init__(self, arac_id: int = None):
        self.arac_id = arac_id
        self.state = KalmanState()

        # Process noise matrix
        self.Q = np.diag(self.Q_DIAG)

    def _build_observation_matrix(self, features: Dict) -> np.ndarray:
        """
        Gözlem matrisi H'yi oluştur.

        Features:
        - ton: Yük ağırlığı
        - ascent_100m: Yükseklik artışı (100m biriminde)
        - age: Araç yaşı
        """
        ton = float(features.get("ton", 0) or 0)
        ascent = float(features.get("ascent_m", 0) or 0) / 100.0  # 100m biriminde
        age = float(features.get("arac_yasi", 5) or 5)

        # H = [1, ton, ascent_100m, age]
        return np.array([1.0, ton, ascent, age])

    def predict(self, features: Dict) -> Tuple[float, float]:
        """
        Mevcut state ile tüketim tahmini yap.

        Returns:
            (tahmin, uncertainty)
        """
        H = self._build_observation_matrix(features)

        # Prediction: y = H * state
        prediction = np.dot(H, self.state.state)

        # Uncertainty: sqrt(H * P * H' + R)
        variance = np.dot(H, np.dot(self.state.P, H.T)) + self.R
        uncertainty = np.sqrt(max(0.1, variance))

        return round(prediction, 2), round(uncertainty, 2)

    def update(self, features: Dict, observed_consumption: float) -> Dict:
        """
        Yeni gözlem ile state'i güncelle (online learning).

        Kalman Update:
        1. K = P * H' * (H * P * H' + R)^-1  (Kalman gain)
        2. state = state + K * (z - H * state)  (State update)
        3. P = (I - K * H) * P  (Covariance update)

        Returns:
            Dict with update metrics
        """
        H = self._build_observation_matrix(features)
        z = observed_consumption  # Gözlem

        # Prediction
        y_pred = np.dot(H, self.state.state)

        # Innovation (prediction error)
        innovation = z - y_pred

        # Innovation covariance: S = H * P * H' + R
        S = np.dot(H, np.dot(self.state.P, H.T)) + self.R
        S = max(1e-10, S)  # Numerik underflow koruması

        # Kalman gain: K = P * H' * S^-1
        K = np.dot(self.state.P, H.T) / S

        # State update
        self.state.state = self.state.state + K * innovation

        # Covariance update: Joseph Form (P = (I-KH)P(I-KH)' + KRK')
        # Bu form numerik olarak çok daha kararlıdır ve P'nin simetrik kalmasını sağlar.
        I_KH = np.eye(4) - np.outer(K, H)
        self.state.P = (
            np.dot(I_KH, np.dot(self.state.P, I_KH.T)) + np.outer(K, K) * self.R
        )

        # "Fading Memory" / Unforgetting Factor (Divergence Protection)
        # P matrisinin aşırı küçülerek modelin yeni verilere "sağırlaşmasını" önler.
        self.state.P = self.state.P * 1.01  # %1 unutma faktörü

        # Add process noise (state drift over time)
        self.state.P = self.state.P + self.Q

        # Update metadata
        self.state.n_observations += 1
        self.state.last_update = datetime.now(timezone.utc)

        logger.debug(
            f"Kalman update: obs={z:.1f}, pred={y_pred:.1f}, innov={innovation:.2f}"
        )

        return {
            "observed": round(z, 2),
            "predicted": round(y_pred, 2),
            "innovation": round(innovation, 2),
            "n_observations": self.state.n_observations,
            "state": self.state.state.tolist(),
        }

    MAX_BATCH_SIZE = 1000  # DoS koruması için batch limiti

    def batch_update(self, observations: List[Dict]) -> Dict:
        """
        Birden fazla gözlem ile güncelle.

        Args:
            observations: [{'features': {...}, 'consumption': float}, ...]

        Raises:
            ValueError: Batch boyutu MAX_BATCH_SIZE'ı aşarsa
        """
        if len(observations) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch boyutu {self.MAX_BATCH_SIZE} aşılamaz (gönderilen: {len(observations)})"
            )

        for obs in observations:
            self.update(obs["features"], obs["consumption"])

        return {
            "updated": len(observations),
            "n_observations": self.state.n_observations,
            "state": self.state.state.tolist(),
        }

    def get_coefficients(self) -> Dict:
        """Mevcut katsayıları döndür"""
        return {
            "base_consumption": round(self.state.state[0], 2),
            "load_factor": round(self.state.state[1], 4),
            "elevation_factor": round(self.state.state[2], 4),
            "age_factor": round(self.state.state[3], 4),
            "n_observations": self.state.n_observations,
            "uncertainty": np.diag(self.state.P).tolist(),
        }

    def save_state(self) -> Dict:
        """State'i dictionary olarak kaydet"""
        return {
            "arac_id": self.arac_id,
            "state": self.state.state.tolist(),
            "P": self.state.P.tolist(),
            "n_observations": self.state.n_observations,
            "last_update": self.state.last_update.isoformat()
            if self.state.last_update
            else None,
        }

    def load_state(self, data: Dict):
        """
        State'i dictionary'den yükle.

        INPUT VALIDATION: Kötü veri ile state bozulmasını önler.
        """
        # Zorunlu alanlar kontrolü
        if "state" not in data or "P" not in data:
            raise ValueError("load_state: 'state' ve 'P' alanları zorunludur")

        # State vektörü validasyonu
        state_array = np.array(data["state"])
        if state_array.shape != (4,):
            raise ValueError(
                f"load_state: state vektörü (4,) olmalı, gelen: {state_array.shape}"
            )
        if not np.all(np.isfinite(state_array)):
            raise ValueError("load_state: state vektöründe NaN/Inf değer var")

        # P matrisi validasyonu
        P_array = np.array(data["P"])
        if P_array.shape != (4, 4):
            raise ValueError(
                f"load_state: P matrisi (4,4) olmalı, gelen: {P_array.shape}"
            )
        if not np.all(np.isfinite(P_array)):
            raise ValueError("load_state: P matrisinde NaN/Inf değer var")
        # Pozitif definitlik kontrolü (diagonal pozitif olmalı)
        if not np.all(np.diag(P_array) > 0):
            raise ValueError(
                "load_state: P matrisi pozitif tanımlı değil (diagonal elemanlar > 0 olmalı)"
            )

        # Tüm validasyonlar geçtiyse state'i yükle
        self.arac_id = data.get("arac_id")
        self.state.state = state_array
        self.state.P = P_array
        self.state.n_observations = data.get("n_observations", 0)
        if data.get("last_update"):
            self.state.last_update = datetime.fromisoformat(data["last_update"])


class KalmanEstimatorService:
    """Kalman estimator servis katmanı"""

    MAX_ESTIMATORS = 200  # Bellek yönetimi için limit

    def __init__(self):
        self._analiz_repo = None
        self.estimators: OrderedDict[int, KalmanFuelEstimator] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def analiz_repo(self):
        if self._analiz_repo is None:
            from v2.modules.analytics_executive.infrastructure.executive_read_models import (
                get_analiz_repo,
            )

            self._analiz_repo = get_analiz_repo()
        return self._analiz_repo

    def get_estimator(self, arac_id: int) -> KalmanFuelEstimator:
        """
        Araç için estimator al veya oluştur (Thread-Safe + LRU Cache).

        DB BLOCKING FIX: DB okuma lock dışında yapılır, sadece cache erişimi lock içinde.
        """
        # 1. Önce lock ile cache kontrol (hızlı yol)
        with self._lock:
            if arac_id in self.estimators:
                # LRU: En sona taşı
                self.estimators.move_to_end(arac_id)
                return self.estimators[arac_id]

        # 2. Cache'de yok - DB okuma LOCK DIŞINDA (blocking'i önler)
        estimator = KalmanFuelEstimator(arac_id)
        try:
            import asyncio as _asyncio

            try:
                _asyncio.get_running_loop()
                # Running inside an async context — skip blocking DB call.
                params = None
            except RuntimeError:
                params = _asyncio.run(self.analiz_repo.get_model_params(arac_id))
        except Exception as e:
            logger.warning(f"Kalman state load skipped: {e}")
            params = None
        if params and "kalman_state" in params.get("coefficients", {}):
            try:
                estimator.load_state(params["coefficients"]["kalman_state"])
                logger.info(f"Loaded Kalman state for vehicle {arac_id}")
            except Exception as e:
                logger.warning(f"Failed to load Kalman state: {e}")

        # 3. Lock ile cache'e ekle (double-check pattern)
        with self._lock:
            # Başka thread araya girmiş olabilir
            if arac_id in self.estimators:
                return self.estimators[arac_id]

            self.estimators[arac_id] = estimator

            # Limit kontrolü
            if len(self.estimators) > self.MAX_ESTIMATORS:
                oldest_id, _ = self.estimators.popitem(last=False)
                logger.debug(
                    f"LRU Cache: Arac {oldest_id} estimator bellekten temizlendi."
                )

            return estimator

    def update_with_trip(
        self, arac_id: int, features: Dict, observed_consumption: float
    ) -> Dict:
        """Yeni sefer verisi ile güncelle"""
        estimator = self.get_estimator(arac_id)
        result = estimator.update(features, observed_consumption)

        # State'i DB'ye kaydet
        self._save_to_db(arac_id, estimator)

        return result

    def predict(self, arac_id: int, features: Dict) -> Dict:
        """Tahmin yap"""
        estimator = self.get_estimator(arac_id)
        consumption, uncertainty = estimator.predict(features)

        return {
            "tahmin_l_100km": consumption,
            "uncertainty": uncertainty,
            "confidence_low": round(consumption - 2 * uncertainty, 1),
            "confidence_high": round(consumption + 2 * uncertainty, 1),
            "coefficients": estimator.get_coefficients(),
        }

    def _save_to_db(self, arac_id: int, estimator: KalmanFuelEstimator):
        """State'i veritabanına kaydet"""
        try:
            import asyncio as _asyncio

            state_dict = estimator.save_state()
            coro = self.analiz_repo.save_model_params(
                arac_id,
                {
                    "coefficients": {"kalman_state": state_dict},
                    "r_squared": 0,  # Kalman için N/A
                    "sample_count": estimator.state.n_observations,
                },
            )
            try:
                _asyncio.get_running_loop()
                # Running inside async — cannot call asyncio.run(); skip persist.
                logger.debug("Kalman state save skipped (async context)")
                coro.close()
            except RuntimeError:
                _asyncio.run(coro)
        except Exception as e:
            logger.error(f"Failed to save Kalman state: {e}")


# Singleton (Thread-Safe Double-Checked Locking)
_kalman_service = None
_kalman_service_lock = threading.Lock()


def get_kalman_service() -> KalmanEstimatorService:
    """Thread-safe singleton erişimi"""
    global _kalman_service
    if _kalman_service is None:
        with _kalman_service_lock:
            if _kalman_service is None:  # Double-checked locking
                _kalman_service = KalmanEstimatorService()
    return _kalman_service
