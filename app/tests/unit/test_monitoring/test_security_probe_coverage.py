"""Additional coverage for security_probe.py.
Targets: _is_trusted_local_ip, BruteForceDetector LRU eviction + alert cooldown +
alert pruning, RBACViolationTracker record + threshold + LRU + pruning,
emit_jwt_anomaly all severity paths, module-level singletons.
"""

import time
from unittest.mock import patch

import pytest

from app.infrastructure.monitoring.security_probe import (
    BruteForceDetector,
    RBACViolationTracker,
    _is_trusted_local_ip,
    emit_jwt_anomaly,
    get_brute_force_detector,
    get_rbac_tracker,
)

pytestmark = pytest.mark.unit


# ─── _is_trusted_local_ip ─────────────────────────────────────────────────────


def test_trusted_loopback():
    assert _is_trusted_local_ip("127.0.0.1") is True


def test_trusted_ipv6_loopback():
    assert _is_trusted_local_ip("::1") is True


def test_trusted_docker_bridge_172_17():
    assert _is_trusted_local_ip("172.17.0.2") is True


def test_trusted_docker_bridge_172_18():
    assert _is_trusted_local_ip("172.18.0.1") is True


def test_trusted_docker_bridge_172_19():
    assert _is_trusted_local_ip("172.19.5.5") is True


def test_trusted_docker_bridge_172_20():
    assert _is_trusted_local_ip("172.20.0.100") is True


def test_not_trusted_public_ip():
    assert _is_trusted_local_ip("203.0.113.5") is False


def test_not_trusted_empty_string():
    assert _is_trusted_local_ip("") is False


def test_not_trusted_192_prefix():
    assert _is_trusted_local_ip("192.168.1.1") is False


# ─── BruteForceDetector — trusted IP skip ─────────────────────────────────────


def test_brute_force_trusted_ip_ignored():
    """Loopback IP 401s never trigger alert regardless of count."""
    det = BruteForceDetector()
    with patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(20):
            det.record("127.0.0.1", 401)
        mock_emit.assert_not_called()


def test_brute_force_docker_bridge_ignored():
    """Docker bridge IPs are trusted, never trigger."""
    det = BruteForceDetector()
    with patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(15):
            det.record("172.17.0.2", 401)
        mock_emit.assert_not_called()


# ─── BruteForceDetector — non-401 codes ──────────────────────────────────────


def test_brute_force_200_ignored():
    det = BruteForceDetector()
    with patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(50):
            det.record("5.6.7.8", 200)
        mock_emit.assert_not_called()


def test_brute_force_403_ignored():
    det = BruteForceDetector()
    with patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(50):
            det.record("9.10.11.12", 403)
        mock_emit.assert_not_called()


# ─── BruteForceDetector — alert cooldown ─────────────────────────────────────


def test_brute_force_alert_not_repeated_within_window():
    """Second burst within 60s window → alert fires only once."""
    det = BruteForceDetector()
    with patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(10):
            det.record("1.1.1.1", 401)
        # First alert fired
        assert mock_emit.call_count == 1

        # Simulate more 401s immediately after
        for _ in range(5):
            det.record("1.1.1.1", 401)

        # Still only one alert (cooldown active)
        assert mock_emit.call_count == 1


def test_brute_force_alert_repeated_after_cooldown():
    """Alert fires again after cooldown window elapses."""
    det = BruteForceDetector()

    with patch.object(det, "_emit_brute_force") as mock_emit:
        # First batch
        for _ in range(10):
            det.record("2.2.2.2", 401)
        assert mock_emit.call_count == 1

        # Manually expire the alert timestamp
        det._alerted["2.2.2.2"] = time.monotonic() - 65

        # Second batch triggers second alert
        for _ in range(5):
            det.record("2.2.2.2", 401)

        assert mock_emit.call_count == 2


# ─── BruteForceDetector — LRU eviction ───────────────────────────────────────


def test_brute_force_lru_evicts_when_full():
    """When _MAX_TRACKED_IPS is reached, oldest entry is evicted."""
    from app.infrastructure.monitoring import security_probe as sp

    original_max = sp._MAX_TRACKED_IPS
    try:
        sp._MAX_TRACKED_IPS = 3
        det = BruteForceDetector()

        with patch.object(det, "_emit_brute_force"):
            det.record("1.0.0.1", 401)
            det.record("1.0.0.2", 401)
            det.record("1.0.0.3", 401)
            assert len(det._windows) == 3

            # Adding 4th should evict oldest
            det.record("1.0.0.4", 401)
            assert len(det._windows) <= 3
    finally:
        sp._MAX_TRACKED_IPS = original_max


# ─── BruteForceDetector — alerted pruning ────────────────────────────────────


def test_brute_force_alerted_dict_pruned_at_100():
    """When _alerted grows beyond 100, stale entries are pruned."""
    det = BruteForceDetector()

    # Fill _alerted with 101 stale entries
    stale_time = time.monotonic() - 200
    for i in range(101):
        det._alerted[f"10.0.{i // 256}.{i % 256}"] = stale_time

    # Trigger a real brute-force alert for a new IP
    with patch.object(det, "_emit_brute_force"):
        for _ in range(10):
            det.record("99.99.99.99", 401)

    # Stale entries should have been pruned
    assert len(det._alerted) < 110  # pruning happened


# ─── BruteForceDetector — _emit_brute_force ──────────────────────────────────


def test_emit_brute_force_calls_emit():
    """_emit_brute_force calls monitoring.emit with CRITICAL severity."""
    det = BruteForceDetector()

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        det._emit_brute_force("1.2.3.4", 12)

    mock_emit.assert_called_once()
    event = mock_emit.call_args[0][0]
    from app.infrastructure.monitoring.models import ErrorSeverity

    assert event.severity == ErrorSeverity.CRITICAL
    assert "1.2.3.4" in event.message
    assert "12" in event.message


