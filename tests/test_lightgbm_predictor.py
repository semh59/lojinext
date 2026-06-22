"""
LightGBM Predictor Unit Tests
"""

import sys

import numpy as np
import pytest

sys.path.insert(0, ".")

from app.core.ml.lightgbm_predictor import (
    LIGHTGBM_AVAILABLE,
    LGBMPredictionResult,
    LightGBMFuelPredictor,
    is_lightgbm_available,
)


class TestLightGBMAvailability:
    """LightGBM kullanılabilirlik testleri"""

    def test_lightgbm_import(self):
        """LightGBM import kontrolü"""
        # Bu test ortamda LightGBM varsa True döner
        assert isinstance(LIGHTGBM_AVAILABLE, bool)

    def test_is_lightgbm_available_function(self):
        """is_lightgbm_available fonksiyon kontrolü"""
        result = is_lightgbm_available()
        assert isinstance(result, bool)
        assert result == LIGHTGBM_AVAILABLE


class TestLightGBMFuelPredictor:
    """LightGBMFuelPredictor sınıf testleri"""

    @pytest.fixture
    def predictor(self):
        """Test predictor instance"""
        return LightGBMFuelPredictor()

    @pytest.fixture
    def sample_seferler(self):
        """Test sefer verileri"""
        return [
            {
                "mesafe_km": 500,
                "ton": 20,
                "ascent_m": 1000,
                "descent_m": 800,
                "zorluk": "Normal",
                "arac_yasi": 3,
                "yas_faktoru": 1.02,
                "mevsim_faktor": 1.05,
                "sofor_katsayi": 0.98,
            },
            {
                "mesafe_km": 300,
                "ton": 15,
                "ascent_m": 500,
                "descent_m": 600,
                "zorluk": "Kolay",
                "arac_yasi": 2,
                "yas_faktoru": 1.01,
                "mevsim_faktor": 1.0,
                "sofor_katsayi": 1.0,
            },
            {
                "mesafe_km": 800,
                "ton": 25,
                "ascent_m": 2000,
                "descent_m": 1500,
                "zorluk": "Zor",
                "arac_yasi": 5,
                "yas_faktoru": 1.05,
                "mevsim_faktor": 1.1,
                "sofor_katsayi": 0.95,
            },
        ] * 5  # 15 sefer

    @pytest.fixture
    def sample_y(self, sample_seferler):
        """Test target values"""
        return np.array([32.5, 28.0, 38.0] * 5)

    def test_init(self, predictor):
        """Predictor başlatma testi"""
        assert predictor is not None
        assert predictor.is_trained is False
        assert len(predictor.FEATURE_NAMES) == 17

    def test_prepare_features_shape(self, predictor, sample_seferler):
        """Feature preparation shape testi"""
        X = predictor.prepare_features(sample_seferler)
        assert X.shape == (len(sample_seferler), len(predictor.FEATURE_NAMES))

    def test_prepare_features_values(self, predictor, sample_seferler):
        """Feature değerleri testi"""
        X = predictor.prepare_features(sample_seferler)

        # İlk sefer için kontroller
        assert X[0, 0] == 500  # mesafe_km
        assert X[0, 1] == 20  # ton
        assert X[0, 2] == 1000  # ascent_m
        assert X[0, 3] == 800  # descent_m

    def test_prepare_features_empty(self, predictor):
        """Boş sefer listesi testi"""
        X = predictor.prepare_features([])
        # Boş liste için 0 satır döner
        assert len(X) == 0 or X.shape[0] == 0

    @pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
    def test_fit_success(self, predictor, sample_seferler, sample_y):
        """Model eğitim başarı testi"""
        result = predictor.fit(sample_seferler, sample_y)

        assert result["success"] is True
        assert "train_r2" in result or "val_r2" in result
        assert "train_mae" in result or "val_mae" in result
        assert predictor.is_trained is True

    @pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
    def test_fit_insufficient_data(self, predictor):
        """Yetersiz veri testi"""
        seferler = [{"mesafe_km": 100, "ton": 10}]
        y = np.array([30.0])

        result = predictor.fit(seferler, y)

        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    @pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
    def test_predict_after_training(self, predictor, sample_seferler, sample_y):
        """Eğitim sonrası tahmin testi"""
        predictor.fit(sample_seferler, sample_y)

        test_sefer = sample_seferler[0]
        prediction = predictor.predict(test_sefer)

        assert isinstance(prediction, LGBMPredictionResult)
        assert prediction.prediction > 0
        # confidence_interval tuple olarak döner (low, high)
        assert (
            prediction.confidence_interval[0]
            < prediction.prediction
            < prediction.confidence_interval[1]
        )

    def test_predict_without_training(self, predictor, sample_seferler):
        """Eğitimsiz tahmin testi - RuntimeError beklenmeli"""
        test_sefer = sample_seferler[0]

        with pytest.raises(RuntimeError):
            predictor.predict(test_sefer)


class TestIntegration:
    """Entegrasyon testleri"""

    @pytest.mark.skipif(not LIGHTGBM_AVAILABLE, reason="LightGBM not installed")
    def test_full_pipeline(self):
        """Tam pipeline testi"""
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        predictor = LightGBMFuelPredictor()

        # Veri oluştur
        seferler = []
        y_values = []

        for i in range(20):
            mesafe = 300 + i * 50
            ton = 15 + i
            consumption = 28 + (ton - 15) * 0.5 + np.random.normal(0, 2)

            seferler.append(
                {
                    "mesafe_km": mesafe,
                    "ton": ton,
                    "ascent_m": 500 + i * 50,
                    "descent_m": 400 + i * 40,
                    "zorluk": ["Kolay", "Normal", "Zor"][i % 3],
                    "arac_yasi": 2 + i % 5,
                    "yas_faktoru": 1.0 + (i % 5) * 0.01,
                    "mevsim_faktor": 1.0,
                    "sofor_katsayi": 1.0,
                }
            )
            y_values.append(consumption)

        y = np.array(y_values)

        # Eğit
        result = predictor.fit(seferler, y)
        assert result["success"] is True

        # Tahmin
        prediction = predictor.predict(seferler[0])
        assert prediction.prediction > 0
        assert prediction.confidence_interval[0] < prediction.confidence_interval[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
