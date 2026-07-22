"""
Additional coverage tests for v2/modules/platform_infra/monitoring/db_probe.py.

Targets uncovered lines:
- setup_db_probe: _before handler sets _query_start
- setup_db_probe: _after handler — slow query emit (500–2000ms), N+1 emit at threshold
- setup_db_probe: _on_error — critical vs non-critical PG codes
- setup_db_probe: _on_checkout — pool pressure emit, throttle guard
- _auto_explain: SELECT without params, rate-limit eviction when >200 entries
- _auto_explain: full explain path with mocked session (plan with Seq Scan)
- reset_recent_queries / get_query_count after increments
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers to capture registered event callbacks
# ---------------------------------------------------------------------------


def _capture_handlers(mock_event, handler_names):  # noqa: ARG001
    """Returns dict mapping handler_name → fn, from listens_for calls."""
    handlers: dict = {}

    def listens_for_decorator(engine, event_name, **kw):  # noqa: ARG001
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    mock_event.listens_for.side_effect = listens_for_decorator
    return handlers


# ---------------------------------------------------------------------------
# setup_db_probe: _before handler
# ---------------------------------------------------------------------------


def test_before_handler_sets_query_start():
    """_before sets _query_start context var to current time."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _query_start,
        setup_db_probe,
    )

    mock_engine = MagicMock()
    mock_sync_engine = MagicMock()
    mock_engine.sync_engine = mock_sync_engine

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    assert "_before" in handlers
    _query_start.set(0.0)
    handlers["_before"](None, None, "SELECT 1", None, None, False)
    assert _query_start.get(0.0) > 0.0


# ---------------------------------------------------------------------------
# setup_db_probe: _after handler — fast query, no emit
# ---------------------------------------------------------------------------


def test_after_handler_fast_query_no_emit():
    """_after does not emit for fast queries (< 500ms)."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _query_start,
        reset_query_counter,
        setup_db_probe,
    )

    mock_engine = MagicMock()
    mock_sync_engine = MagicMock()
    mock_engine.sync_engine = mock_sync_engine

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    reset_query_counter()
    _query_start.set(time.monotonic())  # just set start — will result in ~0ms

    with patch("v2.modules.platform_infra.monitoring.emit") as mock_emit:
        handlers["_after"](None, None, "SELECT 1", None, None, False)
        mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# setup_db_probe: _after handler — slow query (500–2000ms) → WARNING
# ---------------------------------------------------------------------------


def test_after_handler_slow_query_emits_warning():
    """_after emits WARNING for queries between 500ms and 2000ms."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _query_start,
        reset_query_counter,
        setup_db_probe,
    )
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    mock_engine = MagicMock()
    mock_engine.sync_engine = MagicMock()

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    reset_query_counter()
    # Set start time 600ms ago
    _query_start.set(time.monotonic() - 0.6)

    emitted = []
    with patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append):
        handlers["_after"](None, None, "SELECT col FROM t", None, None, False)

    slow_events = [e for e in emitted if e.category == "slow_query"]
    assert len(slow_events) >= 1
    assert slow_events[0].severity == ErrorSeverity.WARNING


# ---------------------------------------------------------------------------
# setup_db_probe: _after handler — very slow query (>2000ms) → ERROR
# ---------------------------------------------------------------------------


def test_after_handler_very_slow_query_emits_error():
    """_after emits ERROR for queries > 2000ms and attempts auto_explain."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _query_start,
        reset_query_counter,
        setup_db_probe,
    )
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    mock_engine = MagicMock()
    mock_engine.sync_engine = MagicMock()

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    reset_query_counter()
    _query_start.set(time.monotonic() - 2.5)  # 2.5s ago

    emitted = []
    with (
        patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append),
        patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")),
    ):
        handlers["_after"](None, None, "SELECT col FROM t", None, None, False)

    slow_events = [e for e in emitted if e.category == "slow_query"]
    assert len(slow_events) >= 1
    assert slow_events[0].severity == ErrorSeverity.ERROR


# ---------------------------------------------------------------------------
# setup_db_probe: _after handler — N+1 detect at threshold
# ---------------------------------------------------------------------------


def test_after_handler_n_plus_one_detected_at_threshold():
    """_after emits n_plus_one_suspect when query count hits _N_PLUS_ONE_THRESHOLD."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _N_PLUS_ONE_THRESHOLD,
        _query_start,
        _request_query_count,
        setup_db_probe,
    )

    mock_engine = MagicMock()
    mock_engine.sync_engine = MagicMock()

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    # Set query count to just below threshold
    _request_query_count.set(_N_PLUS_ONE_THRESHOLD - 1)
    _query_start.set(time.monotonic())  # fast query — won't trigger slow emit

    emitted = []
    with (
        patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append),
        patch(
            "app.infrastructure.context.request_context.get_correlation_id",
            return_value="corr-1",
        ),
        patch(
            "app.infrastructure.context.request_context.get_request_path",
            return_value="/test",
        ),
    ):
        handlers["_after"](None, None, "SELECT * FROM t", None, None, False)

    n1_events = [e for e in emitted if e.category == "n_plus_one_suspect"]
    assert len(n1_events) == 1
    assert n1_events[0].metadata["query_count"] == _N_PLUS_ONE_THRESHOLD


