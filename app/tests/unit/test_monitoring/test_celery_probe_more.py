"""
Additional coverage tests for app/infrastructure/monitoring/celery_probe.py.

Targets uncovered lines:
- setup_celery_probe: signal handlers (on_prerun, on_postrun, on_failure, on_retry, on_revoked)
- on_prerun: eviction when >1000 entries, lazy purge at 64-multiple
- on_postrun: slow-task warn vs error severity, heartbeat on SUCCESS, memory pressure path
- on_failure: unlimited retries (max_retries=None) path, final vs non-final
"""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: build minimal task/sender mock
# ---------------------------------------------------------------------------


def _make_task(name="test.task"):
    t = MagicMock()
    t.name = name
    return t


def _make_sender(name="test.task", max_retries=3, retries=0):
    s = MagicMock()
    s.name = name
    s.max_retries = max_retries
    s.request = MagicMock()
    s.request.retries = retries
    return s


def _setup_probe_and_capture():
    """Patch celery.signals so setup_celery_probe captures handler functions."""
    from app.infrastructure.monitoring import celery_probe as cp

    connected_handlers: dict = {}

    class FakeSignal:
        def connect(self, fn, **kwargs):
            connected_handlers[fn.__name__] = fn

    fake_task_prerun = FakeSignal()
    fake_task_postrun = FakeSignal()
    fake_task_failure = FakeSignal()
    fake_task_retry = FakeSignal()
    fake_task_revoked = FakeSignal()

    fake_signals_mod = MagicMock()
    fake_signals_mod.task_prerun = fake_task_prerun
    fake_signals_mod.task_postrun = fake_task_postrun
    fake_signals_mod.task_failure = fake_task_failure
    fake_signals_mod.task_retry = fake_task_retry
    fake_signals_mod.task_revoked = fake_task_revoked

    # Patch sys.modules so "from celery.signals import ..." picks up our fake
    with patch.dict(sys.modules, {"celery.signals": fake_signals_mod}):
        cp.setup_celery_probe()

    return connected_handlers, cp


# ---------------------------------------------------------------------------
# _purge_stale_task_entries edge cases
# ---------------------------------------------------------------------------


def test_purge_keeps_entries_just_under_ttl():
    from app.infrastructure.monitoring import celery_probe as cp

    cp._task_start_times.clear()
    now = time.monotonic()
    cp._task_start_times["edge"] = now - cp._TASK_ENTRY_TTL_SECONDS + 1
    cp._purge_stale_task_entries(now)
    assert "edge" in cp._task_start_times
    cp._task_start_times.clear()


def test_purge_removes_entries_exactly_at_ttl():
    from app.infrastructure.monitoring import celery_probe as cp

    cp._task_start_times.clear()
    now = time.monotonic()
    cp._task_start_times["at_ttl"] = now - cp._TASK_ENTRY_TTL_SECONDS - 1
    cp._purge_stale_task_entries(now)
    assert "at_ttl" not in cp._task_start_times
    cp._task_start_times.clear()


# ---------------------------------------------------------------------------
# setup_celery_probe: on_prerun signal
# ---------------------------------------------------------------------------


def test_on_prerun_records_start_time():
    """on_prerun stores task_id in _task_start_times."""
    connected_handlers, cp = _setup_probe_and_capture()

    assert "on_prerun" in connected_handlers

    cp._task_start_times.clear()
    task = _make_task()
    connected_handlers["on_prerun"](task_id="tid-001", task=task)
    assert "tid-001" in cp._task_start_times
    cp._task_start_times.clear()


def test_on_prerun_evicts_oldest_when_over_1000():
    """on_prerun evicts oldest entry when dict already has >1000 items."""
    connected_handlers, cp = _setup_probe_and_capture()

    cp._task_start_times.clear()
    for i in range(1001):
        cp._task_start_times[f"fill-{i}"] = time.monotonic()

    assert len(cp._task_start_times) == 1001
    task = _make_task()
    connected_handlers["on_prerun"](task_id="new-tid", task=task)
    # Should have evicted one, then added new: net still ≤ 1001
    assert len(cp._task_start_times) <= 1001
    assert "new-tid" in cp._task_start_times
    cp._task_start_times.clear()


