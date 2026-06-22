"""
Extended coverage for app/core/ml/lightgbm_predictor.py.

Target: raise module coverage from ~37% toward ≥70%.

Covers:
  - LightGBMFuelPredictor init (with/without lightgbm)
  - prepare_features: all edge cases, rota_detay extraction, flat_km
  - fit: guards (insufficient data, lgb not available), success path (mocked lgb)
  - predict / predict_batch: not-trained guards, post-fit prediction
  - get_feature_importance
  - _calculate_checksum
  - save_model / load_model guards
  - LightGBMAnomalyClassifier: init, fit/predict guards, success path
  - is_lightgbm_available
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sefer(
    mesafe_km: float = 500.0,
    ton: float = 20.0,
    ascent_m: float = 800.0,
    descent_m: float = 700.0,
    zorluk: str = "Normal",
    **kwargs,
) -> Dict:
    base = dict(
        mesafe_km=mesafe_km,
        ton=ton,
        ascent_m=ascent_m,
        descent_m=descent_m,
        flat_distance_km=300.0,
        arac_yasi=5,
        yas_faktoru=1.0,
        mevsim_faktor=1.0,
        sofor_katsayi=1.0,
        zorluk=zorluk,
    )
    base.update(kwargs)
    return base


def _batch(n: int = 15, base: float = 32.0) -> List[Dict]:
    return [_make_sefer(mesafe_km=400 + i * 10, ton=18 + (i % 5)) for i in range(n)]


def _y_actual(n: int = 15, base: float = 32.0) -> np.ndarray:
    return np.array([base + (i % 3) * 0.5 for i in range(n)], dtype=np.float64)


# ---------------------------------------------------------------------------
# is_lightgbm_available
# ---------------------------------------------------------------------------


class TestIsLightGBMAvailable:
    def test_returns_bool(self):
        from app.core.ml.lightgbm_predictor import is_lightgbm_available

        result = is_lightgbm_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# LightGBMFuelPredictor — init
# ---------------------------------------------------------------------------


class TestLightGBMFuelPredictorInit:
    def test_default_init(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        assert p.is_trained is False
        assert p.model is None
        assert len(p.FEATURE_NAMES) > 0

    def test_custom_params_override_defaults(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor(params={"num_leaves": 63, "learning_rate": 0.1})
        assert p.params["num_leaves"] == 63
        assert p.params["learning_rate"] == 0.1
        # defaults still present unless overridden
        assert "objective" in p.params

    def test_feature_names_count(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        assert len(p.FEATURE_NAMES) == 17  # per source

    def test_zorluk_map(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        assert p.ZORLUK_MAP["Kolay"] == 0
        assert p.ZORLUK_MAP["Normal"] == 1
        assert p.ZORLUK_MAP["Zor"] == 2


# ---------------------------------------------------------------------------
# LightGBMFuelPredictor — prepare_features
# ---------------------------------------------------------------------------


class TestPrepareFeatures:
    def test_basic_shape(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features([_make_sefer()])
        assert X.shape == (1, len(p.FEATURE_NAMES))

    def test_batch_shape(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features(_batch(5))
        assert X.shape == (5, len(p.FEATURE_NAMES))

    def test_zero_mesafe_yuk_yogunlugu_is_zero(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features([_make_sefer(mesafe_km=0)])
        # yuk_yogunlugu at index 5 should be 0 (ton / 0 → 0)
        assert X[0, 5] == 0.0

    def test_zorluk_kolay(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features([_make_sefer(zorluk="Kolay")])
        assert X[0, 6] == 0  # ZORLUK_MAP["Kolay"] = 0

    def test_zorluk_zor(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features([_make_sefer(zorluk="Zor")])
        assert X[0, 6] == 2  # ZORLUK_MAP["Zor"] = 2

    def test_unknown_zorluk_defaults_to_normal(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features([_make_sefer(zorluk="BilinmeyenZorluk")])
        assert X[0, 6] == 1  # default = Normal = 1

    def test_rota_detay_route_analysis_extracted(self):
        """Route analysis embedded in rota_detay should populate ratios."""
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        sefer = _make_sefer(
            mesafe_km=400.0,
            rota_detay={
                "route_analysis": {
                    "motorway": {"flat": 300, "up": 0, "down": 0},
                    "residential": {"flat": 50, "up": 0, "down": 0},
                }
            },
        )
        X = p.prepare_features([sefer])
        motorway_ratio = X[0, 11]  # index 11 = motorway_ratio
        assert motorway_ratio > 0.0

    def test_none_optional_fields_default(self):
        """None values for optional numeric fields must default to 0/1.0."""
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        sefer = {"mesafe_km": 500, "ton": None, "ascent_m": None}
        X = p.prepare_features([sefer])
        assert X.shape == (1, len(p.FEATURE_NAMES))
        assert np.all(np.isfinite(X))

    def test_no_nan_in_features(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        X = p.prepare_features(_batch(10))
        assert not np.any(np.isnan(X))

    def test_net_elevation_derived(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        sefer = _make_sefer(ascent_m=1000, descent_m=600)
        X = p.prepare_features([sefer])
        net_elevation = X[0, 4]  # index 4 = net_elevation
        assert net_elevation == pytest.approx(400.0)


# ---------------------------------------------------------------------------
# LightGBMFuelPredictor — fit guards
# ---------------------------------------------------------------------------


class TestFitGuards:
    def test_no_lgb_returns_error(self):
        from app.core.ml import lightgbm_predictor

        original = lightgbm_predictor.LIGHTGBM_AVAILABLE
        try:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = False
            p = lightgbm_predictor.LightGBMFuelPredictor()
            result = p.fit(_batch(15), _y_actual(15))
            assert result["success"] is False
            assert "not available" in result["error"].lower()
        finally:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = original

    def test_insufficient_data_returns_error(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMFuelPredictor,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        p = LightGBMFuelPredictor()
        result = p.fit(_batch(5), _y_actual(5))
        assert result["success"] is False
        assert "Yetersiz" in result["error"]

    def test_fit_success_with_mocked_lgb(self):
        """Mock lgb.Dataset and lgb.train to test the full fit path.

        lgb.train is patched so the model's predict() returns arrays whose
        length matches the actual train/val splits computed from n=15 samples
        (validation_split=0.2 → n_val=3, n_train=12).
        """
        from app.core.ml import lightgbm_predictor

        if not lightgbm_predictor.LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        n = 15
        n_features = len(lightgbm_predictor.LightGBMFuelPredictor.FEATURE_NAMES)

        # model.predict(X) must return array matching X's row count
        def _predict(X, *args, **kwargs):
            return np.full(len(X), 32.0)

        mock_model = MagicMock()
        mock_model.predict.side_effect = _predict
        mock_model.feature_importance.return_value = np.ones(n_features)
        mock_model.best_iteration = 50

        with patch("app.core.ml.lightgbm_predictor.lgb") as mock_lgb:
            mock_lgb.Dataset.return_value = MagicMock()
            mock_lgb.early_stopping.return_value = MagicMock()
            mock_lgb.log_evaluation.return_value = MagicMock()
            mock_lgb.train.return_value = mock_model

            p = lightgbm_predictor.LightGBMFuelPredictor()
            seferler = _batch(n)
            y = _y_actual(n)
            result = p.fit(seferler, y)

        assert result["success"] is True
        assert p.is_trained is True


# ---------------------------------------------------------------------------
# LightGBMFuelPredictor — predict / predict_batch
# ---------------------------------------------------------------------------


class TestPredictGuards:
    def test_predict_raises_when_not_trained(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            p.predict(_make_sefer())

    def test_predict_batch_raises_when_not_trained(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            p.predict_batch(_batch(3))

    def test_predict_uses_validation_margin(self):
        """When prediction_interval_margin_ is set, confidence interval uses it."""
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMFuelPredictor,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        p = LightGBMFuelPredictor()
        p.is_trained = True
        p.prediction_interval_margin_ = 2.5

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([33.0])
        p.model = mock_model
        p.feature_importance_ = {"mesafe_km": 0.5}

        result = p.predict(_make_sefer())
        assert result.prediction == pytest.approx(33.0)
        low, high = result.confidence_interval
        assert high - low == pytest.approx(5.0, abs=0.1)

    def test_predict_fallback_margin_from_training_stats(self):
        """When prediction_interval_margin_ is None, uses training_stats.val_mae."""
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMFuelPredictor,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        p = LightGBMFuelPredictor()
        p.is_trained = True
        p.prediction_interval_margin_ = None
        p.training_stats = {"val_mae": 1.5}

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([32.0])
        p.model = mock_model
        p.feature_importance_ = {}

        result = p.predict(_make_sefer())
        low, high = result.confidence_interval
        assert high > low

    def test_predict_batch_returns_array(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMFuelPredictor,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        p = LightGBMFuelPredictor()
        p.is_trained = True

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([32.0, 33.0, 34.0])
        p.model = mock_model

        results = p.predict_batch(_batch(3))
        assert hasattr(results, "__len__")
        assert len(results) == 3


# ---------------------------------------------------------------------------
# LightGBMFuelPredictor — feature importance
# ---------------------------------------------------------------------------


class TestGetFeatureImportance:
    def test_returns_empty_dict_before_training(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        result = p.get_feature_importance()
        assert result == {}

    def test_returns_copy(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        p.feature_importance_ = {"ton": 0.4}
        copy1 = p.get_feature_importance()
        copy1["extra"] = 999
        # original must not be modified
        assert "extra" not in p.feature_importance_


# ---------------------------------------------------------------------------
# LightGBMFuelPredictor — save_model / load_model guards
# ---------------------------------------------------------------------------


class TestSaveLoadGuards:
    def test_save_raises_when_not_trained(self):
        from app.core.ml.lightgbm_predictor import LightGBMFuelPredictor

        p = LightGBMFuelPredictor()
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            p.save_model("/tmp/test_lgb.txt")

    def test_load_raises_when_no_lgb(self):
        from app.core.ml import lightgbm_predictor

        original = lightgbm_predictor.LIGHTGBM_AVAILABLE
        try:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = False
            p = lightgbm_predictor.LightGBMFuelPredictor()
            with pytest.raises(RuntimeError, match="not available"):
                p.load_model("/tmp/nonexistent.txt")
        finally:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = original

    def test_load_raises_file_not_found(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMFuelPredictor,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        p = LightGBMFuelPredictor()
        with pytest.raises(FileNotFoundError):
            p.load_model("/tmp/nonexistent_lgb_model.txt")

    def test_load_raises_if_too_large(self, tmp_path):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMFuelPredictor,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        p = LightGBMFuelPredictor()
        model_path = tmp_path / "big_model.txt"
        model_path.write_bytes(b"x" * 100)  # tiny file

        # Patch stat to fake oversized file
        with patch.object(
            Path, "stat", return_value=MagicMock(st_size=200 * 1024 * 1024)
        ):
            with pytest.raises(RuntimeError, match="büyük"):
                p.load_model(str(model_path))


# ---------------------------------------------------------------------------
# LightGBMAnomalyClassifier
# ---------------------------------------------------------------------------


class TestAnomalyClassifier:
    def test_init_without_lgb(self):
        from app.core.ml import lightgbm_predictor

        original = lightgbm_predictor.LIGHTGBM_AVAILABLE
        try:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = False
            clf = lightgbm_predictor.LightGBMAnomalyClassifier()
            assert clf.model is None
        finally:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = original

    def test_fit_without_lgb_returns_error(self):
        from app.core.ml import lightgbm_predictor

        original = lightgbm_predictor.LIGHTGBM_AVAILABLE
        try:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = False
            clf = lightgbm_predictor.LightGBMAnomalyClassifier()
            X = np.random.rand(10, 5)
            result = clf.fit(X, ["normal"] * 10)
            assert result["success"] is False
        finally:
            lightgbm_predictor.LIGHTGBM_AVAILABLE = original

    def test_predict_raises_when_not_trained(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMAnomalyClassifier,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        clf = LightGBMAnomalyClassifier()
        X = np.random.rand(5, 5)
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            clf.predict(X)

    def test_predict_proba_raises_when_not_trained(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMAnomalyClassifier,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        clf = LightGBMAnomalyClassifier()
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            clf.predict_proba(np.random.rand(3, 5))

    def test_severity_map_keys(self):
        from app.core.ml.lightgbm_predictor import LightGBMAnomalyClassifier

        clf = LightGBMAnomalyClassifier()
        for severity in ("normal", "low", "medium", "high", "critical"):
            assert severity in clf.SEVERITY_MAP

    def test_reverse_map_coverage(self):
        from app.core.ml.lightgbm_predictor import LightGBMAnomalyClassifier

        clf = LightGBMAnomalyClassifier()
        for i in range(5):
            assert i in clf.REVERSE_MAP

    def test_fit_success_with_mocked_lgb(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMAnomalyClassifier,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        clf = LightGBMAnomalyClassifier()
        X = np.random.rand(20, 5)
        labels = (
            ["normal"] * 10
            + ["low"] * 5
            + ["medium"] * 3
            + ["high"] * 1
            + ["critical"] * 1
        )

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0] * 20)
        clf.model = mock_model

        result = clf.fit(X, labels)
        assert result["success"] is True
        assert "accuracy" in result

    def test_predict_reverses_map(self):
        from app.core.ml.lightgbm_predictor import (
            LIGHTGBM_AVAILABLE,
            LightGBMAnomalyClassifier,
        )

        if not LIGHTGBM_AVAILABLE:
            pytest.skip("LightGBM not installed")

        clf = LightGBMAnomalyClassifier()
        clf.is_trained = True

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0, 1, 2])
        clf.model = mock_model

        predictions = clf.predict(np.random.rand(3, 5))
        assert predictions == ["normal", "low", "medium"]


# ---------------------------------------------------------------------------
# LGBMPredictionResult dataclass
# ---------------------------------------------------------------------------


class TestLGBMPredictionResult:
    def test_fields(self):
        from app.core.ml.lightgbm_predictor import LGBMPredictionResult

        r = LGBMPredictionResult(
            prediction=33.5,
            feature_importance={"ton": 0.4, "mesafe_km": 0.3},
            confidence_interval=(31.0, 36.0),
        )
        assert r.prediction == 33.5
        assert r.confidence_interval[1] > r.confidence_interval[0]
        assert "ton" in r.feature_importance
