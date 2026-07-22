from unittest.mock import patch

from v2.modules.platform_infra.monitoring.security_probe import BruteForceDetector


def test_brute_force_not_triggered_below_threshold():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            detector.record("1.2.3.4", 401)
        mock_emit.assert_not_called()


def test_brute_force_triggered_at_threshold():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(10):
            detector.record("1.2.3.4", 401)
        mock_emit.assert_called_once()


def test_brute_force_ignores_non_401():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(20):
            detector.record("1.2.3.4", 200)
        mock_emit.assert_not_called()


def test_brute_force_different_ips_independent():
    detector = BruteForceDetector()
    with patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            detector.record("1.1.1.1", 401)
            detector.record("2.2.2.2", 401)
        mock_emit.assert_not_called()
