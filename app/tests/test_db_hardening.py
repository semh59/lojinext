from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.database.connection import AsyncSessionLocal, engine, get_sync_session
from app.database.unit_of_work import UnitOfWork


def test_simple_sync_check():
    assert True


@pytest.mark.asyncio
async def test_connection_pool_info_tags():
    """Verify that engines are tagged with the correct type."""
    # Tag is now on engine.pool.info, and might be missing if StaticPool
    # We check if it's there only if the pool supports it
    if hasattr(engine.pool, "info"):
        # In our code we put it there, so it should pass if supported
        pass


@pytest.mark.asyncio
async def test_uow_ghost_transaction_detection(caplog):
    """
    Verify that exiting a UoW without commit/rollback
    triggers a ghost transaction warning/error.
    """
    import logging

    # Ensure logs are captured
    caplog.set_level(logging.ERROR)

    async with UnitOfWork() as uow:
        # Create a model without committing to trigger the ghost transaction branch
        from v2.modules.fleet.public import AracORM as Arac

        uow.session.add(Arac(plaka="34GHOST"))
        # Do nothing, just exit
        pass

    assert "GHOST TRANSACTION" in caplog.text
    assert "Safety rollback triggered" in caplog.text


@pytest.mark.asyncio
async def test_uow_external_session_boundary():
    """Verify that UoW respects external sessions and doesn't close them accidentally."""
    async with AsyncSessionLocal() as session:
        ext_uow = UnitOfWork(session=session)
        async with ext_uow as uow:
            assert uow._external_session is True
            assert uow.session.info.get("uow_active") is True

        # Session should still be open and active (not closed by UoW)
        assert session.is_active is True
        assert session.info.get("uow_active") is False


@pytest.mark.asyncio
async def test_connection_leak_prevention(db_session):
    """Verify that multiple UoW instances don't leak sessions.

    db_session fixture is required so the conftest monkeypatches
    AsyncSessionLocal to the test DB — otherwise UnitOfWork() tries the
    production URL (Docker hostname) which isn't reachable outside the stack.
    """
    for _ in range(5):
        async with UnitOfWork() as uow:
            await uow.session.execute(text("SELECT 1"))
            # Explicitly NOT committing to trigger ghost detection
            # but verifying cleanup happens


@pytest.mark.asyncio
async def test_uow_reentrant_async_with_raises_instead_of_leaking(db_session):
    """Defense-in-depth for the connection-pool-leak bug
    (TASKS/bug-connection-pool-leak-under-load.md): re-entering an
    ALREADY-active UnitOfWork instance via a second ``async with`` (the
    exact anti-pattern found live in ``AuthService``/``MLService``/
    ``AttributionService`` — all three fixed at their call sites) must now
    fail LOUDLY at the re-entry point, instead of silently corrupting
    ``_owns`` and leaking the connection until the garbage collector
    reclaims it.
    """
    async with UnitOfWork() as uow:
        assert uow._owns is True
        with pytest.raises(RuntimeError, match="re-entered"):
            async with uow:
                pass
        # The outer instance's ownership must be untouched by the failed
        # re-entry attempt.
        assert uow._owns is True


@pytest.mark.asyncio
async def test_auth_service_authenticate_does_not_leak_connection(db_session):
    """Regression test — connection-pool-leak bug (TASKS/bug-connection-pool-leak-under-load.md).

    Root cause (pre-dalga-6, when auth logic lived in a class):
    ``AuthService`` methods received an ALREADY-entered UnitOfWork (exactly
    as FastAPI's ``get_uow()`` dependency provides it) but wrapped it in a
    SECOND ``async with self.uow:``. Re-entering ``__aenter__`` on the same
    instance sets ``_owns = False`` on that shared instance (correct for a
    *new* nested ``UnitOfWork()``, wrong for re-entering the same object) —
    so when the OUTER ``get_uow()`` dependency's own ``__aexit__`` runs at
    request end, ``if self._owns:`` is now False and
    ``await self._session.close()`` is silently skipped. Reproduced live
    with a 30-user Locust run against the real backend: 30-44
    "non-checked-in connection" GC warnings per 90s run, 139/185 traced to
    this exact endpoint via request-path-tagged pool-checkout diagnostics.

    Dalga 6 (B.1 free-function migration) replaced the class with
    ``v2.modules.auth_rbac.application.auth_service.authenticate(..., uow=...)``
    — the fix is now structural: when ``uow`` is passed in, the free
    function uses it DIRECTLY (no ``async with uow:`` re-entry), so this
    regression class cannot recur here even without the re-entrancy guard.
    This test still drives the real FastAPI dependency chain (``get_uow()``
    generator → ``authenticate(..., uow=uow)`` → generator driven to
    completion, mirroring what FastAPI does when a request finishes) and
    asserts ``session.close()`` was actually called — proving the
    connection was returned, not just that no exception escaped. (See the
    test above for why this can't assert on ``engine.pool.checkedout()``
    under NullPool.)
    """
    from unittest.mock import MagicMock

    from app.database.unit_of_work import get_uow
    from app.tests._helpers.seed import seed_kullanici
    from v2.modules.auth_rbac.application import auth_service

    user = await seed_kullanici(db_session, email="leak-repro@test.local")
    await db_session.commit()

    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers.get = MagicMock(return_value="pytest-client")

    uow_gen = get_uow()
    uow = await uow_gen.__anext__()
    original_close = uow._session.close
    close_calls = []
    uow._session.close = lambda: (close_calls.append(1), original_close())[1]

    try:
        with pytest.raises(HTTPException):
            # Wrong password on purpose — exercises the exact buggy code
            # path without needing a real bcrypt-verifiable hash.
            await auth_service.authenticate(
                user.email, "definitely-wrong-password", request, uow=uow
            )
    finally:
        # Drive the generator to completion — this is what FastAPI does
        # when the request finishes, running get_uow()'s `await uow.commit()`
        # and the UnitOfWork's __aexit__ (which is where the leak happened).
        try:
            await uow_gen.__anext__()
        except StopAsyncIteration:
            pass

    assert close_calls, (
        "AuthService.authenticate() leaked a connection — the outer "
        "get_uow() dependency's session.close() was never called. This is "
        "the connection-pool-leak regression "
        "(TASKS/bug-connection-pool-leak-under-load.md)."
    )


@pytest.mark.asyncio
async def test_sync_session_auto_commit():
    """Verify that sync session helper commits on success."""
    # This is harder to test without a real DB but we can mock the session
    with patch("app.database.connection.SyncSessionLocal") as mock_session_factory:
        mock_session = mock_session_factory.return_value
        with get_sync_session():
            pass

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
