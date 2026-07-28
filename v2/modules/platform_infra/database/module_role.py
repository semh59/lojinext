"""FAZ2 Wave 2 — per-request/per-task PostgreSQL module-role context.

This module only holds a `ContextVar` plus the helpers that read/write it —
the code that actually sends `SET LOCAL ROLE` to Postgres lives in
`connection.py`'s SQLAlchemy `after_begin` event listener (a single hook
that covers every `AsyncSessionLocal()` creation path — see the spike
recorded in TASKS/faz2-db-rol-izolasyonu-ve-read-model-grantlari.md).

Three entry points:
  - `require_module_role(module_name)` — FastAPI `Depends(...)`, wired into
    `api_router.py`'s `include_router()` calls (not wired yet — separate step).
  - Celery `task_prerun`/`task_postrun` signal — uses `module_role_scope`
    directly (not wired yet — separate step).
  - `open_role_scoped_session(role)` — for maintenance scripts running
    outside FastAPI/Celery (not wired into any script yet — separate step).
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
