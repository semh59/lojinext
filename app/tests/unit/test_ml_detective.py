import threading

import numpy as np
import pytest

from v2.modules.driver.domain.performance_ml import DriverPerformanceML
from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor
from v2.modules.prediction_ml.domain.kalman_estimator import KalmanFuelEstimator
from v2.modules.prediction_ml.domain.time_series_predictor import TimeSeriesPredictor


def test_ensemble_race_condition_protection():
    predictor = EnsembleFuelPredictor()
    # Dummy data for fit
    seferler = [{"mesafe_km": 100, "ton": 20}] * 20
    y = np.array([30.0] * 20)

    def train_worker():
        predictor.fit(seferler, y)

    def predict_worker():
        # Eğitim sürerken tahmin yapmaya çalış
        try:
            res = predictor.predict(seferler[0])
            # Eğitim sırasında is_trained False olacağı için sadece fizik tahmini dönmeli
            # Lock sayesinde predict bekleyecek veya is_trained=False görecek
            assert res is not None
        except Exception as e:
            pytest.fail(f"Predict failed during training: {e}")

    # Aynı anda hem eğitim hem tahmin başlat
    t1 = threading.Thread(target=train_worker)
    t2 = threading.Thread(target=predict_worker)

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert predictor.is_trained is True


def test_kalman_fading_memory():
    estimator = KalmanFuelEstimator()
    np.trace(estimator.state.P)

    # Çok sayıda update yap (normalde P küçülür)
    features = {"ton": 20, "ascent_m": 100, "arac_yasi": 5}
    for _ in range(100):
        estimator.update(features, 32.0)

    # Fading memory sayesinde P aşırı küçülmemeli (divergence protection)
    # 1.01 faktörü ve Q diag ile besleniyor
    final_P_trace = np.trace(estimator.state.P)
    assert final_P_trace > 0.1, f"P matrix collapsed: {final_P_trace}"


def test_time_series_padding_safety():
    predictor = TimeSeriesPredictor()
    # Sadece 5 günlük veri (Gereken: 30+7=37)
    short_data = [
        {
            "tarih": "2024-01-01",
            "ort_tuketim": 32.0,
            "toplam_km": 100,
            "ort_ton": 20,
            "sefer_sayisi": 2,
        }
    ] * 5

    features = predictor.prepare_features(short_data)
    targets = np.array([32.0] * 5)

    # create_sequences hata vermemeli, padding yapmalı
    X, y = predictor.create_sequences(features, targets)
    assert X.shape[0] > 0
    assert X.shape[1] == predictor.SEQUENCE_LENGTH


def test_driver_performance_consistency_formula():
    ml = DriverPerformanceML()
    # Tutarsız şoför (En iyi 25, En kötü 45, Ort 35)
    stats = {
        "en_iyi_tuketim": 25.0,
        "en_kotu_tuketim": 45.0,
        "ort_tuketim": 35.0,
        "toplam_sefer": 10,
    }
    features = ml.prepare_features([stats])[0]
    consistency_idx = ml.FEATURE_NAMES.index("tuketim_tutarliligi")
    val = features[consistency_idx]

    # abs(45-25)/35 = 20/35 approx 0.57
    assert 0.5 < val < 0.6
