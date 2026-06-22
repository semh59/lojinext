"""Tests for speed profile ML features added to EnsemblePredictor."""

from app.core.ml.ensemble_predictor import EnsembleFuelPredictor as EnsemblePredictor

SAMPLE_SEFER = {
    "ton": 20.0,
    "mesafe_km": 500.0,
    "ascent_m": 800.0,
    "descent_m": 750.0,
    "flat_distance_km": 350.0,
    "zorluk": "Normal",
    "arac_yasi": 5.0,
    "yas_faktoru": 1.0,
    "mevsim_faktor": 1.0,
    "sofor_katsayi": 1.0,
    "dorse_bos_agirlik": 6500.0,
    "dorse_lastik_sayisi": 6,
    "rota_detay": {
        "motorway": {"flat": 200.0, "up": 10.0, "down": 10.0},
        "trunk": {"flat": 80.0, "up": 5.0, "down": 5.0},
        "primary": {"flat": 50.0, "up": 8.0, "down": 7.0},
        "residential": {"flat": 15.0, "up": 2.0, "down": 1.0},
        "other": {"flat": 5.0, "up": 1.0, "down": 1.0},
        "ascent_m": 800.0,
        "descent_m": 750.0,
    },
}


def test_feature_count_matches_feature_names():
    """Feature matrix column count must equal len(FEATURE_NAMES)."""
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([SAMPLE_SEFER])
    assert features.shape[1] == len(EnsemblePredictor.FEATURE_NAMES), (
        f"Shape[1]={features.shape[1]} != len(FEATURE_NAMES)={len(EnsemblePredictor.FEATURE_NAMES)}"
    )


def test_speed_feature_names_present():
    """New speed features must appear in FEATURE_NAMES."""
    assert "expected_avg_speed" in EnsemblePredictor.FEATURE_NAMES
    assert "urban_speed_ratio" in EnsemblePredictor.FEATURE_NAMES
    assert "highway_speed_ratio" in EnsemblePredictor.FEATURE_NAMES


def test_expected_avg_speed_is_positive():
    """expected_avg_speed must be positive when route_analysis is present."""
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([SAMPLE_SEFER])
    idx = EnsemblePredictor.FEATURE_NAMES.index("expected_avg_speed")
    assert features[0, idx] > 0.0, (
        f"expected_avg_speed={features[0, idx]} should be > 0"
    )


def test_highway_speed_ratio_between_0_and_1():
    """highway_speed_ratio = motorway_ratio + trunk_ratio, capped at 1.0."""
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([SAMPLE_SEFER])
    idx = EnsemblePredictor.FEATURE_NAMES.index("highway_speed_ratio")
    assert 0.0 <= features[0, idx] <= 1.0


def test_empty_route_analysis_produces_zero_speed_features():
    """Without route_analysis, speed features must default to 0."""
    sefer_no_route = {**SAMPLE_SEFER, "rota_detay": {}}
    predictor = EnsemblePredictor()
    features = predictor.prepare_features([sefer_no_route])
    idx_speed = EnsemblePredictor.FEATURE_NAMES.index("expected_avg_speed")
    assert features[0, idx_speed] == 0.0
