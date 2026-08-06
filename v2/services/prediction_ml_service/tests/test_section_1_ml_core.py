"""
Split off app/tests/sections/test_section_1_backend_core.py (Task 5,
2026-08-04): TestEnsemblePredictor, TestEnsemblePredictorSecurity,
TestTimeSeriesService, and two individual test methods
(test_ensemble_predictor_memory_guard, test_empty_strings_and_none_values)
all exercised code that only lives in this service's own package now
(domain.ensemble_core, application.ensemble_service,
application.time_series_service) -- moved here whole, mechanical import
path fix only, no behavioral changes.
"""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

# =============================================================================
# TestEnsemblePredictor
# =============================================================================


class TestEnsemblePredictor:
    """Ensemble (hybrid) prediction model tests."""

    @pytest.fixture
    def predictor(self):
        from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

        return EnsembleFuelPredictor()

    @pytest.fixture
    def sample_seferler(self):
        """Sample trip list for training."""
        return [
            {
                "mesafe_km": 450,
                "ton": 20.0,
                "ascent_m": 500,
                "descent_m": 300,
                "sofor_score": 0.95,
                "tuketim": 34.5,
            },
            {
                "mesafe_km": 300,
                "ton": 15.0,
                "ascent_m": 200,
                "descent_m": 250,
                "sofor_score": 0.90,
                "tuketim": 32.0,
            },
            {
                "mesafe_km": 600,
                "ton": 25.0,
                "ascent_m": 800,
                "descent_m": 400,
                "sofor_score": 1.0,
                "tuketim": 38.0,
            },
            {
                "mesafe_km": 200,
                "ton": 10.0,
                "ascent_m": 100,
                "descent_m": 150,
                "sofor_score": 0.85,
                "tuketim": 30.5,
            },
            {
                "mesafe_km": 500,
                "ton": 22.0,
                "ascent_m": 600,
                "descent_m": 350,
                "sofor_score": 0.92,
                "tuketim": 35.8,
            },
        ] * 10  # multiply for 50 records

    def test_prepare_features_structure(self, predictor, sample_seferler):
        """Feature preparation -- structure check."""
        features = predictor.prepare_features(sample_seferler)

        assert features is not None
        assert isinstance(features, np.ndarray)
        assert len(features) == len(sample_seferler)

    def test_predict_without_training_uses_physics(self, predictor):
        """Prediction without training -- uses the physics model."""
        sefer = {
            "mesafe_km": 450,
            "ton": 20.0,
            "ascent_m": 500,
            "descent_m": 300,
            "sofor_score": 0.95,
        }

        result = predictor.predict(sefer)

        assert result is not None
        assert hasattr(result, "tahmin_l_100km")
        assert result.tahmin_l_100km > 0

        # Physics model should dominate (no training)
        assert result.physics_weight > 0

    def test_prediction_result_structure(self, predictor):
        """Prediction result structure check."""
        sefer = {
            "mesafe_km": 450,
            "ton": 20.0,
            "ascent_m": 500,
            "descent_m": 300,
            "sofor_score": 0.95,
        }

        result = predictor.predict(sefer)

        # Required fields must be present
        assert hasattr(result, "tahmin_l_100km")
        assert hasattr(result, "physics_only")
        assert hasattr(result, "ml_correction")
        assert hasattr(result, "confidence_low")
        assert hasattr(result, "confidence_high")
        assert hasattr(result, "physics_weight")
        assert hasattr(result, "features_used")

    def test_confidence_interval_valid(self, predictor):
        """Confidence interval validity."""
        sefer = {
            "mesafe_km": 450,
            "ton": 20.0,
            "ascent_m": 500,
            "descent_m": 300,
            "sofor_score": 0.95,
        }

        result = predictor.predict(sefer)

        # Confidence interval: low <= prediction <= high
        assert result.confidence_low <= result.tahmin_l_100km
        assert result.tahmin_l_100km <= result.confidence_high

    def test_weights_sum_to_one(self, predictor):
        """Model weights must sum to 1."""
        weights = predictor.WEIGHTS

        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001


# =============================================================================
# TestEnsemblePredictorSecurity
# =============================================================================


