"""Coverage tests for app/infrastructure/monitoring/db_probe.py"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _sql_fingerprint — already partially tested, extend coverage
# ---------------------------------------------------------------------------


def test_sql_fingerprint_normalises_in_clause():
    from app.infrastructure.monitoring.db_probe import _sql_fingerprint

    s1 = _sql_fingerprint("SELECT * FROM t WHERE id IN (1, 2, 3)")
    s2 = _sql_fingerprint("SELECT * FROM t WHERE id IN (10, 20, 30, 40)")
    assert s1 == s2  # both collapse to IN (?)


def test_sql_fingerprint_normalises_strings():
    from app.infrastructure.monitoring.db_probe import _sql_fingerprint

    s1 = _sql_fingerprint("SELECT * FROM t WHERE name = 'alice'")
    s2 = _sql_fingerprint("SELECT * FROM t WHERE name = 'bob'")
    assert s1 == s2


def test_sql_fingerprint_normalises_numbers():
    from app.infrastructure.monitoring.db_probe import _sql_fingerprint

    s1 = _sql_fingerprint("SELECT * FROM t WHERE id = 42")
    s2 = _sql_fingerprint("SELECT * FROM t WHERE id = 7")
    assert s1 == s2


def test_sql_fingerprint_different_tables():
    from app.infrastructure.monitoring.db_probe import _sql_fingerprint

    s1 = _sql_fingerprint("SELECT * FROM users WHERE id = 1")
    s2 = _sql_fingerprint("SELECT * FROM orders WHERE id = 1")
    assert s1 != s2


def test_sql_fingerprint_returns_hex_string():
    from app.infrastructure.monitoring.db_probe import _sql_fingerprint

    fp = _sql_fingerprint("SELECT 1")
    assert isinstance(fp, str)
    assert len(fp) == 12  # blake2b digest_size=6 → 12 hex chars


def test_sql_fingerprint_sqlparse_fallback(monkeypatch):
    """When sqlparse raises, raw normalisation is used."""
    import sys

    fake_sqlparse = MagicMock()
    fake_sqlparse.format.side_effect = RuntimeError("parse error")
    monkeypatch.setitem(sys.modules, "sqlparse", fake_sqlparse)
    from app.infrastructure.monitoring.db_probe import _sql_fingerprint

    fp = _sql_fingerprint("select * from t where id = 1")
    assert isinstance(fp, str)
    assert len(fp) == 12


# ---------------------------------------------------------------------------
# PG code map
# ---------------------------------------------------------------------------


def test_pg_code_map_completeness():
    from app.infrastructure.monitoring.db_probe import _PG_CODE_MAP

    required = {
        "40001": "deadlock",
        "40P01": "deadlock",
        "23505": "unique_violation",
        "23503": "fk_violation",
        "23502": "not_null_violation",
        "23514": "check_violation",
        "57014": "query_cancelled",
    }
    for code, expected in required.items():
        assert _PG_CODE_MAP[code] == expected


def test_critical_pg_codes_subset():
    from app.infrastructure.monitoring.db_probe import _CRITICAL_PG_CODES, _PG_CODE_MAP

    for code in _CRITICAL_PG_CODES:
        assert code in _PG_CODE_MAP, f"{code} is critical but not in _PG_CODE_MAP"


def test_non_critical_code_not_in_critical_set():
    from app.infrastructure.monitoring.db_probe import _CRITICAL_PG_CODES

    # unique_violation should NOT be critical
    assert "23505" not in _CRITICAL_PG_CODES


# ---------------------------------------------------------------------------
# ContextVar helpers
# ---------------------------------------------------------------------------


def test_reset_query_counter():
    from app.infrastructure.monitoring.db_probe import (
        _request_query_count,
        reset_query_counter,
    )

    _request_query_count.set(99)
    reset_query_counter()
    assert _request_query_count.get(0) == 0


def test_get_query_count_default_zero():
    from app.infrastructure.monitoring.db_probe import (
        get_query_count,
        reset_query_counter,
    )

    reset_query_counter()
    assert get_query_count() == 0


def test_get_query_count_after_set():
    from app.infrastructure.monitoring.db_probe import (
        _request_query_count,
        get_query_count,
    )

    _request_query_count.set(42)
    assert get_query_count() == 42


def test_reset_recent_queries():
    from app.infrastructure.monitoring.db_probe import (
        _recent_queries,
        reset_recent_queries,
    )

    _recent_queries.set([{"fp": "abc", "sql": "SELECT 1"}])
    reset_recent_queries()
    assert _recent_queries.get([]) == []


# ---------------------------------------------------------------------------
# _auto_explain — real asyncpg paramstyle (numeric_dollar) is NOT skipped;
# executemany and non-SELECT statements are.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_explain_runs_for_asyncpg_style_params():
    """Regression test: the old code skipped ANY parameterized statement via
    a regex (`:\\w+|\\$\\d+|\\?`) matching asyncpg's own `$1, $2, ...`
    compiled placeholders — meaning it never actually explained a real
    (parameterized) query in production. `$1` + a positional params tuple
    is asyncpg's native calling convention and must now be used directly,
    not skipped."""
    from app.infrastructure.monitoring import db_probe as dp

    dp._explain_last.clear()
    dp._explain_sem = None

    stmt = "SELECT * FROM t WHERE id = $1"

    mock_asyncpg_conn = AsyncMock()
    mock_asyncpg_conn.fetch = AsyncMock(return_value=[("Seq Scan on t",)])

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
        patch("app.infrastructure.monitoring.aemit", AsyncMock()),
    ):
        await dp._auto_explain(stmt, (1,), 3000.0)

    # The params tuple was forwarded as positional args to asyncpg's fetch,
    # exactly as asyncpg's own numeric_dollar paramstyle expects.
    mock_asyncpg_conn.fetch.assert_awaited_once()
    call_args = mock_asyncpg_conn.fetch.call_args
    assert call_args.args[0].startswith("EXPLAIN")
    assert call_args.args[1:] == (1,)


@pytest.mark.asyncio
async def test_auto_explain_skips_executemany():
    """executemany params are a list-of-tuples (one per batch row), not a
    single param set — re-EXPLAINing a batch insert isn't meaningful here."""
    from app.infrastructure.monitoring.db_probe import _auto_explain

    await _auto_explain(
        "SELECT * FROM t WHERE id = $1", [(1,), (2,)], 3000.0, executemany=True
    )
    # No error means it returned early without touching the DB


