"""
Canonical Unit of Work entrypoint.
Core katmanda concrete UoW'yu yeniden ihrac eder.
"""

from contextlib import asynccontextmanager

from app.database.unit_of_work import UnitOfWork


@asynccontextmanager
async def get_uow():
    """
    Backward-compatible async context manager.

    Bazi eski kod/testler `async with get_uow() as uow` kullaniyor.
    FastAPI dependency tarafi icin `app.database.unit_of_work.get_uow` kullanilmali.
    """
    async with UnitOfWork() as uow:
        yield uow


__all__ = ["UnitOfWork", "get_uow"]
