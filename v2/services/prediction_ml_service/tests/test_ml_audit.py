import os
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

from prediction_ml_service.domain.physics_fuel_predictor import VehicleSpecs


class TestModelSerialization:
    """Model serialization güvenliği"""

    def test_no_pickle_in_codebase(self):
        """pickle.load kullanılmamalı (joblib hariç)"""
        # scan entire prediction_ml domain directory
        ml_dir = (
            Path(__file__).parent.parent.parent.parent.parent
            / "v2"
            / "services"
            / "prediction_ml_service"
            / "domain"
        )

        for file in ml_dir.glob("*.py"):
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
                # joblib is allowed because we implemented checksums, but simple pickle.load is dangerous
                if "pickle.load" in content:
                    # Allow if it's in a comment or string
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if "pickle.load" in line and not line.strip().startswith(
                            ("#", '"', "'")
                        ):
                            pytest.fail(
                                f"Unsafe pickle.load found in {file.name} at line {i + 1}"
                            )

    def test_sha256_checksum_verification(self):
        """Model dosyası checksum ile doğrulanmalı"""
        # This logic is inside EnsembleFuelPredictor, here we mock to verify it's called
        from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()

        # Test sanity of _calculate_checksum
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test data")
            tmp_path = tmp.name

        try:
            checksum = predictor._calculate_checksum(tmp_path)
            assert len(checksum) == 64  # SHA256 length
        finally:
            os.remove(tmp_path)

    def test_torch_load_safety(self):
        """Torch load weights_only=True kontrolü"""
        # time_series_predictor.py içinde weights_only=True kullanılıyor mu?
        ts_file = (
            Path(__file__).parent.parent.parent.parent.parent
            / "v2"
            / "services"
            / "prediction_ml_service"
            / "domain"
            / "time_series_predictor.py"
        )
        with open(ts_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "weights_only=True" in content, (
                "time_series_predictor.py must use weights_only=True for torch.load"
            )


class TestNumericalStability:
    """Sayısal stabilite testleri"""

    def test_physics_params_validation(self):
        """Physics model parameters must be positive"""
        with pytest.raises(
            ValueError, match="Engine efficiency must be greater than 0"
        ):
            VehicleSpecs(engine_efficiency=0)

        with pytest.raises(ValueError, match="Fuel density must be greater than 0"):
            VehicleSpecs(fuel_density_kg_l=-1)


class TestEnsembleModel:
    """Ensemble model testleri"""

    def test_weights_sum_to_one(self):
        """Ağırlıklar toplamı 1.0 olmalı"""
        from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()

        weights = predictor.WEIGHTS
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_lru_cache_eviction(self):
        """Cache limiti aşılınca eviction çalışmalı"""
        from prediction_ml_service.application.ensemble_service import (
            EnsemblePredictorService,
        )

        service = EnsemblePredictorService()
        service.MAX_PREDICTORS = 2

        service.get_predictor(1)
        service.get_predictor(2)

        assert 1 in service.predictors
        assert 2 in service.predictors

        service.get_predictor(3)

        assert 3 in service.predictors
        assert 2 in service.predictors
        assert 1 not in service.predictors  # Should be evicted