@pytest.mark.asyncio
async def test_auto_explain_skips_non_select():
    from app.infrastructure.monitoring.db_probe import _auto_explain

    await _auto_explain("UPDATE t SET col=1", None, 3000.0)
    # Should return early, no crash


@pytest.mark.asyncio
async def test_auto_explain_skips_unexpected_params_type():
    """Defensive guard: if params is neither None nor a list/tuple (the
    asyncpg dialect should never actually produce this), skip rather than
    guess how to call fetch()."""
    from app.infrastructure.monitoring.db_probe import _auto_explain

    await _auto_explain("SELECT * FROM t WHERE id = $1", {"id": 1}, 3000.0)
    # No error means it returned early without touching the DB


@pytest.mark.asyncio
async def test_auto_explain_rate_limits_same_fingerprint():
    from app.infrastructure.monitoring import db_probe as dp

    dp._explain_last.clear()
    stmt = "SELECT * FROM things"
    fp = dp._sql_fingerprint(stmt)
    # Mark as recently explained
    dp._explain_last[fp] = time.monotonic()

    # Should return early (rate limited) — no DB session needed
    await dp._auto_explain(stmt, None, 3000.0)
    # If it didn't raise, rate limit worked


@pytest.mark.asyncio
async def test_auto_explain_semaphore_locked():
    """When semaphore is already locked, _auto_explain bails out early."""
    from app.infrastructure.monitoring import db_probe as dp

    dp._explain_last.clear()
    dp._explain_sem = asyncio.Semaphore(1)

    stmt = "SELECT col FROM big_table"

    # Hold the semaphore in the background
    acquired = asyncio.Event()
    release = asyncio.Event()

    async def hold_sem():
        async with dp._explain_sem:
            acquired.set()
            await release.wait()

    task = asyncio.ensure_future(hold_sem())
    await acquired.wait()

    # Now semaphore is locked; _auto_explain should bail
    await dp._auto_explain(stmt, None, 3000.0)

    release.set()
    await task


# ---------------------------------------------------------------------------
# _pool_state initial value
# ---------------------------------------------------------------------------


def test_pool_state_initial_value():
    from app.infrastructure.monitoring.db_probe import _pool_state

    assert "last_alert" in _pool_state
    assert isinstance(_pool_state["last_alert"], float)


# ---------------------------------------------------------------------------
# N+1 / query count thresholds
# ---------------------------------------------------------------------------


def test_n_plus_one_threshold_value():
    from app.infrastructure.monitoring.db_probe import _N_PLUS_ONE_THRESHOLD

    assert _N_PLUS_ONE_THRESHOLD == 20


def test_recent_queries_keep_value():
    from app.infrastructure.monitoring.db_probe import _RECENT_QUERIES_KEEP

    assert _RECENT_QUERIES_KEEP == 8


# ---------------------------------------------------------------------------
# setup_db_probe — registration smoke test
# ---------------------------------------------------------------------------


def test_setup_db_probe_registers_listeners():
    """setup_db_probe attaches event listeners without raising."""
    from app.infrastructure.monitoring.db_probe import setup_db_probe

    mock_engine = MagicMock()
    mock_sync_engine = MagicMock()
    mock_engine.sync_engine = mock_sync_engine

    # event.listens_for is called internally; we patch it to avoid real SA setup
    with patch("app.infrastructure.monitoring.db_probe.event") as mock_event:
        mock_event.listens_for.return_value = lambda fn: fn  # decorator passthrough
        setup_db_probe(mock_engine)

    # Verify listens_for was called 4 times (before/after execute, handle_error, checkout)
    assert mock_event.listens_for.call_count == 4
