"""Coverage tests for app/core/ml/ensemble_strategy.py (46% → ≥75%)."""

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# DynamicWeightStrategy
# ---------------------------------------------------------------------------


class TestDynamicWeightStrategy:
    def _strategy(self):
        from app.core.ml.ensemble_strategy import DynamicWeightStrategy

        return DynamicWeightStrategy()

    def test_weights_sum_to_one_with_valid_r2(self):
        s = self._strategy()
        metrics = {
            "rf": {"r2": 0.8},
            "xgb": {"r2": 0.6},
            "lgb": {"r2": 0.5},
        }
        models = ["rf", "xgb", "lgb"]
        weights = s.calculate_weights(metrics, models)
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_all_models_get_weights(self):
        s = self._strategy()
        metrics = {"a": {"r2": 0.5}, "b": {"r2": 0.3}}
        weights = s.calculate_weights(metrics, ["a", "b"])
        assert set(weights.keys()) == {"a", "b"}

    def test_negative_r2_clamped_to_minimum(self):
        """Negative R² is replaced by 0.01 minimum baseline."""
        s = self._strategy()
        metrics = {"a": {"r2": -0.5}, "b": {"r2": 0.9}}
        weights = s.calculate_weights(metrics, ["a", "b"])
        assert weights["a"] > 0
        assert weights["b"] > weights["a"]

    def test_zero_r2_clamped_to_minimum(self):
        s = self._strategy()
        metrics = {"a": {"r2": 0.0}, "b": {"r2": 0.5}}
        weights = s.calculate_weights(metrics, ["a", "b"])
        assert weights["a"] > 0

    def test_model_missing_from_metrics_uses_baseline(self):
        """Model not in metrics dict gets baseline 0.01."""
        s = self._strategy()
        metrics = {"known": {"r2": 0.7}}
        weights = s.calculate_weights(metrics, ["known", "unknown"])
        assert "unknown" in weights
        assert weights["unknown"] > 0

    def test_model_missing_r2_key_uses_baseline(self):
        """Model in metrics but without 'r2' key gets baseline."""
        s = self._strategy()
        metrics = {"a": {"mse": 10.0}, "b": {"r2": 0.8}}
        weights = s.calculate_weights(metrics, ["a", "b"])
        assert "a" in weights
        assert weights["a"] > 0

    def test_single_model_gets_weight_one(self):
        s = self._strategy()
        metrics = {"rf": {"r2": 0.9}}
        weights = s.calculate_weights(metrics, ["rf"])
        assert abs(weights["rf"] - 1.0) < 1e-9

    def test_returns_dict(self):
        s = self._strategy()
        result = s.calculate_weights({}, [])
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# EqualWeightStrategy
# ---------------------------------------------------------------------------


class TestEqualWeightStrategy:
    def _strategy(self):
        from app.core.ml.ensemble_strategy import EqualWeightStrategy

        return EqualWeightStrategy()

    def test_equal_weights_for_two_models(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["a", "b"])
        assert abs(weights["a"] - 0.5) < 1e-9
        assert abs(weights["b"] - 0.5) < 1e-9

    def test_equal_weights_for_four_models(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["a", "b", "c", "d"])
        for v in weights.values():
            assert abs(v - 0.25) < 1e-9

    def test_sum_to_one(self):
        s = self._strategy()
        models = ["rf", "xgb", "lgb", "gb"]
        weights = s.calculate_weights({}, models)
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_empty_models_returns_empty_dict(self):
        s = self._strategy()
        weights = s.calculate_weights({}, [])
        assert weights == {}

    def test_metrics_ignored(self):
        """Metrics should not affect equal weighting."""
        s = self._strategy()
        metrics = {"a": {"r2": 0.99}, "b": {"r2": 0.01}}
        w1 = s.calculate_weights(metrics, ["a", "b"])
        w2 = s.calculate_weights({}, ["a", "b"])
        assert w1 == w2

    def test_single_model_gets_weight_one(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["only"])
        assert abs(weights["only"] - 1.0) < 1e-9

    def test_returns_dict(self):
        s = self._strategy()
        result = s.calculate_weights({}, ["x"])
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# PhysicsFirstStrategy
# ---------------------------------------------------------------------------


