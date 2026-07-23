"""Additional coverage for security_probe.py (Redis-backed, FAZ2).

Targets: _is_trusted_local_ip, BruteForceDetector record (Redis INCR+EXPIRE +
alert dedup via SET NX) + degraded (Redis-down) path, RBACViolationTracker
record + threshold + endpoints_sample + degraded path, emit_jwt_anomaly all
severity paths, module-level singletons.
"""

from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.platform_infra.monitoring.security_probe import (
    BruteForceDetector,
    RBACViolationTracker,
    _is_trusted_local_ip,
    emit_jwt_anomaly,
    get_brute_force_detector,
    get_rbac_tracker,
)

pytestmark = pytest.mark.unit


class _FakeAsyncRedis:
    """Minimal in-memory stand-in for `redis.asyncio.Redis` — just enough of
    INCR/EXPIRE/SET NX/LPUSH/LTRIM/LRANGE to exercise the detectors' real
    command sequences without a live Redis."""

    def __init__(self):
        self._counters: dict = {}
        self._nx_keys: dict = {}
        self._lists: dict = {}

    async def incr(self, key):
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key, seconds):  # noqa: ARG002
        return True

    async def set(self, key, value, nx=False, ex=None):  # noqa: ARG002
        if nx and key in self._nx_keys:
            return None
        self._nx_keys[key] = value
        return True

    async def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    async def ltrim(self, key, start, end):
        if key in self._lists:
            self._lists[key] = self._lists[key][start : end + 1]
        return True

    async def lrange(self, key, start, end):
        return self._lists.get(key, [])[start : end + 1]

    def expire_alert(self, key: str) -> None:
        """Test helper: simulate the NX cooldown key's TTL elapsing."""
        self._nx_keys.pop(key, None)


def _patch_redis(fake):
    return patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=type("Mgr", (), {"_redis": fake})(),
    )


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


async def test_brute_force_trusted_ip_ignored():
    """Loopback IP 401s never trigger alert regardless of count — and never
    even touch Redis (early return)."""
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(20):
            await det.record("127.0.0.1", 401)
        mock_emit.assert_not_called()
        assert fake._counters == {}


async def test_brute_force_docker_bridge_ignored():
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(15):
            await det.record("172.17.0.2", 401)
        mock_emit.assert_not_called()


# ─── BruteForceDetector — non-401 codes ──────────────────────────────────────


async def test_brute_force_200_ignored():
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(50):
            await det.record("5.6.7.8", 200)
        mock_emit.assert_not_called()


async def test_brute_force_403_ignored():
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(50):
            await det.record("9.10.11.12", 403)
        mock_emit.assert_not_called()


# ─── BruteForceDetector — Redis INCR path + alert dedup ──────────────────────


async def test_brute_force_below_threshold_no_emit():
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            await det.record("1.1.1.1", 401)
        mock_emit.assert_not_called()


async def test_brute_force_alert_not_repeated_within_window():
    """Second burst within the NX cooldown window → alert fires only once."""
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(10):
            await det.record("1.1.1.1", 401)
        assert mock_emit.call_count == 1

        for _ in range(5):
            await det.record("1.1.1.1", 401)
        assert mock_emit.call_count == 1


async def test_brute_force_alert_repeated_after_cooldown():
    """Alert fires again once the NX cooldown key has expired."""
    det = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(det, "_emit_brute_force") as mock_emit:
        for _ in range(10):
            await det.record("2.2.2.2", 401)
        assert mock_emit.call_count == 1

        fake.expire_alert("secprobe:bf:alerted:2.2.2.2")

        for _ in range(1):
            await det.record("2.2.2.2", 401)
        assert mock_emit.call_count == 2


# ─── BruteForceDetector — 4-worker simulation (MEMORY §4.1 acceptance test) ──


async def test_brute_force_four_workers_share_one_threshold():
    """MEMORY §4.1: with `UVICORN_WORKERS=4`, four separate processes each ran
    their OWN in-memory `BruteForceDetector` — the same IP could rack up
    ~4×`_BRUTE_FORCE_THRESHOLD` attempts (spread round-robin across workers)
    before anything fired. Simulate that exact topology with 4 independent
    `BruteForceDetector` instances (one per "worker") sharing one Redis, and
    assert the threshold is now enforced on the TOTAL, not per-instance."""
    fake = _FakeAsyncRedis()
    workers = [BruteForceDetector() for _ in range(4)]

    with _patch_redis(fake), patch.object(
        workers[0], "_emit_brute_force"
    ) as w0, patch.object(workers[1], "_emit_brute_force") as w1, patch.object(
        workers[2], "_emit_brute_force"
    ) as w2, patch.object(workers[3], "_emit_brute_force") as w3:
        mocks = [w0, w1, w2, w3]
        # Round-robin 9 requests across 4 "workers" — below threshold (10),
        # even though the busiest single worker only saw 3.
        for i in range(9):
            await workers[i % 4].record("6.6.6.6", 401)
        assert sum(m.call_count for m in mocks) == 0

        # The 10th request (still round-robin, worker index 9%4=1) crosses the
        # SHARED threshold — pre-fix, each worker's own counter would have
        # been at most 3, nowhere near the per-process threshold of 10.
        await workers[9 % 4].record("6.6.6.6", 401)
        assert sum(m.call_count for m in mocks) == 1


