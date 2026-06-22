"""
LSTM Time Series Predictor Unit Tests
"""

import sys
from datetime import date, timedelta

import numpy as np
import pytest

sys.path.insert(0, ".")

from app.core.ml.time_series_predictor import (
    TORCH_AVAILABLE,
    TimeSeriesPrediction,
    TimeSeriesPredictor,
    is_lstm_available,
)


class TestLSTMAvailability:
    """LSTM (PyTorch) kullanılabilirlik testleri"""

    def test_torch_import(self):
        """PyTorch import kontrolü"""
        assert isinstance(TORCH_AVAILABLE, bool)

    def test_is_lstm_available_function(self):
        """is_lstm_available her zaman False döner — LSTM production'da
        devre dışı (KARAR 2026-05-28: ARIMA tabanlı time series)."""
        result = is_lstm_available()
        assert isinstance(result, bool)
        assert result is False


class TestTimeSeriesPredictor:
    """TimeSeriesPredictor sınıf testleri"""

    @pytest.fixture
    def predictor(self):
        """Test predictor instance"""
        return TimeSeriesPredictor()

    @pytest.fixture
    def sample_daily_data(self):
        """Test günlük veri"""
        base_date = date.today() - timedelta(days=60)
        data = []

        for i in range(60):
            current_date = base_date + timedelta(days=i)
            consumption = 32.0 + np.sin(i / 7 * np.pi) * 3 + np.random.normal(0, 1)

            data.append(
                {
                    "tarih": current_date,
                    "ort_tuketim": consumption,
                    "toplam_km": 500 + np.random.randint(-100, 100),
                    "ort_ton": 18 + np.random.random() * 4,
                    "sefer_sayisi": np.random.randint(3, 10),
                }
            )

        return data

    def test_init(self, predictor):
        """Predictor başlatma testi"""
        assert predictor is not None
        assert predictor.SEQUENCE_LENGTH == 30
        assert predictor.FORECAST_DAYS == 7
        assert predictor.FEATURE_COUNT == 11

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_model_creation(self, predictor):
        """Model oluşturma testi"""
        assert predictor.model is not None
        assert predictor.is_trained is False

    def test_prepare_features_shape(self, predictor, sample_daily_data):
        """Feature preparation shape testi"""
        features = predictor.prepare_features(sample_daily_data)

        assert features.shape[0] == len(sample_daily_data)
        assert features.shape[1] == predictor.FEATURE_COUNT

    def test_prepare_features_values(self, predictor, sample_daily_data):
        """Feature değerleri testi"""
        features = predictor.prepare_features(sample_daily_data)

        # İlk gün için temel kontroller
        assert features[0, 0] > 0  # ort_tuketim
        assert 0 <= features[0, 4] <= 1  # weekday normalized
        assert 0 <= features[0, 5] <= 1  # day_of_month normalized
        assert 0 <= features[0, 6] <= 1  # season normalized

    def test_create_sequences(self, predictor, sample_daily_data):
        """Sequence oluşturma testi"""
        features = predictor.prepare_features(sample_daily_data)
        targets = np.array([d["ort_tuketim"] for d in sample_daily_data])

        X, y = predictor.create_sequences(features, targets)

        # Beklenen sequence sayısı
        expected_sequences = (
            len(sample_daily_data)
            - predictor.SEQUENCE_LENGTH
            - predictor.FORECAST_DAYS
            + 1
        )

        assert X.shape[0] == expected_sequences
        assert X.shape[1] == predictor.SEQUENCE_LENGTH
        assert X.shape[2] == predictor.FEATURE_COUNT
        assert y.shape[0] == expected_sequences
        assert y.shape[1] == predictor.FORECAST_DAYS

    def test_normalize(self, predictor, sample_daily_data):
        """Normalization testi"""
        features = predictor.prepare_features(sample_daily_data)
        targets = np.array([d["ort_tuketim"] for d in sample_daily_data])

        X, y = predictor.create_sequences(features, targets)
        X_norm, y_norm = predictor.normalize(X, y, fit=True)

        # Normalization parametreleri kaydedilmeli
        assert predictor.feature_mean is not None
        assert predictor.feature_std is not None
        assert predictor.target_mean is not None
        assert predictor.target_std is not None

        # Normalize edilmiş değerler ortalama 0'a yakın olmalı
        assert abs(X_norm.mean()) < 1.0

    def test_denormalize(self, predictor, sample_daily_data):
        """Denormalization testi"""
        features = predictor.prepare_features(sample_daily_data)
        targets = np.array([d["ort_tuketim"] for d in sample_daily_data])

        X, y = predictor.create_sequences(features, targets)
        X_norm, y_norm = predictor.normalize(X, y, fit=True)

        # Denormalize
        y_denorm = predictor.denormalize_target(y_norm)

        # Orijinal değerlere yakın olmalı
        np.testing.assert_array_almost_equal(y, y_denorm, decimal=5)

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_train_insufficient_data(self, predictor):
        """Yetersiz veri ile eğitim testi"""
        small_data = [
            {"tarih": date.today() - timedelta(days=i), "ort_tuketim": 32.0}
            for i in range(10)
        ]

        result = predictor.train(small_data, epochs=10)

        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_train_success(self, predictor, sample_daily_data):
        """Başarılı eğitim testi"""
        result = predictor.train(sample_daily_data, epochs=5, batch_size=8)

        assert result["success"] is True
        assert "mae" in result
        assert "r2" in result
        assert predictor.is_trained is True

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_predict_after_training(self, predictor, sample_daily_data):
        """Eğitim sonrası tahmin testi"""
        predictor.train(sample_daily_data, epochs=5, batch_size=8)

        # Son 30 günü kullan
        recent_data = sample_daily_data[-30:]
        prediction = predictor.predict(recent_data, with_confidence=False)

        assert isinstance(prediction, TimeSeriesPrediction)
        assert len(prediction.forecast) == predictor.FORECAST_DAYS
        assert len(prediction.confidence_low) == predictor.FORECAST_DAYS
        assert len(prediction.confidence_high) == predictor.FORECAST_DAYS
        assert prediction.trend in ["increasing", "stable", "decreasing"]

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_predict_with_confidence(self, predictor, sample_daily_data):
        """Monte Carlo dropout güven aralığı testi"""
        predictor.train(sample_daily_data, epochs=5, batch_size=8)

        recent_data = sample_daily_data[-30:]
        prediction = predictor.predict(recent_data, with_confidence=True)

        # Güven aralığı kontrolleri
        for i in range(len(prediction.forecast)):
            assert prediction.confidence_low[i] <= prediction.forecast[i]
            assert prediction.forecast[i] <= prediction.confidence_high[i]

    def test_predict_without_training(self, predictor, sample_daily_data):
        """Eğitimsiz tahmin testi (hata beklenir)"""
        recent_data = sample_daily_data[-30:]

        with pytest.raises(RuntimeError):
            predictor.predict(recent_data)

    def test_predict_insufficient_data(self, predictor, sample_daily_data):
        """Yetersiz input verisi testi"""
        predictor.is_trained = True  # Mock trained state

        short_data = sample_daily_data[:10]

        with pytest.raises(ValueError):
            predictor.predict(short_data)


