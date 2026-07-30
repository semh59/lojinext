"""FAZ2 Wave 2 — per-request/per-task PostgreSQL module-role context.

This module only holds a `ContextVar` plus the helpers that read/write it —
the code that actually sends `SET LOCAL ROLE` to Postgres lives in
`connection.py`'s SQLAlchemy `after_begin` event listener (a single hook
that covers every `AsyncSessionLocal()` creation path — see the spike
recorded in TASKS/faz2-db-rol-izolasyonu-ve-read-model-grantlari.md).

Three entry points:
  - `require_module_role(module_name)` — FastAPI `Depends(...)`, wired into
    `api_router.py`'s `include_router()` calls for every business module.
  - `setup_celery_module_role_signals()` — connects `task_prerun`/
    `task_postrun` Celery signals, called once from `celery_app.py` at
    worker-process startup (`@worker_process_init.connect`).
  - `open_role_scoped_session(role)` — for maintenance scripts running
    outside FastAPI/Celery, wired into each script's own session-open call.
"""

from __future__ import annotations

import contextvars
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Optional

from v2.modules.platform_infra.database.role_grants import (
    ALL_ROLES,
    MODULE_SCHEMA_ROLES,
)

# Business module name (e.g. "trip") -> PostgreSQL role (e.g. "m_trip"). The
# two schema-less read-model modules aren't in MODULE_SCHEMA_ROLES, added here.
MODULE_ROLE_MAP: dict[str, str] = {
    **MODULE_SCHEMA_ROLES,
    "analytics_executive": "m_analytics_executive",
    "ai_assistant": "m_ai_assistant",
}

# Celery task name -> owning business-module name (a MODULE_ROLE_MAP key).
# NOT derivable from the task name's own prefix -- several task-name prefixes
# are misleading relative to the module that actually owns the task file:
# "analytics.*" -> reports (not "analytics"), "compliance.*" ->
# analytics_executive (not "compliance"), "ocr.*" -> import_excel (not
# "ocr"), "ml.*" -> prediction_ml (not "ml"). Hand-maintained; add a new
# entry whenever a new @celery_app.task is registered in a business module.
TASK_NAME_TO_MODULE: dict[str, str] = {
    "prediction.drain_dlq": "prediction_ml",
    "monitoring.fuel_coverage_check": "fuel",
    "coaching.weekly_digest": "driver",
    "coaching.evaluate_pending": "driver",
    "theft.daily_pattern_scan": "anomaly",
    "ml.weekly_retrain_all_vehicles": "prediction_ml",
    "prediction.backfill_missing": "prediction_ml",
    "analytics.prune_page_views": "reports",
    "compliance.inspection_push": "analytics_executive",
    "notifications.weekly_digest": "notification",
    "anomaly.cluster_scan": "anomaly",
    "ocr.process_belge": "import_excel",
    "prediction.generate": "prediction_ml",
}
# Deliberately unmapped -- platform-wide tasks with no single owning business
# module (outbox relay reads every module's outbox rows; the two monitoring
# tasks and the two backup tasks touch cross-cutting/system tables, not one
# module's schema): infrastructure.relay_outbox_events, monitoring.error_
# digest, monitoring.create_monthly_partition, monitoring.db_health_check,
# infrastructure.db_backup, infrastructure.db_backup_verify. These run with
# module_role unset (today's behavior -- full login-role privilege).

_module_role: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "module_role", default=None
)


def get_module_role() -> Optional[str]:
    """Read by `connection.py`'s after_begin listener."""
    return _module_role.get()


@contextmanager
def module_role_scope(role: str) -> Iterator[None]:
    """Makes `role` the active PostgreSQL role for the block's lifetime.

    Raises immediately on an unknown role (typo/wrong module name) instead
    of silently connecting with the widest-available privilege.
    """
    if role not in ALL_ROLES:
        raise ValueError(f"Unknown PostgreSQL module role: {role!r}")
    token = _module_role.set(role)
    try:
        yield
    finally:
        _module_role.reset(token)


def require_module_role(module_name: str):
    """FastAPI dependency factory — `Depends(require_module_role("trip"))`."""
    role = MODULE_ROLE_MAP[module_name]

    async def _dependency() -> AsyncIterator[None]:
        with module_role_scope(role):
            yield

    return _dependency


@asynccontextmanager
async def open_role_scoped_session(role: str):
    """For maintenance scripts (outside FastAPI/Celery): returns an
    `AsyncSession` already scoped to the given role."""
    from v2.modules.platform_infra.database.connection import AsyncSessionLocal

    with module_role_scope(role):
        async with AsyncSessionLocal() as session:
            yield session


# task_id -> Token, mirroring celery_probe.py's task_id-keyed
# `_task_start_times` dict. A single "current token" variable is NOT safe
# here: task_postrun must reset the exact token task_prerun created for its
# own task_id, not whatever the most-recently-started task set, in case two
# tasks' pre/postrun handlers ever interleave on the same worker child
# process.
_role_tokens: dict[str, contextvars.Token] = {}


def setup_celery_module_role_signals() -> None:
    """Connect Celery `task_prerun`/`task_postrun` signals. Call once at
    worker-process startup (`@worker_process_init.connect`, celery_app.py).

    `task_prerun`/`task_postrun` are synchronous Celery signals, fired in
    the same OS thread/logical context that the task body's own
    `asyncio.run(...)` call executes in -- `contextvars.ContextVar.set()`
    done here is visible inside that later async code (asyncio.run copies
    the calling thread's Context into the new event loop's initial task),
    the same mechanism `require_module_role`'s FastAPI dependency already
    relies on.
    """
    from celery.signals import task_postrun, task_prerun

    # weak=False is required: `.connect()` defaults to a WEAK reference to
    # the receiver, and `_on_prerun`/`_on_postrun` are local closures with
    # no other strong reference once this function returns -- without
    # weak=False they get garbage-collected almost immediately, silently
    # turning every subsequent real task_prerun/task_postrun signal into a
    # no-op (found live, 2026-07-30: a new unit test sending these signals
    # directly proved the connected receiver was already a dead weakref by
    # the time the signal fired, meaning Celery-task role-scoping likely
    # never actually applied in production since this wiring was added).
    @task_prerun.connect(weak=False)
    def _on_prerun(task_id: str, task, **_):
        module_name = TASK_NAME_TO_MODULE.get(task.name)
        if module_name is None:
            return
        role = MODULE_ROLE_MAP[module_name]
        _role_tokens[task_id] = _module_role.set(role)

    @task_postrun.connect(weak=False)
    def _on_postrun(task_id: str, task, **_):
        token = _role_tokens.pop(task_id, None)
        if token is not None:
            _module_role.reset(token)
