"""Tests for the silent-fallback observability probe (GO operation gate #3)."""

from unittest.mock import patch

import pytest

from v2.modules.platform_infra.monitoring.silent_fallback_probe import (
    SilentFallbackProbe,
    get_silent_fallback_probe,
    record_silent_fallback,
)

pytestmark = pytest.mark.unit


def test_record_increments_count_by_reason():
    probe = SilentFallbackProbe()
    probe.record("sefer_estimator_timeout", arac_id=1)
    probe.record("sefer_estimator_timeout", arac_id=2)
    probe.record("open_meteo_elevation_failed", status_code=429)

    stats = probe.get_stats()
    assert stats["reasons"]["sefer_estimator_timeout"] == 2
    assert stats["reasons"]["open_meteo_elevation_failed"] == 1
    assert stats["total"] == 3


def test_emits_alert_every_n_occurrences():
    probe = SilentFallbackProbe()
    with patch.object(probe, "_emit") as mock_emit:
        # 24 occurrences → no emit yet
        for _ in range(24):
            probe.record("sefer_estimator_timeout")
        assert mock_emit.call_count == 0
        # 25th → one alert
        probe.record("sefer_estimator_timeout")
        assert mock_emit.call_count == 1

    event = mock_emit.call_args[0][0]
    assert event.category == "silent_fallback"
    assert event.metadata["reason"] == "sefer_estimator_timeout"
    assert event.metadata["count"] == 25


def test_emit_failure_never_propagates():
    probe = SilentFallbackProbe()
    with patch.object(probe, "_emit", side_effect=RuntimeError("sentry down")):
        # Even at the alert boundary, a failing emit must not break the caller.
        for _ in range(25):
            probe.record("sefer_estimator_timeout")
    # If we got here without raising, the contract holds.
    assert probe.get_stats()["total"] == 25


def test_module_level_record_never_raises():
    # Even with a broken probe, the convenience helper swallows errors.
    with patch(
        "v2.modules.platform_infra.monitoring.silent_fallback_probe.get_silent_fallback_probe",
        side_effect=RuntimeError("boom"),
    ):
        record_silent_fallback("whatever")  # must not raise


def test_get_silent_fallback_probe_is_singleton():
    a = get_silent_fallback_probe()
    b = get_silent_fallback_probe()
    assert a is b


def test_stats_exposes_alert_threshold():
    probe = SilentFallbackProbe()
    assert probe.get_stats()["alert_every_n"] == 25