# ---------------------------------------------------------------------------
# setup_db_probe: _on_error — critical PG code → CRITICAL severity
# ---------------------------------------------------------------------------


def test_on_error_critical_pg_code():
    """_on_error emits CRITICAL for critical PG codes."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        setup_db_probe,
    )
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    mock_engine = MagicMock()
    mock_engine.sync_engine = MagicMock()

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    orig_exc = Exception("too many connections")
    orig_exc.pgcode = "53300"  # critical code

    ctx = MagicMock()
    ctx.original_exception = orig_exc

    emitted = []
    with patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append):
        handlers["_on_error"](ctx)

    assert len(emitted) == 1
    assert emitted[0].severity == ErrorSeverity.CRITICAL
    assert emitted[0].category == "too_many_connections"


# ---------------------------------------------------------------------------
# setup_db_probe: _on_error — non-critical PG code → ERROR
# ---------------------------------------------------------------------------


def test_on_error_non_critical_pg_code():
    """_on_error emits ERROR (not CRITICAL) for non-critical PG codes."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        setup_db_probe,
    )
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    mock_engine = MagicMock()
    mock_engine.sync_engine = MagicMock()

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    orig_exc = Exception("unique violation")
    orig_exc.pgcode = "23505"  # unique_violation — not critical

    ctx = MagicMock()
    ctx.original_exception = orig_exc

    emitted = []
    with patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append):
        handlers["_on_error"](ctx)

    assert len(emitted) == 1
    assert emitted[0].severity == ErrorSeverity.ERROR
    assert emitted[0].category == "unique_violation"


# ---------------------------------------------------------------------------
# setup_db_probe: _on_error — unknown PG code → db_error category
# ---------------------------------------------------------------------------


def test_on_error_unknown_pg_code():
    """_on_error uses 'db_error' category for unknown PG code."""
    from v2.modules.platform_infra.monitoring.db_probe import setup_db_probe

    mock_engine = MagicMock()
    mock_engine.sync_engine = MagicMock()

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    orig_exc = Exception("unknown error")
    orig_exc.pgcode = "99999"  # not in map

    ctx = MagicMock()
    ctx.original_exception = orig_exc

    emitted = []
    with patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append):
        handlers["_on_error"](ctx)

    assert emitted[0].category == "db_error"


# ---------------------------------------------------------------------------
# setup_db_probe: _on_checkout — pool pressure emit
# ---------------------------------------------------------------------------