class TestEnsemblePredictorSecurity:
    """Ensemble predictor security tests."""

    @pytest.fixture
    def predictor(self):
        from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

        return EnsembleFuelPredictor()

    def test_save_load_model_integrity(self, predictor, tmp_path):
        """Save/load model integrity check."""
        # Build a simple model (simulating training)
        predictor.is_trained = True
        predictor._physics_weight = 0.2

        filepath = str(tmp_path / "test_model")

        # Note: an untrained model should raise here for a real test the
        # model would need to be trained first.
        try:
            predictor.save_model(filepath)

            # Load with a new instance
            from prediction_ml_service.domain.ensemble_core import (
                EnsembleFuelPredictor,
            )

            new_predictor = EnsembleFuelPredictor()
            new_predictor.load_model(filepath)

            # Values must match
            assert new_predictor._physics_weight == predictor._physics_weight
        except Exception:
            # An error is expected if the model was never trained
            pass

    def test_model_tampering_detection(self, predictor, tmp_path):
        """Model tampering detection: a checksum mismatch on load must raise."""
        import hashlib
        import json

        import joblib
        from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

        base_path = tmp_path / "model_tamper"
        sklearn_file = tmp_path / "model_tamper_sklearn.joblib"
        meta_file = tmp_path / "model_tamper_meta.json"

        # Create a minimal valid sklearn joblib file
        joblib.dump(
            {
                "gb_model": None,
                "rf_model": None,
                "xgb_model": None,
                "lgb_model": None,
                "scaler": None,
            },
            str(sklearn_file),
        )

        # Compute checksum of the valid file
        sha256 = hashlib.sha256()
        with open(str(sklearn_file), "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                sha256.update(block)
        checksum = sha256.hexdigest()

        # Write metadata with valid checksum
        meta = {
            "physics_weight": 0.8,
            "training_stats": {},
            "is_trained": True,
            "last_updated": "2025-01-01",
            "sklearn_checksum": checksum,
            "model_weights": {
                "physics": 0.8,
                "lightgbm": 0.05,
                "xgboost": 0.05,
                "gradient_boosting": 0.05,
                "random_forest": 0.05,
            },
        }
        with open(str(meta_file), "w", encoding="utf-8") as f:
            json.dump(meta, f)

        # Corrupt the sklearn file after recording the checksum
        with open(str(sklearn_file), "ab") as f:
            f.write(b"\xff\xfe\xfd")

        # Loading a corrupted file must raise SecurityError (checksum mismatch)
        tampered = EnsembleFuelPredictor()
        with pytest.raises(Exception):
            tampered.load_model(str(base_path) + ".pkl")


# =============================================================================
# TestTimeSeriesService
# =============================================================================


class TestTimeSeriesService:
    """Time-series service tests."""

    @pytest.fixture
    def ts_service(self):
        from prediction_ml_service.application.time_series_service import (
            get_time_series_service,
        )

        return get_time_series_service()

    async def test_predict_weekly_no_model(self, ts_service):
        """Prediction with no model trained -- error or fallback."""
        result = await ts_service.predict_weekly(arac_id=None)

        # If there's no model: error message or an empty-ish result
        assert "error" in result or not result.get("success") or "forecast" in result

    async def test_get_trend_analysis(self, ts_service):
        """Trend analysis."""
        # Mock get_daily_summary (correct format: a list of dicts)
        with patch.object(
            ts_service, "get_daily_summary", new_callable=AsyncMock
        ) as mock:
            mock.return_value = [
                {
                    "tarih": "2024-01-01",
                    "ort_tuketim": 32.0,
                    "toplam_km": 100,
                    "ort_ton": 10,
                    "sefer_sayisi": 5,
                },
                {
                    "tarih": "2024-01-02",
                    "ort_tuketim": 32.5,
                    "toplam_km": 110,
                    "ort_ton": 11,
                    "sefer_sayisi": 6,
                },
                {
                    "tarih": "2024-01-03",
                    "ort_tuketim": 33.0,
                    "toplam_km": 120,
                    "ort_ton": 12,
                    "sefer_sayisi": 5,
                },
                {
                    "tarih": "2024-01-04",
                    "ort_tuketim": 33.5,
                    "toplam_km": 115,
                    "ort_ton": 11,
                    "sefer_sayisi": 6,
                },
                {
                    "tarih": "2024-01-05",
                    "ort_tuketim": 34.0,
                    "toplam_km": 130,
                    "ort_ton": 13,
                    "sefer_sayisi": 7,
                },
                {
                    "tarih": "2024-01-06",
                    "ort_tuketim": 34.5,
                    "toplam_km": 125,
                    "ort_ton": 12,
                    "sefer_sayisi": 5,
                },
                {
                    "tarih": "2024-01-07",
                    "ort_tuketim": 35.0,
                    "toplam_km": 140,
                    "ort_ton": 14,
                    "sefer_sayisi": 8,
                },
            ]

            result = await ts_service.get_trend_analysis(arac_id=None, days=30)

            assert "success" in result or "trend" in result

    def test_model_status(self, ts_service):
        """Model status info."""
        status = ts_service.get_model_status()

        assert isinstance(status, dict)
        assert "trained" in status or "is_trained" in status or "available" in status


# =============================================================================
# Individual methods split out of TestPerformance / TestEdgeCases
# =============================================================================


def test_ensemble_predictor_memory_guard():
    """Ensemble predictor memory guard."""
    from prediction_ml_service.application.ensemble_service import (
        EnsemblePredictorService,
    )

    service = EnsemblePredictorService()

    # Check there's a MAX_PREDICTORS limit
    assert hasattr(service, "MAX_PREDICTORS")
    assert service.MAX_PREDICTORS > 0
    assert service.MAX_PREDICTORS <= 1000  # reasonable limit


def test_empty_strings_and_none_values():
    """Empty-string and None-value handling."""
    from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

    predictor = EnsembleFuelPredictor()

    # Trip with None values
    sefer_with_none = {
        "mesafe_km": None,
        "ton": None,
        "ascent_m": None,
        "descent_m": None,
        "sofor_score": None,
    }

    # Should be handled gracefully
    try:
        predictor.predict(sefer_with_none)
    except (TypeError, ValueError, KeyError):
        pass  # Expected behavior
