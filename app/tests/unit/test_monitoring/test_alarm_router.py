import time
from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.monitoring.alarm_router import (
    _DEDUP_WINDOW_SECONDS,
    _MIN_SAMPLES,
    _Z_SCORE_THRESHOLD,
    AlarmRouter,
    AnomalyDetector,
)
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity


def make_event(sev=ErrorSeverity.CRITICAL, layer=ErrorLayer.DB, category="test"):
    return ErrorEvent(layer=layer, category=category, severity=sev, message="test")


@pytest.mark.unit
async def test_critical_routes_immediately():
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.CRITICAL)
    with patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)):
        mock_send = AsyncMock()
        with patch.object(router, "_send_immediate", mock_send):
            await router.route(ev)
            mock_send.assert_called_once()


@pytest.mark.unit
async def test_warning_does_not_send_immediately():
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.WARNING)
    with patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)):
        mock_send = AsyncMock()
        with patch.object(router, "_send_immediate", mock_send):
            await router.route(ev)
            mock_send.assert_not_called()


@pytest.mark.unit
def test_z_score_spike_detection():
    detector = AnomalyDetector()
    counts = [2, 3, 2, 4, 2, 3, 2, 4, 2, 3, 2, 20]
    assert detector._compute_z_score(counts) > 3.0


@pytest.mark.unit
def test_z_score_no_spike():
    detector = AnomalyDetector()
    counts = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6]
    assert detector._compute_z_score(counts) < 3.0


@pytest.mark.unit
def test_z_score_insufficient_data():
    detector = AnomalyDetector()
    assert detector._compute_z_score([10, 20]) is None


# ─── Z-score edge cases ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_z_score_returns_none_for_empty():
    detector = AnomalyDetector()
    assert detector._compute_z_score([]) is None


@pytest.mark.unit
def test_z_score_flat_baseline_returns_zero():
    """All identical values → stdev=0 → 0.0 (not exception)."""
    detector = AnomalyDetector()
    counts = [5] * (_MIN_SAMPLES + 1)  # 7 values total
    z = detector._compute_z_score(counts)
    assert z == 0.0


@pytest.mark.unit
def test_z_score_exactly_min_samples_plus_one():
    """Exactly _MIN_SAMPLES+1 points is the minimum valid input."""
    detector = AnomalyDetector()
    counts = [10] * _MIN_SAMPLES + [10]
    z = detector._compute_z_score(counts)
    assert z is not None  # valid, stdev=0 → 0.0


@pytest.mark.unit
def test_z_score_below_threshold_is_not_anomaly():
    """Small spike, z < 3."""
    detector = AnomalyDetector()
    counts = [10, 10, 10, 10, 10, 10, 12]
    z = detector._compute_z_score(counts)
    assert z is not None
    assert z < _Z_SCORE_THRESHOLD


# ─── Dedup ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_critical_dedup_within_window():
    """Same fingerprint sent twice within 900s → _send_immediate called once."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.CRITICAL)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
    ):
        await router.route(ev)
        await router.route(ev)  # same fingerprint, within dedup window
        assert mock_send.call_count == 1


@pytest.mark.unit
async def test_critical_resent_after_dedup_expires():
    """900s dedup window passed → second CRITICAL sent."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.CRITICAL)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
    ):
        await router.route(ev)
        # Backdate the sent timestamp past the dedup window
        router._sent_critical[ev.fingerprint] = time.monotonic() - (
            _DEDUP_WINDOW_SECONDS + 1
        )
        await router.route(ev)
        assert mock_send.call_count == 2


@pytest.mark.unit
async def test_stale_dedup_entries_pruned():
    """Entries older than 2×_DEDUP_WINDOW removed during route() call."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.CRITICAL)
    stale_fp = "definitely_stale_fp"
    router._sent_critical[stale_fp] = time.monotonic() - (2 * _DEDUP_WINDOW_SECONDS + 1)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock),
    ):
        await router.route(ev)

    assert stale_fp not in router._sent_critical


# ─── Anomaly escalation ────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_error_event_sends_immediate_and_digest():
    """ERROR severity (non-anomaly) → immediate send + digest counter (first occurrence)."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.ERROR)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(
            router, "_increment_digest_counter", new_callable=AsyncMock
        ) as mock_digest,
    ):
        await router.route(ev)
        mock_send.assert_called_once_with(ev, is_anomaly=False)
        mock_digest.assert_called_once_with(ev)


@pytest.mark.unit
async def test_error_event_deduped_after_first_send():
    """ERROR severity — second occurrence within dedup window skips _send_immediate."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.ERROR)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=False)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(router, "_increment_digest_counter", new_callable=AsyncMock),
    ):
        await router.route(ev)
        await router.route(ev)
        mock_send.assert_called_once()  # second call deduped


@pytest.mark.unit
async def test_anomaly_escalates_error_to_immediate():
    """ERROR + anomaly=True → escalated to CRITICAL path, _send_immediate called."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.ERROR)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=True)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(
            router, "_increment_digest_counter", new_callable=AsyncMock
        ) as mock_digest,
    ):
        await router.route(ev)
        mock_send.assert_called_once_with(ev, is_anomaly=True)
        mock_digest.assert_not_called()


@pytest.mark.unit
async def test_anomaly_escalates_warning_to_immediate():
    """WARNING + anomaly → CRITICAL path, _send_immediate called."""
    router = AlarmRouter()
    ev = make_event(sev=ErrorSeverity.WARNING)

    with (
        patch.object(router._anomaly, "check", new=AsyncMock(return_value=True)),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
    ):
        await router.route(ev)
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs.get("is_anomaly") is True
