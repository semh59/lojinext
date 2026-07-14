import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root to path (d:/PROJECT/excel)
sys.path.insert(0, str(Path(__file__).parent.parent))

from v2.modules.fuel.domain.local_regression import LinearRegressionModel

# NOTE: the old YakitTahminService class (with its `self.model` constructor
# attribute) no longer exists — dalga 4 migration replaced it with free
# functions (v2/modules/fuel/domain/consumption_prediction.py) that create a
# local LinearRegressionModel per call, never a persistent `self.model`
# (that attribute was dead weight even before the migration — no method
# read it). The tests that asserted on `service.model` were testing that
# dead attribute, not real behavior, so they were dropped rather than
# ported.


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
