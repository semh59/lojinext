from unittest.mock import patch

from v2.modules.prediction_ml.infrastructure.ml_probe import MLProbe


def test_no_alert_below_100_predictions():
    probe = MLProbe()
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        for i in range(99):
            probe.record_prediction("m1", used_fallback=True)
        mock_emit.assert_not_called()


def test_alert_at_100_if_rate_above_80_pct():
    probe = MLProbe()
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        for i in range(100):
            probe.record_prediction("m1", used_fallback=True)  # 100% fallback
        mock_emit.assert_called_once()
        ev = mock_emit.call_args[0][0]
        assert ev.category == "high_fallback_rate"
        assert ev.metadata["model_id"] == "m1"


def test_no_alert_at_100_if_rate_below_80_pct():
    probe = MLProbe()
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        for i in range(100):
            probe.record_prediction("m1", used_fallback=(i < 79))  # 79%
        mock_emit.assert_not_called()


def test_get_stats_returns_correct_rate():
    probe = MLProbe()
    for i in range(10):
        probe.record_prediction("m1", used_fallback=(i < 5))
    stats = probe.get_stats("m1")
    assert stats["total_predictions"] == 10
    assert stats["fallback_count"] == 5
    assert stats["fallback_rate"] == 0.5


def test_model_load_failure_emits_critical():
    probe = MLProbe()
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        probe.record_model_load_failure("physics", exc=RuntimeError("file not found"))
        mock_emit.assert_called_once()
        ev = mock_emit.call_args[0][0]
        assert ev.severity.value == "critical"


def test_no_alert_at_exact_80_pct():
    """Threshold is >, not >=, so exactly 80% should NOT alert."""
    probe = MLProbe()
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        for i in range(100):
            probe.record_prediction("m1", used_fallback=(i < 80))  # exactly 80%
        mock_emit.assert_not_called()


def test_alert_fires_again_at_200_predictions():
    """Alert should re-fire at every _CHECK_EVERY_N_PREDICTIONS interval."""
    probe = MLProbe()
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        for i in range(200):
            probe.record_prediction("m1", used_fallback=True)
        assert mock_emit.call_count == 2  # fires at 100 and 200
