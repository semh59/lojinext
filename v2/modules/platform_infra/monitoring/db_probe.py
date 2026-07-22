from __future__ import annotations

import asyncio
import re
import time
from contextvars import ContextVar
from hashlib import blake2b

from sqlalchemy import event
from sqlalchemy.engine import ExceptionContext
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.logging.logger import get_logger
from v2.modules.platform_infra.monitoring.models import (
    ErrorEvent,
    ErrorLayer,
    ErrorSeverity,
)

logger = get_logger(__name__)

_pool_state: dict[str, float] = {"last_alert": 0.0}
# Throttle auto-explain: at most one concurrent EXPLAIN + once per fingerprint per 60s
_explain_sem = None  # asyncio.Semaphore — lazily created inside async context
_explain_last: dict[str, float] = {}
_db_bg_tasks: set = set()

_NUM_RE = re.compile(r"\b\d+\b")
_STR_RE = re.compile(r"'[^']*'")
_IN_RE = re.compile(r"IN\s*\([^)]+\)", re.I)


def _sql_fingerprint(stmt: str) -> str:
    try:
        import sqlparse

        normalized = sqlparse.format(stmt, strip_whitespace=True, keyword_case="upper")
    except Exception:
        normalized = stmt.upper()
    normalized = _IN_RE.sub("IN (?)", normalized)
    normalized = _NUM_RE.sub("?", normalized)
    normalized = _STR_RE.sub("?", normalized)
    return blake2b(normalized.encode(), digest_size=6).hexdigest()


_PG_CODE_MAP: dict[str, str] = {
    "40001": "deadlock",
    "40P01": "deadlock",
    "23505": "unique_violation",
    "23503": "fk_violation",
    "23502": "not_null_violation",
    "23514": "check_violation",
    "23000": "integrity_error",
    "53300": "too_many_connections",
    "53200": "out_of_memory",
    "57P03": "db_unavailable",
    "08006": "connection_failure",
    "55P03": "lock_not_available",
    "57014": "query_cancelled",
    "42P01": "undefined_table",
    "42703": "undefined_column",
}
_CRITICAL_PG_CODES = frozenset({"53300", "57P03", "40P01", "08006"})

_request_query_count: ContextVar[int] = ContextVar("request_query_count", default=0)
_query_start: ContextVar[float] = ContextVar("query_start", default=0.0)
# Son N SQL fingerprint'i — N+1 tetiklendiğinde root cause için sample
# (sadece son tek statement_fp endpoint'i tespit etmeye yetmiyor)
_recent_queries: ContextVar[list] = ContextVar("recent_queries", default=[])
_RECENT_QUERIES_KEEP = 8
_N_PLUS_ONE_THRESHOLD = 20


def reset_query_counter() -> None:
    _request_query_count.set(0)


def reset_recent_queries() -> None:
    _recent_queries.set([])


def get_query_count() -> int:
    return _request_query_count.get(0)


