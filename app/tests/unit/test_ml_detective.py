"""
Driver performance formula checks that stayed on the main backend after
the prediction_ml_service extraction (Task 5) -- the two EnsembleFuelPredictor
/TimeSeriesPredictor race-condition/padding tests moved to
v2/services/prediction_ml_service/tests/test_ml_detective.py.
"""

from v2.modules.driver.domain.performance_ml import DriverPerformanceML


def test_driver_performance_consistency_formula():
    ml = DriverPerformanceML()
    # Inconsistent driver (best 25, worst 45, avg 35)
    stats = {
        "en_iyi_tuketim": 25.0,
        "en_kotu_tuketim": 45.0,
        "ort_tuketim": 35.0,
        "toplam_sefer": 10,
    }
    features = ml.prepare_features([stats])[0]
    consistency_idx = ml.FEATURE_NAMES.index("tuketim_tutarliligi")
    val = features[consistency_idx]

    # abs(45-25)/35 = 20/35 approx 0.57
    assert 0.5 < val < 0.6