class TestTimeSeriesPrediction:
    """TimeSeriesPrediction dataclass testleri"""

    def test_prediction_dataclass(self):
        """Prediction dataclass testi"""
        prediction = TimeSeriesPrediction(
            forecast=[32.0, 33.0, 31.5, 32.5, 33.5, 32.0, 31.0],
            confidence_low=[30.0] * 7,
            confidence_high=[35.0] * 7,
            trend="stable",
            model_accuracy=0.05,
            input_days=30,
            forecast_days=7,
        )

        assert len(prediction.forecast) == 7
        assert prediction.trend == "stable"
        assert prediction.input_days == 30
        assert prediction.forecast_days == 7


class TestIntegration:
    """Entegrasyon testleri"""

    @pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
    def test_full_pipeline(self):
        """Tam pipeline testi"""
        from app.core.ml.time_series_predictor import TimeSeriesPredictor

        predictor = TimeSeriesPredictor()

        # Sentetik veri oluştur (90 gün)
        base_date = date.today() - timedelta(days=90)
        data = []

        for i in range(90):
            current_date = base_date + timedelta(days=i)
            # Haftalık pattern + trend + noise
            consumption = (
                32.0
                + np.sin(i / 7 * 2 * np.pi) * 2
                + i * 0.02
                + np.random.normal(0, 0.5)
            )

            data.append(
                {
                    "tarih": current_date,
                    "ort_tuketim": consumption,
                    "toplam_km": 500,
                    "ort_ton": 20,
                    "sefer_sayisi": 5,
                }
            )

        # Eğit
        result = predictor.train(data, epochs=10, batch_size=16)
        assert result["success"] is True

        # Tahmin
        prediction = predictor.predict(data[-30:], with_confidence=False)
        assert len(prediction.forecast) == 7

        # Değerler makul aralıkta olmalı
        for val in prediction.forecast:
            assert 20 < val < 50, f"Tahmin değeri ({val}) makul aralıkta değil"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