def setup_db_probe(engine: AsyncEngine) -> None:
    """Register all SQLAlchemy event listeners. Call once at startup."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, params, context, executemany):
        try:
            _query_start.set(time.monotonic())
        except Exception as exc:
            logger.debug("db_probe _before failed: %s", exc)

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, params, context, executemany):
        try:
            start = _query_start.get(0.0)
            if start == 0.0:
                return
            elapsed_ms = (time.monotonic() - start) * 1000

            count = _request_query_count.get(0) + 1
            _request_query_count.set(count)

            # Recent queries rolling buffer — root cause için (statement_fp
            # + ilk 200 char SQL). Dedektör öz-kirliliği filtresi: emit()
            # zinciri kendi ErrorEvent'lerini `error_events` tablosuna
            # INSERT'liyor; bu INSERT'ler tampona girerse N+1 raporundaki
            # recent_queries örnekleri dedektörün KENDİ yazımlarıyla dolup
            # asıl suçlu SQL'leri dışarı itiyor (kanıt: LOJINEXT-17A
            # event'lerinin recent_queries'i kendi INSERT INTO error_events
            # satırını içeriyordu). Basit substring kontrolü yeterli;
            # sayaç (query_count) davranışına DOKUNULMUYOR — sadece tampon
            # örnekleri temiz tutuluyor.
            current_fp = _sql_fingerprint(statement)
            stmt_str = statement if isinstance(statement, str) else str(statement)
            if "error_events" not in stmt_str:
                recent = _recent_queries.get([])
                recent = (recent + [{"fp": current_fp, "sql": stmt_str[:200]}])[
                    -_RECENT_QUERIES_KEEP:
                ]
                _recent_queries.set(recent)
            else:
                recent = _recent_queries.get([])

            if count == _N_PLUS_ONE_THRESHOLD:
                from app.infrastructure.context.request_context import (
                    get_correlation_id,
                    get_request_path,
                )
                from v2.modules.platform_infra.monitoring import emit

                emit(
                    ErrorEvent(
                        layer=ErrorLayer.DB,
                        category="n_plus_one_suspect",
                        severity=ErrorSeverity.WARNING,
                        message=f"N+1 suspect: {count} queries in single request",
                        # Request context — UI'da trace tıklayıp endpoint'i
                        # ve son SQL'leri görmek için
                        trace_id=get_correlation_id(),
                        path=get_request_path(),
                        metadata={
                            "query_count": count,
                            "statement_fp": current_fp,
                            "recent_queries": recent,
                        },
                    )
                )

            if elapsed_ms < 500:
                return
            severity = (
                ErrorSeverity.ERROR if elapsed_ms > 2000 else ErrorSeverity.WARNING
            )
            fp = _sql_fingerprint(statement)
            from v2.modules.platform_infra.monitoring import emit

            emit(
                ErrorEvent(
                    layer=ErrorLayer.DB,
                    category="slow_query",
                    severity=severity,
                    message=f"Slow query: {elapsed_ms:.0f}ms",
                    metadata={"query_ms": round(elapsed_ms, 1), "statement_fp": fp},
                )
            )

            if elapsed_ms > 2000:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(
                        _auto_explain(statement, params, elapsed_ms, executemany),
                        name="auto-explain",
                    )
                    _db_bg_tasks.add(task)
                    task.add_done_callback(_db_bg_tasks.discard)
                except RuntimeError:
                    pass
        except Exception as exc:
            logger.debug("db_probe _after failed: %s", exc)

    @event.listens_for(sync_engine, "handle_error")
    def _on_error(ctx: ExceptionContext):
        try:
            orig = ctx.original_exception
            pg_code = getattr(orig, "pgcode", None)
            category = _PG_CODE_MAP.get(pg_code or "", "db_error")
            severity = (
                ErrorSeverity.CRITICAL
                if pg_code in _CRITICAL_PG_CODES
                else ErrorSeverity.ERROR
            )
            from v2.modules.platform_infra.monitoring import emit

            emit(
                ErrorEvent(
                    layer=ErrorLayer.DB,
                    category=category,
                    severity=severity,
                    message=f"{type(orig).__name__}: {str(orig)[:300]}",
                    metadata={
                        "pg_code": pg_code,
                        "exception_type": type(orig).__name__,
                    },
                )
            )
        except Exception as exc:
            logger.debug("db_probe _on_error failed: %s", exc)

    @event.listens_for(sync_engine, "checkout")
    def _on_checkout(dbapi_conn, conn_record, conn_proxy):
        try:
            pool = sync_engine.pool
            checked_out = pool.checkedout()
            size = pool.size()
            if size > 0 and checked_out / size > 0.85:
                now = time.monotonic()
                if now - _pool_state["last_alert"] < 60:
                    return
                _pool_state["last_alert"] = now
                from v2.modules.platform_infra.monitoring import emit

                emit(
                    ErrorEvent(
                        layer=ErrorLayer.DB,
                        category="pool_pressure",
                        severity=ErrorSeverity.ERROR,
                        message=(
                            f"Connection pool {checked_out}/{size}"
                            f" ({100 * checked_out // size}% used)"
                        ),
                        metadata={
                            "checked_out": checked_out,
                            "pool_size": size,
                            "overflow": pool.overflow(),
                        },
                    )
                )
        except Exception as exc:
            logger.debug("db_probe _on_checkout failed: %s", exc)

    logger.info("DB probe activated")


async def _auto_explain(
    statement: str, params, elapsed_ms: float, executemany: bool = False
) -> None:
    """Re-run the slow statement as ``EXPLAIN (ANALYZE FALSE)`` and record the plan.

    Previously this bailed out on ANY parameterized statement
    (``:\\w+|\\$\\d+|\\?``) — but the asyncpg dialect's paramstyle is
    ``numeric_dollar`` (SQLAlchemy compiles every bound query to ``$1, $2,
    ...`` before it reaches this hook), so that regex matched essentially
    every real query the app runs. In practice `_auto_explain` never
    captured a plan for anything but literal, unparameterized SQL — dead
    code for the actual slow-query population (confirmed live: a genuine
    8.5s query on 2026-07-10 produced a "slow_query" ErrorEvent but no
    matching "slow_query_plan" one).

    Fix: `$1, $2, ...` positional placeholders + a params sequence is
    exactly asyncpg's own native calling convention (``Connection.fetch(sql,
    *args)``) — no translation needed. Grab the raw asyncpg driver
    connection off a fresh pooled connection (dedicated to this EXPLAIN,
    never the request's own in-flight connection/cursor) and call it
    directly, bypassing SQLAlchemy's text()/bindparam layer (which only
    understands ``:name`` style and would require reparsing the
    already-compiled positional SQL to translate it back).
    """
    global _explain_sem
    try:
        # executemany params is a list-of-tuples (one per batch row) — not a
        # single parameter set, and re-EXPLAINing an INSERT/UPDATE batch
        # isn't the point of this diagnostic anyway (SELECT-only, see below).
        if executemany:
            return

        clean = statement.strip().upper()
        if not clean.startswith("SELECT"):
            return

        # Rate-limit: once per unique fingerprint per 60s, max 1 concurrent
        fp = _sql_fingerprint(statement)
        now = time.monotonic()
        if now - _explain_last.get(fp, 0.0) < 60.0:
            return
        _explain_last[fp] = now
        # Evict old entries to prevent unbounded growth
        if len(_explain_last) > 200:
            cutoff = now - 120.0
            for k in [k for k, v in _explain_last.items() if v < cutoff]:
                _explain_last.pop(k, None)

        if _explain_sem is None:
            _explain_sem = asyncio.Semaphore(1)
        if _explain_sem.locked():  # already running one EXPLAIN — skip
            return

        if params is None:
            args: tuple = ()
        elif isinstance(params, (list, tuple)):
            args = tuple(params)
        else:
            # Unexpected paramstyle (shouldn't happen on the asyncpg
            # dialect's numeric_dollar compiler) — don't guess, skip.
            logger.debug(
                "Auto EXPLAIN skipped: unexpected params type %s for fp=%s",
                type(params).__name__,
                fp,
            )
            return

        async with _explain_sem:
            from v2.modules.platform_infra.database.connection import engine

            async with engine.connect() as conn:
                raw = await conn.get_raw_connection()
                asyncpg_conn = raw.driver_connection
                rows = await asyncpg_conn.fetch(
                    f"EXPLAIN (ANALYZE FALSE, FORMAT TEXT) {statement}", *args
                )
                plan_lines = [row[0] for row in rows]
                plan_text = "\n".join(plan_lines[:20])

            seq_scan = any("Seq Scan" in line for line in plan_lines)
            from v2.modules.platform_infra.monitoring import aemit

            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.DB,
                    category="slow_query_plan",
                    severity=ErrorSeverity.WARNING,
                    message=f"EXPLAIN for {elapsed_ms:.0f}ms query",
                    metadata={
                        "query_ms": round(elapsed_ms, 1),
                        "has_seq_scan": seq_scan,
                        "plan_excerpt": plan_text[:500],
                        "statement_fp": fp,
                    },
                )
            )
    except Exception as exc:
        logger.debug("Auto EXPLAIN failed: %s", exc)
