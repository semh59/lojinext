import math
from unittest import mock

import pytest
from prediction_ml_service.domain.ensemble_core import EnsembleFuelPredictor

pytestmark = pytest.mark.unit


def _make_seferler(n=20):
    return [
        {
            "tuketim": 30.0 + (i % 5),
            "tarih": f"2026-0{1 + i % 6}-15",
            "mesafe_km": 200.0 + i * 10,
            "ton": 18.0,
        }
        for i in range(n)
    ]


def test_fit_returns_success_shape_before_and_after_split():
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_seferler(20))

    assert result["success"] is True
    assert "sample_count" in result
    assert "ensemble_r2" in result
    assert "measurements" in result
    assert set(result["measurements"].keys()) == {"mae", "rmse", "mape", "physics_mae"}
    assert "metrics" in result
    assert "feature_importance" in result
    assert "model_weights" in result
    assert "is_honest_test" in result
    assert predictor.is_trained is True


def test_fit_insufficient_data_returns_error():
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_seferler(3))

    assert result["success"] is False
    assert "Yetersiz veri" in result["error"]


def _make_learnable_seferler(n=70):
    """Dataset with a genuinely learnable ton/ascent-derived signal.

    Unlike `_make_seferler` above (flat `30.0 + (i % 5)` pattern with no
    real relationship to `mesafe_km`/`ton`), this builds `tuketim` from a
    nonlinear combination of `ton`, `mesafe_km` and `ascent_m` that the
    physics baseline does not fully capture (weight-squared term +
    oscillating component). This drives `ml_total_r2 > 0` in
    `_compute_ensemble_weights`, so `physics_weight` collapses away from
    the 1.0 fallback and the weighted-prediction loop in
    `_evaluate_and_build_stats` (the code moved out of `fit()` in the
    Task 3 split) actually executes on every model branch.
    """
    rows = []
    for i in range(n):
        mesafe = 100.0 + (i % 12) * 40.0
        ton = 5.0 + (i % 10) * 2.0
        ascent = 50.0 + (i % 7) * 80.0
        descent = 40.0 + (i % 5) * 60.0
        signal = (
            0.04 * ton * (ascent / 100.0) + 3.0 * math.sin(i * 0.45) + 0.03 * (ton**2)
        )
        tuketim = 28.0 + 0.08 * mesafe / 10 + 0.4 * ton + signal
        rows.append(
            {
                "tuketim": round(tuketim, 2),
                "tarih": f"2026-0{1 + i % 6}-{1 + (i % 27):02d}",
                "mesafe_km": mesafe,
                "ton": ton,
                "ascent_m": ascent,
                "descent_m": descent,
                "zorluk": "Normal",
            }
        )
    return rows


def test_fit_weighted_prediction_loop_executes_with_learnable_signal():
    """Characterization test that actually exercises the weighted-sum loop.

    `test_fit_returns_success_shape_before_and_after_split` above only
    checks key presence — with its flat/no-signal dataset, all ML models
    score R2<=0, so `_compute_ensemble_weights` falls back to
    `physics=1.0` and the `weights["gb"]`/`weights["rf"]`/
    `weights["xgboost"]`/`weights["lightgbm"]` lines in
    `_evaluate_and_build_stats` never run. This test uses a dataset with a
    real learnable pattern so `ml_total_r2 > 0`, driving `physics_weight`
    well below 1.0 and exercising every weighted-prediction branch.
    """
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_learnable_seferler(70))

    assert result["success"] is True
    # Proves the ML-weighted path actually engaged, not the physics=1.0
    # fallback (which the old vacuous test could not distinguish from).
    assert result["model_weights"]["physics"] < 1.0
    assert result["model_weights"]["physics"] == pytest.approx(0.0999, rel=0.01)
    # ensemble_r2/mae are NOT pinned to a historical constant here -- see
    # test_fit_weighted_prediction_loop_is_regression_sensitive_to_weight_key_swap
    # below for why (this repo's app/requirements.txt leaves
    # xgboost/lightgbm/scikit-learn version-unpinned, so a fresh
    # `pip install` can and does compute a measurably different exact
    # float across independent CI runs -- observed live: 0.7652, then
    # 0.7661, then 0.7693 across three real installs on 2026-08-05, a
    # ~0.5% spread -- 13x wider than the ~0.04% shift the real
    # mistyped-weight-key bug this dataset was built to catch actually
    # produces, so no fixed tolerance can both survive that drift and
    # still catch the regression). A broad sanity range is enough here;
    # the dedicated test below verifies regression-sensitivity within a
    # single run instead, immune to cross-install drift.
    assert 0.5 < result["ensemble_r2"] < 0.95
    assert 1.0 < result["measurements"]["mae"] < 8.0


def test_fit_weighted_prediction_loop_is_regression_sensitive_to_weight_key_swap():
    """Same-run regression guard for the weighted-prediction loop in
    `_evaluate_and_build_stats` (the code moved out of `fit()` in the
    Task 3 split): a mistyped weight key (e.g. `weights["rf"]` used where
    `weights["gb"]` was meant, or vice versa) must produce a measurably
    different `ensemble_r2` than the correct computation.

    Deliberately does NOT compare against a hardcoded historical
    `ensemble_r2` value (see the previous test's docstring for why that's
    not viable with this repo's unpinned transitive ML deps) -- instead
    runs fit() twice in the SAME test execution (same installed library
    versions either way, so any deterministic-inputs assumption failures
    or version drift affect both runs identically and cancel out of the
    comparison), the second time with `_compute_ensemble_weights` swapping
    the "gb"/"rf" keys of its returned dict right before
    `_evaluate_and_build_stats` reads `weights["gb"]`/`weights["rf"]` in
    the weighted-sum loop -- reproducing the exact same class of bug this
    test's ancestor was written to catch, without needing to touch
    `ensemble_core.py`'s source.
    """
    correct_predictor = EnsembleFuelPredictor()
    correct_result = correct_predictor.fit(_make_learnable_seferler(70))
    assert correct_result["success"] is True
    assert correct_result["model_weights"]["physics"] < 1.0

    original_compute_weights = EnsembleFuelPredictor._compute_ensemble_weights

    def _compute_weights_with_gb_rf_swapped(self, model_scores):
        weights = original_compute_weights(self, model_scores)
        weights["gb"], weights["rf"] = weights["rf"], weights["gb"]
        self.weights = weights
        return weights

    buggy_predictor = EnsembleFuelPredictor()
    with mock.patch.object(
        EnsembleFuelPredictor,
        "_compute_ensemble_weights",
        _compute_weights_with_gb_rf_swapped,
    ):
        buggy_result = buggy_predictor.fit(_make_learnable_seferler(70))

    assert buggy_result["success"] is True
    assert buggy_result["ensemble_r2"] != pytest.approx(
        correct_result["ensemble_r2"], abs=1e-6
    ), "Swapping weights['gb']/weights['rf'] should measurably change ensemble_r2"
