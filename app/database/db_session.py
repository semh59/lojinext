"""Context-var-scoped async session helpers.

`_session_ctx` carries the current `AsyncSession` through nested awaits so
that a `UnitOfWork` can detect re-entry and reuse the same transaction.
"""

from __future__ import annotations

import contextvars
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import AsyncSessionLocal

_session_ctx: contextvars.ContextVar[Optional[AsyncSession]] = contextvars.ContextVar(
    "lojinext_db_session", default=None
)


@asynccontextmanager
async def get_async_session_context() -> AsyncIterator[AsyncSession]:
    """Yield the contextual session; create one if none is active.

    Reuses an existing session inside nested calls so that callers participate
    in the outer transaction. The owner (the call that created the session)
    commits on clean exit, otherwise rolls back.
    """
    existing = _session_ctx.get()
    if existing is not None:
        yield existing
        return

    async with AsyncSessionLocal() as session:
        token = _session_ctx.set(session)
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            _session_ctx.reset(token)