# ─── BruteForceDetector — Redis unavailable (fail-loud, not fail-closed) ─────


async def test_brute_force_redis_down_emits_critical_and_does_not_count():
    det = BruteForceDetector()
    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=type("Mgr", (), {"_redis": None})(),
    ), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        await det.record("8.8.8.8", 401)

    mock_aemit.assert_called_once()
    event = mock_aemit.call_args[0][0]
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert event.severity == ErrorSeverity.CRITICAL
    assert event.category == "detector_degraded"


async def test_brute_force_redis_error_degrades_gracefully():
    """A raised exception from Redis (not just `_redis is None`) also degrades
    instead of propagating and breaking the request."""
    det = BruteForceDetector()
    broken = AsyncMock()
    broken.incr.side_effect = ConnectionError("boom")
    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=type("Mgr", (), {"_redis": broken})(),
    ), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        await det.record("8.8.4.4", 401)  # must not raise

    mock_aemit.assert_called_once()


# ─── BruteForceDetector — _emit_brute_force ──────────────────────────────────


async def test_emit_brute_force_calls_aemit():
    det = BruteForceDetector()

    with patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        await det._emit_brute_force("1.2.3.4", 12)

    mock_aemit.assert_called_once()
    event = mock_aemit.call_args[0][0]
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert event.severity == ErrorSeverity.CRITICAL
    assert "1.2.3.4" in event.message
    assert "12" in event.message


# ─── RBACViolationTracker ─────────────────────────────────────────────────────


async def test_rbac_below_threshold_no_emit():
    tracker = RBACViolationTracker()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        for _ in range(19):
            await tracker.record(user_id=1, endpoint="/api/v1/admin")
        mock_aemit.assert_not_called()


async def test_rbac_at_threshold_emits():
    tracker = RBACViolationTracker()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        for _ in range(20):
            await tracker.record(user_id=2, endpoint="/api/v1/admin")
        mock_aemit.assert_called_once()


async def test_rbac_alert_not_repeated_within_window():
    tracker = RBACViolationTracker()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        for _ in range(20):
            await tracker.record(user_id=3, endpoint="/api/v1/x")
        assert mock_aemit.call_count == 1

        for _ in range(10):
            await tracker.record(user_id=3, endpoint="/api/v1/y")
        assert mock_aemit.call_count == 1


async def test_rbac_alert_repeated_after_cooldown():
    tracker = RBACViolationTracker()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        for _ in range(20):
            await tracker.record(user_id=4, endpoint="/admin")
        assert mock_aemit.call_count == 1

        fake.expire_alert("secprobe:rbac:alerted:4")

        await tracker.record(user_id=4, endpoint="/admin")
        assert mock_aemit.call_count == 2


async def test_rbac_different_users_independent():
    tracker = RBACViolationTracker()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        for _ in range(19):
            await tracker.record(100, "/api")
        for _ in range(19):
            await tracker.record(200, "/api")
        mock_aemit.assert_not_called()


async def test_rbac_endpoints_sample_included_in_event():
    tracker = RBACViolationTracker()
    fake = _FakeAsyncRedis()
    captured = []

    async def _capture(ev):
        captured.append(ev)

    with _patch_redis(fake), patch(
        "v2.modules.platform_infra.monitoring.aemit", side_effect=_capture
    ):
        for i in range(20):
            await tracker.record(999, f"/endpoint/{i}")

    assert len(captured) == 1
    assert "endpoints_sample" in captured[0].metadata
    assert len(captured[0].metadata["endpoints_sample"]) <= 10


async def test_rbac_redis_down_emits_critical_and_does_not_count():
    tracker = RBACViolationTracker()
    with patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=type("Mgr", (), {"_redis": None})(),
    ), patch(
        "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
    ) as mock_aemit:
        await tracker.record(user_id=42, endpoint="/admin")

    mock_aemit.assert_called_once()
    event = mock_aemit.call_args[0][0]
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert event.severity == ErrorSeverity.CRITICAL
    assert event.category == "detector_degraded"


# ─── emit_jwt_anomaly ─────────────────────────────────────────────────────────


def test_jwt_anomaly_expired_is_info():
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("ExpiredSignatureError", "/api/login", "1.2.3.4")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.INFO


def test_jwt_anomaly_immature_is_error():
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("ImmatureSignatureError", "/api/data", "5.6.7.8")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.ERROR


def test_jwt_anomaly_decode_error_is_error():
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("DecodeError", "/api/v1/trips", "9.10.11.12")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.ERROR


def test_jwt_anomaly_invalid_signature_is_error():
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("InvalidSignatureError", "/", "10.0.0.1")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.ERROR


def test_jwt_anomaly_invalid_algorithm_is_critical():
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("InvalidAlgorithmError", "/auth", "10.0.0.2")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.CRITICAL


def test_jwt_anomaly_unknown_exc_type_is_warning():
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        emit_jwt_anomaly("SomeUnknownError", "/path", "10.0.0.3")

    event = mock_emit.call_args[0][0]
    assert event.severity == ErrorSeverity.WARNING


def test_jwt_anomaly_metadata_contains_fields():
    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
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