# ---------------------------------------------------------------------------
# setup_celery_probe: on_postrun signal
# ---------------------------------------------------------------------------


def test_on_postrun_no_emit_for_fast_task():
    """on_postrun does not emit for tasks faster than _SLOW_TASK_WARN_MS."""
    connected_handlers, cp = _setup_probe_and_capture()

    # RSS memory-pressure kontrolünü devre dışı bırak — bu test SADECE task-hız
    # mantığını izole eder. CI runner'da RSS > 800MB iken memory emit tetikleniyordu
    # (Windows'ta resource modülü yok → lokalde gizliydi, CI Linux'ta görünür).
    with (
        patch("app.infrastructure.monitoring.emit") as mock_emit,
        patch.object(cp, "_write_heartbeat_sync"),
        patch.object(cp, "_RESOURCE_AVAILABLE", False),
    ):
        cp._task_start_times["fast-tid"] = time.monotonic()
        task = _make_task("fast.task")
        connected_handlers["on_postrun"](task_id="fast-tid", task=task, state="SUCCESS")
        mock_emit.assert_not_called()


def test_on_postrun_emits_warning_for_slow_task():
    """on_postrun emits WARNING when task > _SLOW_TASK_WARN_MS but < _SLOW_TASK_ERROR_MS."""
    connected_handlers, cp = _setup_probe_and_capture()

    from app.infrastructure.monitoring.models import ErrorSeverity

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    with (
        patch("app.infrastructure.monitoring.emit", fake_emit),
        patch.object(cp, "_write_heartbeat_sync"),
    ):
        # 35s ago — above warn (30s) but below error (120s)
        cp._task_start_times["slow-tid"] = time.monotonic() - 35
        task = _make_task("slow.task")
        connected_handlers["on_postrun"](task_id="slow-tid", task=task, state="SUCCESS")

    slow_events = [e for e in emitted_events if e.category == "slow_task"]
    assert len(slow_events) >= 1
    assert slow_events[0].severity == ErrorSeverity.WARNING


def test_on_postrun_emits_error_for_very_slow_task():
    """on_postrun emits ERROR when task > _SLOW_TASK_ERROR_MS (120s)."""
    connected_handlers, cp = _setup_probe_and_capture()

    from app.infrastructure.monitoring.models import ErrorSeverity

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    with (
        patch("app.infrastructure.monitoring.emit", fake_emit),
        patch.object(cp, "_write_heartbeat_sync"),
    ):
        cp._task_start_times["very-slow"] = time.monotonic() - 130
        task = _make_task("very.slow.task")
        connected_handlers["on_postrun"](
            task_id="very-slow", task=task, state="FAILURE"
        )

    slow_events = [e for e in emitted_events if e.category == "slow_task"]
    assert len(slow_events) >= 1
    assert slow_events[0].severity == ErrorSeverity.ERROR


def test_on_postrun_writes_heartbeat_on_success():
    """on_postrun calls _write_heartbeat_sync when state=SUCCESS."""
    connected_handlers, cp = _setup_probe_and_capture()

    with patch.object(cp, "_write_heartbeat_sync") as mock_hb:
        cp._task_start_times["hb-tid"] = time.monotonic()
        task = _make_task("infra.task")
        connected_handlers["on_postrun"](task_id="hb-tid", task=task, state="SUCCESS")
        mock_hb.assert_called_once_with("infra.task")


def test_on_postrun_no_start_time_entry():
    """on_postrun handles missing task_id in _task_start_times without crash."""
    connected_handlers, cp = _setup_probe_and_capture()

    cp._task_start_times.pop("missing-tid", None)
    task = _make_task("some.task")

    with patch.object(cp, "_write_heartbeat_sync"):
        # Should not raise even when task_id not in dict
        connected_handlers["on_postrun"](
            task_id="missing-tid", task=task, state="SUCCESS"
        )


