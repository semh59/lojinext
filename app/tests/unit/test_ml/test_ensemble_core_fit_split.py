import math

import pytest

from v2.modules.prediction_ml.domain.ensemble_core import EnsembleFuelPredictor

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

    All ensemble sub-models (`GradientBoostingRegressor`, `RandomForestRegressor`,
    `XGBRegressor`, `LGBMRegressor`) are constructed with `random_state=42`
    in `EnsembleFuelPredictor.__init__`, and this dataset has no random
    component of its own, so `fit()` is bit-for-bit deterministic across
    runs (verified locally: two consecutive `fit()` calls on the same
    input produced identical `ensemble_r2`/`mae`/`model_weights` to full
    float precision). `pytest.approx(rel=...)` is still used below as a
    safety margin against float/BLAS non-determinism across different
    machines/library versions (not because this run is expected to vary).

    `ensemble_r2` is pinned with a tight `rel=1e-4` tolerance rather than
    a loose one: it was empirically confirmed (by temporarily swapping
    `weights["gb"]`/`weights["rf"]` in the prediction loop this test
    covers) that a real mistyped-weight-key bug only shifts `ensemble_r2`
    by ~0.04% for this GB/RF-similar-weight dataset — a loose `rel=0.05`
    tolerance would silently swallow that regression, defeating the
    point of this test. `mae` keeps a looser tolerance since it is
    already rounded to 2 decimals in the response and is not the
    sensitive signal here.
    """
    predictor = EnsembleFuelPredictor()
    result = predictor.fit(_make_learnable_seferler(70))

    assert result["success"] is True
    # Proves the ML-weighted path actually engaged, not the physics=1.0
    # fallback (which the old vacuous test could not distinguish from).
    assert result["model_weights"]["physics"] < 1.0
    assert result["model_weights"]["physics"] == pytest.approx(0.0999, rel=0.01)
    assert result["ensemble_r2"] == pytest.approx(0.7652, rel=1e-4)
    assert result["measurements"]["mae"] == pytest.approx(3.47, rel=0.05)
