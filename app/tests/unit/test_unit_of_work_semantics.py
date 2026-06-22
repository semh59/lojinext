"""UnitOfWork commit-semantics contract tests (ARCH-012).

These lock in the EXPLICIT-commit contract that the module docstring documents:
clean exit without a commit does NOT persist pending writes — the ghost
transaction guard rolls them back loudly. Pure-mock, no DB → deterministic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.database.db_session import _session_ctx
from app.database.unit_of_work import UnitOfWork

pytestmark = pytest.mark.unit


def _mock_session(*, new=(), dirty=(), deleted=()):
    session = AsyncMock()
    session.new = list(new)
    session.dirty = list(dirty)
    session.deleted = list(deleted)
    session.info = {}
    return session


def _patch_session_factory(monkeypatch, session):
    """Force an owning UoW (no ambient contextual session) backed by `session`."""
    monkeypatch.setattr("app.database.unit_of_work.AsyncSessionLocal", lambda: session)
    token = _session_ctx.set(None)
    return token


async def test_clean_exit_without_commit_rolls_back_pending(monkeypatch):
    """Forgetting commit() with staged writes → ghost guard rolls back, never
    commits. This is the contract the docstring promises."""
    session = _mock_session(new=[object()])
    token = _patch_session_factory(monkeypatch, session)
    try:
        async with UnitOfWork():
            pass  # staged a write (session.new) but never called commit()
    finally:
        _session_ctx.reset(token)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.close.assert_awaited_once()


async def test_clean_exit_read_only_neither_commits_nor_rolls_back(monkeypatch):
    """No pending writes → just close; no spurious rollback or commit."""
    session = _mock_session()  # empty new/dirty/deleted
    token = _patch_session_factory(monkeypatch, session)
    try:
        async with UnitOfWork():
            pass
    finally:
        _session_ctx.reset(token)

    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


async def test_explicit_commit_persists(monkeypatch):
    """await uow.commit() commits exactly once and skips the ghost rollback."""
    session = _mock_session(new=[object()])
    token = _patch_session_factory(monkeypatch, session)
    try:
        async with UnitOfWork() as uow:
            await uow.commit()
    finally:
        _session_ctx.reset(token)

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


async def test_exception_inside_block_rolls_back(monkeypatch):
    """An exception inside the block triggers automatic rollback and propagates."""
    session = _mock_session(new=[object()])
    token = _patch_session_factory(monkeypatch, session)
    try:
        with pytest.raises(ValueError):
            async with UnitOfWork():
                raise ValueError("boom")
    finally:
        _session_ctx.reset(token)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.close.assert_awaited_once()
