from __future__ import annotations

from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.monitoring.models import (
    ErrorEvent,
    ErrorLayer,
    ErrorSeverity,
)

logger = get_logger(__name__)

_BRUTE_FORCE_THRESHOLD = 10
_BRUTE_FORCE_WINDOW_SEC = 60
_RBAC_AGGREGATION_WINDOW_SEC = 300
_RBAC_VIOLATION_THRESHOLD = 20

# Loopback + Docker bridge — testlerden gelen 401'ler brute force değil.
# Production'da gerçek client'lar dış IP'lerden gelir; bu prefix'ler
# güvenle bypass edilebilir.
_TRUSTED_BRUTE_FORCE_PREFIXES = (
    "127.",
    "::1",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
)


def _is_trusted_local_ip(ip: str) -> bool:
    if not ip:
        return False
    return any(ip.startswith(p) for p in _TRUSTED_BRUTE_FORCE_PREFIXES)


def _get_redis():
    """Return the shared async Redis client, or None if unavailable.

    Same access point `rate_limit_middleware.py` uses (`get_pubsub_manager()`)
    — one shared connection, no separate pool for this module.
    """
    from v2.modules.platform_infra.cache.redis_pubsub import get_pubsub_manager

    mgr = get_pubsub_manager()
    return mgr._redis


async def _emit_degraded(detector: str, reason: Exception) -> None:
    """Redis unavailable — the counter this call was supposed to update is
    dropped (fail-loud, not fail-closed: there is no request left to reject
    at this point in the pipeline, see `security_probe.py`'s post-response
    call site in `logging_middleware.py`). Login itself fails closed via
    `RateLimitMiddleware`'s `_AUTH_PATHS` tight limit — that IS a pre-request
    gate and already fails closed on Redis outage.
    """
    from v2.modules.platform_infra.monitoring import aemit

    logger.critical(
        "%s degraded: Redis unavailable (%s) — this attempt was NOT counted",
        detector,
        reason,
    )
    await aemit(
        ErrorEvent(
            layer=ErrorLayer.SECURITY,
            category="detector_degraded",
            severity=ErrorSeverity.CRITICAL,
            message=f"{detector} degraded: Redis unavailable — attempts are not being counted",
            metadata={"detector": detector, "reason": str(reason)},
        )
    )


class BruteForceDetector:
    """Redis-backed: INCR+EXPIRE per-IP sliding window, shared across workers."""

    async def record(self, ip: str, status_code: int) -> None:
        if status_code != 401:
            return
        # Loopback + Docker bridge IP'leri brute force tetiklemez.
        if _is_trusted_local_ip(ip):
            return
        redis = _get_redis()
        if redis is None:
            await _emit_degraded(
                "BruteForceDetector", RuntimeError("no redis client configured")
            )
            return
        try:
            key = f"secprobe:bf:{ip}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, _BRUTE_FORCE_WINDOW_SEC)
            if count >= _BRUTE_FORCE_THRESHOLD:
                alert_key = f"secprobe:bf:alerted:{ip}"
                # NX: only the first crosser in the window fires the alert.
                alerted = await redis.set(
                    alert_key, "1", nx=True, ex=_BRUTE_FORCE_WINDOW_SEC
                )
                if alerted:
                    await self._emit_brute_force(ip, count)
        except Exception as exc:
            await _emit_degraded("BruteForceDetector", exc)

    async def _emit_brute_force(self, ip: str, attempts: int) -> None:
        from v2.modules.platform_infra.monitoring import aemit

        await aemit(
            ErrorEvent(
                layer=ErrorLayer.SECURITY,
                category="brute_force",
                severity=ErrorSeverity.CRITICAL,
                message=(
                    f"Brute force from {ip}: {attempts} attempts"
                    f" in {_BRUTE_FORCE_WINDOW_SEC}s"
                ),
                metadata={
                    "ip": ip,
                    "attempts": attempts,
                    "window_sec": _BRUTE_FORCE_WINDOW_SEC,
                },
            )
        )


class RBACViolationTracker:
    """Redis-backed: INCR+EXPIRE per-user counter + capped endpoint sample list."""

    async def record(self, user_id: int, endpoint: str) -> None:
        redis = _get_redis()
        if redis is None:
            await _emit_degraded(
                "RBACViolationTracker", RuntimeError("no redis client configured")
            )
            return
        try:
            count_key = f"secprobe:rbac:{user_id}"
            endpoints_key = f"secprobe:rbac:endpoints:{user_id}"
            count = await redis.incr(count_key)
            if count == 1:
                await redis.expire(count_key, _RBAC_AGGREGATION_WINDOW_SEC)
            await redis.lpush(endpoints_key, endpoint)
            await redis.ltrim(endpoints_key, 0, 9)
            await redis.expire(endpoints_key, _RBAC_AGGREGATION_WINDOW_SEC)
            if count >= _RBAC_VIOLATION_THRESHOLD:
                alert_key = f"secprobe:rbac:alerted:{user_id}"
                alerted = await redis.set(
                    alert_key, "1", nx=True, ex=_RBAC_AGGREGATION_WINDOW_SEC
                )
                if alerted:
                    endpoints_raw = await redis.lrange(endpoints_key, 0, 9)
                    endpoints = [
                        e.decode() if isinstance(e, bytes) else e
                        for e in endpoints_raw
                    ]
                    await self._emit_rbac_scraping(user_id, count, endpoints)
        except Exception as exc:
            await _emit_degraded("RBACViolationTracker", exc)

    async def _emit_rbac_scraping(
        self, user_id: int, count: int, endpoints: list
    ) -> None:
        from v2.modules.platform_infra.monitoring import aemit

        await aemit(
            ErrorEvent(
                layer=ErrorLayer.SECURITY,
                category="rbac_scraping",
                severity=ErrorSeverity.ERROR,
                message=(
                    f"User {user_id}: {count} 403s"
                    f" in {_RBAC_AGGREGATION_WINDOW_SEC}s"
                ),
                metadata={
                    "user_id": user_id,
                    "attempt_count": count,
                    "endpoints_sample": endpoints,
                },
            )
        )


def emit_jwt_anomaly(exc_type: str, path: str, ip: str) -> None:
    """JWT decode exception handler'larından çağrılır.

    ExpiredSignatureError beklenen davranış (tarayıcı saatlik refresh) —
    INFO seviyesinde sadece audit'e kayıt; Telegram digest'ine girmiyor.
    Diğer hatalar (decode/signature/algorithm) gerçek anomali → ERROR/CRITICAL.
    """
    severity_map = {
        "ExpiredSignatureError": ErrorSeverity.INFO,
        "ImmatureSignatureError": ErrorSeverity.ERROR,
        "DecodeError": ErrorSeverity.ERROR,
        "InvalidSignatureError": ErrorSeverity.ERROR,
        "InvalidAlgorithmError": ErrorSeverity.CRITICAL,
    }
    severity = severity_map.get(exc_type, ErrorSeverity.WARNING)
    from v2.modules.platform_infra.monitoring import emit

    emit(
        ErrorEvent(
            layer=ErrorLayer.SECURITY,
            category="jwt_anomaly",
            severity=severity,
            message=f"JWT {exc_type} from {ip} at {path}",
            metadata={"exc_type": exc_type, "ip": ip, "path": path},
        )
    )


_brute_force = BruteForceDetector()
_rbac_tracker = RBACViolationTracker()


def get_brute_force_detector() -> BruteForceDetector:
    return _brute_force


def get_rbac_tracker() -> RBACViolationTracker:
    return _rbac_tracker