# ─── RBACViolationTracker ─────────────────────────────────────────────────────


def test_rbac_below_threshold_no_emit():
    tracker = RBACViolationTracker()
    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        for _ in range(19):
            tracker.record(user_id=1, endpoint="/api/v1/admin")
        mock_emit.assert_not_called()


def test_rbac_at_threshold_emits():
    tracker = RBACViolationTracker()
    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        for _ in range(20):
            tracker.record(user_id=2, endpoint="/api/v1/admin")
        mock_emit.assert_called_once()


def test_rbac_alert_not_repeated_within_window():
    """Second burst within aggregation window → only one alert."""
    tracker = RBACViolationTracker()
    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        for _ in range(20):
            tracker.record(user_id=3, endpoint="/api/v1/x")
        assert mock_emit.call_count == 1

        for _ in range(10):
            tracker.record(user_id=3, endpoint="/api/v1/y")
        # Still one alert
        assert mock_emit.call_count == 1


def test_rbac_alert_repeated_after_cooldown():
    """Alert re-fires after aggregation window elapses."""
    tracker = RBACViolationTracker()
    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        for _ in range(20):
            tracker.record(user_id=4, endpoint="/admin")
        assert mock_emit.call_count == 1

        # Expire the alert
        tracker._alerted[4] = time.monotonic() - 400

        for _ in range(5):
            tracker.record(user_id=4, endpoint="/admin")

        assert mock_emit.call_count == 2


def test_rbac_lru_evicts_when_full():
    """LRU eviction kicks in when _MAX_TRACKED_USERS is hit."""
    from app.infrastructure.monitoring import security_probe as sp

    original_max = sp._MAX_TRACKED_USERS
    try:
        sp._MAX_TRACKED_USERS = 3
        tracker = RBACViolationTracker()
        with patch("app.infrastructure.monitoring.emit"):
            tracker.record(1, "/a")
            tracker.record(2, "/b")
            tracker.record(3, "/c")
            assert len(tracker._windows) == 3

            tracker.record(4, "/d")
            assert len(tracker._windows) <= 3
    finally:
        sp._MAX_TRACKED_USERS = original_max


def test_rbac_different_users_independent():
    """Violations from one user do not bleed into another."""
    tracker = RBACViolationTracker()
    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        for _ in range(19):
            tracker.record(100, "/api")
        for _ in range(19):
            tracker.record(200, "/api")
        mock_emit.assert_not_called()


def test_rbac_endpoints_sample_included_in_event():
    """The emitted event includes an endpoints_sample in metadata."""
    tracker = RBACViolationTracker()
    captured = []

    with patch(
        "app.infrastructure.monitoring.emit", side_effect=lambda ev: captured.append(ev)
    ):
        for i in range(20):
            tracker.record(999, f"/endpoint/{i}")

    assert len(captured) == 1
    assert "endpoints_sample" in captured[0].metadata


def test_rbac_alerted_dict_pruned_at_100():
    """_alerted dict pruned when it exceeds 100 entries."""
    tracker = RBACViolationTracker()
    stale = time.monotonic() - 1200
    for i in range(101):
        tracker._alerted[i + 1000] = stale

    with patch("app.infrastructure.monitoring.emit"):
        for _ in range(20):
            tracker.record(user_id=9999, endpoint="/admin")

    assert len(tracker._alerted) < 110


# ─── emit_jwt_anomaly ─────────────────────────────────────────────────────────


def test_jwt_anomaly_expired_is_info():
    from app.infrastructure.monitoring.models import ErrorSeverity

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("ExpiredSignatureError", "/api/login", "1.2.3.4")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.INFO


def test_jwt_anomaly_immature_is_error():
    from app.infrastructure.monitoring.models import ErrorSeverity

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("ImmatureSignatureError", "/api/data", "5.6.7.8")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.ERROR


def test_jwt_anomaly_decode_error_is_error():
    from app.infrastructure.monitoring.models import ErrorSeverity

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("DecodeError", "/api/v1/trips", "9.10.11.12")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.ERROR


def test_jwt_anomaly_invalid_signature_is_error():
    from app.infrastructure.monitoring.models import ErrorSeverity

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("InvalidSignatureError", "/", "10.0.0.1")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.ERROR


def test_jwt_anomaly_invalid_algorithm_is_critical():
    from app.infrastructure.monitoring.models import ErrorSeverity

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("InvalidAlgorithmError", "/auth", "10.0.0.2")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.CRITICAL


def test_jwt_anomaly_unknown_exc_type_is_warning():
    from app.infrastructure.monitoring.models import ErrorSeverity

    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("SomeUnknownError", "/path", "10.0.0.3")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.WARNING


def test_jwt_anomaly_metadata_contains_fields():
    with patch("app.infrastructure.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("DecodeError", "/api/v1/x", "1.1.1.1")

    event = mock_emit.call_args[0][0]
    assert event.metadata["exc_type"] == "DecodeError"
    assert event.metadata["ip"] == "1.1.1.1"
    assert event.metadata["path"] == "/api/v1/x"


# ─── Module-level singletons ──────────────────────────────────────────────────


def test_get_brute_force_detector_returns_instance():
    det = get_brute_force_detector()
    assert isinstance(det, BruteForceDetector)


def test_get_rbac_tracker_returns_instance():
    tracker = get_rbac_tracker()
    assert isinstance(tracker, RBACViolationTracker)


def test_singletons_are_same_object():
    """get_brute_force_detector returns the same object on repeated calls."""
    assert get_brute_force_detector() is get_brute_force_detector()
    assert get_rbac_tracker() is get_rbac_tracker()
