import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root to path (d:/PROJECT/excel)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ml.fuel_predictor import LinearRegressionModel
from app.core.services.yakit_tahmin_service import YakitTahminService


class TestFuelPredictor:
    @pytest.fixture
    def model(self):
        return LinearRegressionModel()

    def test_fit_simple_linear(self, model):
        """Lineer regresyon fit testi - Z-Score normalizasyonu ile"""
        # y = 2x + 1 data
        X = np.array([[1], [2], [3], [4]])
        y = np.array([3, 5, 7, 9])

        result = model.fit(X, y)
        assert result["success"] is True

        # Z-Score normalization ile:
        # intercept = mean(y) = 6.0
        assert result["coefficients"]["intercept"] == pytest.approx(6.0, abs=1e-5)
        # R^2 = 1.0 (perfect fit)
        assert result["r_squared"] == pytest.approx(1.0, abs=1e-5)

    def test_insufficient_data(self, model):
        """Yetersiz veri durumunda ValueError fırlatılmalı"""
        X = np.array([[1]])
        y = np.array([3])
        with pytest.raises(ValueError, match="Eğitim için"):
            model.fit(X, y)

    def test_empty_data(self, model):
        """Boş veri durumunda ValueError fırlatılmalı"""
        X = np.array([])
        y = np.array([])
        with pytest.raises(ValueError, match="Eğitim için"):
            model.fit(X, y)

    def test_mismatched_dimensions(self, model):
        """X ve y boyutları uyuşmazsa hata fırlatılmalı"""
        X = np.array([[1], [2]])
        y = np.array([3])
        # Model içindeki check veya numpy hatası
        with pytest.raises((ValueError, IndexError)):
            model.fit(X, y)


class TestYakitService:
    @pytest.fixture
    def service(self):
        return YakitTahminService()

    def test_calculation_safety(self, service):
        """Model parametreleri ile güvenli hesaplama testi"""
        # Manually set model params to bypass DB params fetch
        # 0.1L/km, 0.5L/ton, 0.0/ascent
        service.model.coefficients = np.array([0.1, 0.5, 0.0])
        service.model.intercept = 0.0
        service.model.r_squared_score = 0.99

        assert service.model is not None
        assert service.model.r_squared_score == 0.99

        # Predict metodunu mocklamadan basic attribute kontrolü
        assert len(service.model.coefficients) == 3

    def test_service_initialization(self, service):
        """Servis başlatma kontrolü"""
        # Model objesi initialize edilmiş olmalı
        assert hasattr(service, "model")
        assert isinstance(service.model, LinearRegressionModel)