class TestPhysicsFirstStrategy:
    def _strategy(self):
        from app.core.ml.ensemble_strategy import PhysicsFirstStrategy

        return PhysicsFirstStrategy()

    def test_xgb_lgb_get_80_percent(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["xgb", "lgb", "rf", "gb"])
        # xgb and lgb share 0.8
        assert abs(weights["xgb"] - 0.4) < 1e-9
        assert abs(weights["lgb"] - 0.4) < 1e-9

    def test_others_share_20_percent(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["xgb", "lgb", "rf", "gb"])
        assert abs(weights["rf"] - 0.1) < 1e-9
        assert abs(weights["gb"] - 0.1) < 1e-9

    def test_only_xgb_gets_80_percent(self):
        """Single booster: 0.8 for xgb, 0.2 for others split."""
        s = self._strategy()
        weights = s.calculate_weights({}, ["xgb", "rf"])
        assert abs(weights["xgb"] - 0.8) < 1e-9
        assert abs(weights["rf"] - 0.2) < 1e-9

    def test_no_boosters_falls_back_to_equal(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["rf", "gb"])
        assert abs(weights["rf"] - 0.5) < 1e-9
        assert abs(weights["gb"] - 0.5) < 1e-9

    def test_empty_models_returns_empty_dict(self):
        s = self._strategy()
        weights = s.calculate_weights({}, [])
        assert weights == {}

    def test_only_boosters_no_others(self):
        """Only xgb + lgb, no 'other' models: still 0.8 total for boosters."""
        s = self._strategy()
        weights = s.calculate_weights({}, ["xgb", "lgb"])
        assert abs(weights["xgb"] - 0.4) < 1e-9
        assert abs(weights["lgb"] - 0.4) < 1e-9
        # No 'rf'/'gb' keys
        assert "rf" not in weights

    def test_metrics_not_used_in_physics_first(self):
        """PhysicsFirstStrategy ignores metrics."""
        s = self._strategy()
        w1 = s.calculate_weights({"rf": {"r2": 0.99}}, ["xgb", "rf"])
        w2 = s.calculate_weights({}, ["xgb", "rf"])
        assert w1 == w2

    def test_returns_dict(self):
        s = self._strategy()
        result = s.calculate_weights({}, ["xgb"])
        assert isinstance(result, dict)

    def test_single_booster_no_others(self):
        """Only one booster model present."""
        s = self._strategy()
        weights = s.calculate_weights({}, ["xgb"])
        assert abs(weights["xgb"] - 0.8) < 1e-9
        # No 'other' models, so total = 0.8 not 1.0 (by design)

    def test_lgb_alone_gets_80(self):
        s = self._strategy()
        weights = s.calculate_weights({}, ["lgb"])
        assert abs(weights["lgb"] - 0.8) < 1e-9


# ---------------------------------------------------------------------------
# Abstract base: EnsembleStrategy
# ---------------------------------------------------------------------------


class TestEnsembleStrategyABC:
    def test_cannot_instantiate_directly(self):
        from app.core.ml.ensemble_strategy import EnsembleStrategy

        with pytest.raises(TypeError):
            EnsembleStrategy()

    def test_concrete_strategies_are_subclasses(self):
        from app.core.ml.ensemble_strategy import (
            DynamicWeightStrategy,
            EnsembleStrategy,
            EqualWeightStrategy,
            PhysicsFirstStrategy,
        )

        for cls in [DynamicWeightStrategy, EqualWeightStrategy, PhysicsFirstStrategy]:
            assert issubclass(cls, EnsembleStrategy)