# ---------------------------------------------------------------------------
# setup_celery_probe: on_failure signal
# ---------------------------------------------------------------------------


def test_on_failure_unlimited_retries_not_final():
    """on_failure with max_retries=None and retries<10 → non-final failure."""
    connected_handlers, cp = _setup_probe_and_capture()

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    sender = _make_sender("retry.task", max_retries=None, retries=5)

    with patch("app.infrastructure.monitoring.emit", fake_emit):
        cp._task_start_times.pop("fail-tid", None)
        connected_handlers["on_failure"](
            task_id="fail-tid",
            exception=RuntimeError("boom"),
            traceback=None,
            sender=sender,
        )

    assert len(emitted_events) == 1
    evt = emitted_events[0]
    assert evt.category == "task_failure"


def test_on_failure_unlimited_retries_final():
    """on_failure with max_retries=None and retries>=10 → final failure."""
    connected_handlers, cp = _setup_probe_and_capture()

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    sender = _make_sender("retry.task", max_retries=None, retries=10)

    with patch("app.infrastructure.monitoring.emit", fake_emit):
        connected_handlers["on_failure"](
            task_id="fail-final",
            exception=RuntimeError("final"),
            traceback=None,
            sender=sender,
        )

    assert len(emitted_events) == 1
    assert emitted_events[0].category == "task_failure_final"


def test_on_failure_finite_retries_non_final():
    """on_failure with max_retries=3 and retries=1 → non-final."""
    connected_handlers, cp = _setup_probe_and_capture()

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    sender = _make_sender("retry.task", max_retries=3, retries=1)

    with patch("app.infrastructure.monitoring.emit", fake_emit):
        connected_handlers["on_failure"](
            task_id="fail-nonfinal",
            exception=ValueError("mid"),
            traceback=None,
            sender=sender,
        )

    assert emitted_events[0].category == "task_failure"


def test_on_failure_finite_retries_at_max_is_final():
    """on_failure with retries == max_retries → final failure."""
    connected_handlers, cp = _setup_probe_and_capture()

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    sender = _make_sender("retry.task", max_retries=3, retries=3)

    with patch("app.infrastructure.monitoring.emit", fake_emit):
        connected_handlers["on_failure"](
            task_id="fail-at-max",
            exception=ValueError("at max"),
            traceback=None,
            sender=sender,
        )

    assert emitted_events[0].category == "task_failure_final"


# ---------------------------------------------------------------------------
# setup_celery_probe: on_retry and on_revoked
# ---------------------------------------------------------------------------


def test_on_retry_emits_event():
    """on_retry emits a task_retry event."""
    connected_handlers, cp = _setup_probe_and_capture()

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    request = MagicMock()
    request.task = "infra.relay_outbox"
    request.retries = 2

    with patch("app.infrastructure.monitoring.emit", fake_emit):
        connected_handlers["on_retry"](
            request=request,
            reason="timeout",
            einfo=None,
        )

    assert len(emitted_events) == 1
    assert emitted_events[0].category == "task_retry"
    assert emitted_events[0].metadata["retry_count"] == 2


def test_on_revoked_emits_event():
    """on_revoked emits a task_revoked event."""
    connected_handlers, cp = _setup_probe_and_capture()

    emitted_events = []

    def fake_emit(event):
        emitted_events.append(event)

    request = MagicMock()
    request.task = "prediction.drain_dlq"

    with patch("app.infrastructure.monitoring.emit", fake_emit):
        connected_handlers["on_revoked"](
            request=request,
            terminated=True,
            signum=15,
            expired=False,
        )

    assert len(emitted_events) == 1
    assert emitted_events[0].category == "task_revoked"
    assert emitted_events[0].metadata["terminated"] is True
    assert emitted_events[0].metadata["signum"] == 15
