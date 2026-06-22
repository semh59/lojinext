"""Coverage tests for app/infrastructure/monitoring/db_probe.py"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

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
# _auto_explain — skips parameterised & non-SELECT statements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_explain_skips_parameterised():
    from app.infrastructure.monitoring.db_probe import _auto_explain

    # Statement with :param → should return early, no session
    await _auto_explain("SELECT * FROM t WHERE id = :id", {"id": 1}, 3000.0)
    # No error means it returned early silently


@pytest.mark.asyncio
async def test_auto_explain_skips_non_select():
    from app.infrastructure.monitoring.db_probe import _auto_explain

    await _auto_explain("UPDATE t SET col=1", None, 3000.0)
    # Should return early, no crash


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