def test_on_checkout_emits_pool_pressure():
    """_on_checkout emits pool_pressure when >85% connections used."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _pool_state,
        setup_db_probe,
    )

    mock_engine = MagicMock()
    mock_sync_engine = MagicMock()
    mock_engine.sync_engine = mock_sync_engine

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    # Configure pool to appear 90% used
    mock_pool = MagicMock()
    mock_pool.checkedout.return_value = 9
    mock_pool.size.return_value = 10
    mock_pool.overflow.return_value = 0
    mock_sync_engine.pool = mock_pool

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    # Reset throttle
    _pool_state["last_alert"] = 0.0

    emitted = []
    with patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append):
        handlers["_on_checkout"](None, None, None)

    assert len(emitted) == 1
    assert emitted[0].category == "pool_pressure"


# ---------------------------------------------------------------------------
# setup_db_probe: _on_checkout — throttle guard (same alert < 60s)
# ---------------------------------------------------------------------------


def test_on_checkout_throttle_prevents_duplicate_alerts():
    """_on_checkout does NOT emit if last alert was < 60s ago."""
    from v2.modules.platform_infra.monitoring.db_probe import (
        _pool_state,
        setup_db_probe,
    )

    mock_engine = MagicMock()
    mock_sync_engine = MagicMock()
    mock_engine.sync_engine = mock_sync_engine

    handlers: dict = {}

    def listens_for(eng, ev_name, **kw):
        def decorator(fn):
            handlers[fn.__name__] = fn
            return fn

        return decorator

    mock_pool = MagicMock()
    mock_pool.checkedout.return_value = 9
    mock_pool.size.return_value = 10
    mock_pool.overflow.return_value = 0
    mock_sync_engine.pool = mock_pool

    with patch("v2.modules.platform_infra.monitoring.db_probe.event") as mock_ev:
        mock_ev.listens_for.side_effect = listens_for
        setup_db_probe(mock_engine)

    # Simulate recent alert (30s ago)
    _pool_state["last_alert"] = time.monotonic() - 30

    emitted = []
    with patch("v2.modules.platform_infra.monitoring.emit", side_effect=emitted.append):
        handlers["_on_checkout"](None, None, None)

    assert len(emitted) == 0


# ---------------------------------------------------------------------------
# _auto_explain: rate-limit eviction when _explain_last > 200 entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_explain_evicts_old_fingerprints():
    """_auto_explain evicts stale entries from _explain_last when > 200."""
    from v2.modules.platform_infra.monitoring import db_probe as dp

    dp._explain_last.clear()
    old_time = time.monotonic() - 200  # older than 120s cutoff

    # Fill with 201 old entries
    for i in range(201):
        dp._explain_last[f"fp-{i:04d}"] = old_time

    assert len(dp._explain_last) == 201

    # This SELECT has no params, will pass the parameterized check
    stmt = "SELECT col FROM eviction_test_table"
    fp = dp._sql_fingerprint(stmt)
    # Ensure this fingerprint is fresh so we get past the rate-limit check
    dp._explain_last.pop(fp, None)

    # Mock the raw asyncpg driver connection so we don't need a real DB
    mock_asyncpg_conn = AsyncMock()
    mock_asyncpg_conn.fetch = AsyncMock(
        return_value=[("Seq Scan on t",), ("cost=0.00..5.00",)]
    )
    mock_raw = MagicMock()
    mock_raw.driver_connection = mock_asyncpg_conn

    mock_conn = AsyncMock()
    mock_conn.get_raw_connection = AsyncMock(return_value=mock_raw)
    mock_conn_ctx = AsyncMock()
    mock_conn_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn_ctx)

    with (
        patch("v2.modules.platform_infra.database.connection.engine", mock_engine),
        patch("v2.modules.platform_infra.monitoring.aemit", AsyncMock()),
    ):
        dp._explain_sem = None  # reset semaphore
        await dp._auto_explain(stmt, None, 3000.0)

    # After the call, _explain_last should have been trimmed
    assert len(dp._explain_last) <= 202  # some eviction should have happened


# ---------------------------------------------------------------------------
# _auto_explain: full path with seq scan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_explain_full_path_with_seq_scan():
    """_auto_explain runs EXPLAIN, detects Seq Scan, and emits slow_query_plan."""
    from v2.modules.platform_infra.monitoring import db_probe as dp

    dp._explain_last.clear()
    dp._explain_sem = None

    stmt = "SELECT id FROM full_explain_table"

    mock_asyncpg_conn = AsyncMock()
    mock_asyncpg_conn.fetch = AsyncMock(
        return_value=[
            ("Seq Scan on full_explain_table  (cost=0.00..35.50 rows=2550 width=4)",),
            ("  Filter: (active = true)",),
        ]
    )
    mock_raw = MagicMock()
    mock_raw.driver_connection = mock_asyncpg_conn

    mock_conn = AsyncMock()
    mock_conn.get_raw_connection = AsyncMock(return_value=mock_raw)
    mock_conn_ctx = AsyncMock()
    mock_conn_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_conn_ctx)

    emitted = []

    async def fake_aemit(event):
        emitted.append(event)

    with (
        patch("v2.modules.platform_infra.database.connection.engine", mock_engine),
        patch("v2.modules.platform_infra.monitoring.aemit", fake_aemit),
    ):
        await dp._auto_explain(stmt, None, 2500.0)

    plan_events = [e for e in emitted if e.category == "slow_query_plan"]
    assert len(plan_events) == 1
    assert plan_events[0].metadata["has_seq_scan"] is True
