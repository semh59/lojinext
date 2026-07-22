from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque

from app.infrastructure.logging.logger import get_logger
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

_MAX_TRACKED_IPS = 10_000
_MAX_TRACKED_USERS = 5_000

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


class BruteForceDetector:
    def __init__(self) -> None:
        self._windows: OrderedDict[str, deque] = OrderedDict()
        self._alerted: dict[str, float] = {}
        self._lock = threading.Lock()

    def record(self, ip: str, status_code: int) -> None:
        if status_code != 401:
            return
        # Loopback + Docker bridge IP'leri brute force tetiklemez.
        if _is_trusted_local_ip(ip):
            return
        now = time.monotonic()
        with self._lock:
            if ip not in self._windows:
                if len(self._windows) >= _MAX_TRACKED_IPS:
                    self._windows.popitem(last=False)  # evict LRU
            else:
                self._windows.move_to_end(ip)  # mark as recently used
            if ip not in self._windows:
                self._windows[ip] = deque()
            q = self._windows[ip]
            q.append(now)
            while q and now - q[0] > _BRUTE_FORCE_WINDOW_SEC:
                q.popleft()
            if len(q) >= _BRUTE_FORCE_THRESHOLD:
                last_alert = self._alerted.get(ip, 0.0)
                if now - last_alert > _BRUTE_FORCE_WINDOW_SEC:
                    # Prune stale alerted entries (avoid unbounded growth)
                    if len(self._alerted) > 100:
                        cutoff = now - 2 * _BRUTE_FORCE_WINDOW_SEC
                        self._alerted = {
                            k: v for k, v in self._alerted.items() if v > cutoff
                        }
                    self._alerted[ip] = now
                    self._emit_brute_force(ip, len(q))

    def _emit_brute_force(self, ip: str, attempts: int) -> None:
        from v2.modules.platform_infra.monitoring import emit

        emit(
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
    def __init__(self) -> None:
        self._windows: OrderedDict[int, deque] = OrderedDict()
        self._alerted: dict[int, float] = {}
        self._lock = threading.Lock()

    def record(self, user_id: int, endpoint: str) -> None:
        now = time.monotonic()
        with self._lock:
            if user_id not in self._windows:
                if len(self._windows) >= _MAX_TRACKED_USERS:
                    self._windows.popitem(last=False)  # evict LRU
            else:
                self._windows.move_to_end(user_id)  # mark as recently used
            if user_id not in self._windows:
                self._windows[user_id] = deque()
            q = self._windows[user_id]
            q.append((now, endpoint))
            while q and now - q[0][0] > _RBAC_AGGREGATION_WINDOW_SEC:
                q.popleft()
            if len(q) >= _RBAC_VIOLATION_THRESHOLD:
                last_alert = self._alerted.get(user_id, 0.0)
                if now - last_alert > _RBAC_AGGREGATION_WINDOW_SEC:
                    # Prune stale alerted entries (avoid unbounded growth)
                    if len(self._alerted) > 100:
                        cutoff = now - 2 * _RBAC_AGGREGATION_WINDOW_SEC
                        self._alerted = {
                            k: v for k, v in self._alerted.items() if v > cutoff
                        }
                    self._alerted[user_id] = now
                    endpoints = list({ep for _, ep in q})[:10]
                    from v2.modules.platform_infra.monitoring import emit

                    emit(
                        ErrorEvent(
                            layer=ErrorLayer.SECURITY,
                            category="rbac_scraping",
                            severity=ErrorSeverity.ERROR,
                            message=(
                                f"User {user_id}: {len(q)} 403s"
                                f" in {_RBAC_AGGREGATION_WINDOW_SEC}s"
                            ),
                            metadata={
                                "user_id": user_id,
                                "attempt_count": len(q),
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
