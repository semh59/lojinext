from unittest.mock import patch

import pytest

from v2.modules.platform_infra.monitoring.security_probe import BruteForceDetector

pytestmark = pytest.mark.unit


class _FakeAsyncRedis:
    """See `test_security_probe_coverage.py` for the fuller version — this
    file only needs INCR/EXPIRE (no alert dedup manipulation)."""

    def __init__(self):
        self._counters: dict = {}
        self._nx_keys: dict = {}

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


def _patch_redis(fake):
    return patch(
        "v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager",
        return_value=type("Mgr", (), {"_redis": fake})(),
    )


async def test_brute_force_not_triggered_below_threshold():
    detector = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            await detector.record("1.2.3.4", 401)
        mock_emit.assert_not_called()


async def test_brute_force_triggered_at_threshold():
    detector = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(10):
            await detector.record("1.2.3.4", 401)
        mock_emit.assert_called_once()


async def test_brute_force_ignores_non_401():
    detector = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(20):
            await detector.record("1.2.3.4", 200)
        mock_emit.assert_not_called()


async def test_brute_force_different_ips_independent():
    detector = BruteForceDetector()
    fake = _FakeAsyncRedis()
    with _patch_redis(fake), patch.object(detector, "_emit_brute_force") as mock_emit:
        for _ in range(9):
            await detector.record("1.1.1.1", 401)
            await detector.record("2.2.2.2", 401)
        mock_emit.assert_not_called()
