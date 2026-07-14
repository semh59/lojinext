"""Unit of Work — single async transaction + lazily-bound repositories.

Commit is EXPLICIT — there is no auto-commit on clean exit. Callers that write
MUST call ``await uow.commit()`` themselves:

    async with UnitOfWork() as uow:
        arac = await uow.arac_repo.get_by_id(1)        # read — no commit needed
        await uow.sefer_repo.create(...)               # write — staged only
        await uow.commit()                             # <- required to persist

Exit semantics (owning UoW only):
  - Exception inside the block        → automatic rollback.
  - Clean exit WITHOUT a commit but with pending writes (new/dirty/deleted)
    → treated as a programmer error: a GHOST TRANSACTION error is logged and
      the session is rolled back, so forgetting ``commit()`` loses the writes
      loudly rather than committing or hanging silently.
  - Clean exit with no pending writes → just close (read-only usage).

Nested entry: if an outer UoW already opened a session in the same contextvar,
an inner ``async with UnitOfWork()`` reuses it without committing or closing —
the outermost owner controls the transaction lifecycle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Generic,
    Optional,
    TypeVar,
    overload,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import AsyncSessionLocal
from app.database.db_session import _session_ctx
from app.database.repositories import (
    AdminConfigRepository,
    AnalizRepository,
    AracRepository,
    AuditRepository,
    ConfigRepository,
    DorseRepository,
    ImportHistoryRepository,
    KullaniciRepository,
    LokasyonRepository,
    MaintenanceRepository,
    MLTrainingRepository,
    ModelVersiyonRepository,
    NotificationRepository,
    RolRepository,
    RouteRepository,
    SeferRepository,
    SessionRepository,
    SettingRepository,
    SoforRepository,
    YakitRepository,
)
from app.infrastructure.events.event_bus import EventBus, get_event_bus
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


_T = TypeVar("_T")


class _Lazy(Generic[_T]):
    """Typed lazy descriptor: build once on first access, cache on the instance.

    Generic over the factory's return type so ``uow.<x>_repo`` resolves to the
    concrete repository type (not ``Any``) — this keeps every repo method call
    on the UoW under mypy's eye.
    """

    def __init__(self, attr: str, factory: "Callable[[UnitOfWork], _T]") -> None:
        self._attr = attr
        self._factory = factory

    @overload
    def __get__(self, obj: None, objtype: Any = ...) -> "_Lazy[_T]": ...

    @overload
    def __get__(self, obj: "UnitOfWork", objtype: Any = ...) -> _T: ...

    def __get__(self, obj: "Optional[UnitOfWork]", objtype: Any = None) -> Any:
        if obj is None:
            return self
        cached = obj.__dict__.get(self._attr)
        if cached is None:
            cached = self._factory(obj)
            obj.__dict__[self._attr] = cached
        return cached


class UnitOfWork:
    """Async UoW. Owns one session per outermost entry; reuses on re-entry."""

    __slots__ = (
        "_session",
        "_owns",
        "_token",
        "_committed",
        "_rolled_back",
        "_external_session",
        "_entered",
        "__dict__",
    )

    def __init__(self, session: Optional[AsyncSession] = None) -> None:
        self._session: Optional[AsyncSession] = session
        self._owns = False
        self._token: Optional[Any] = None
        self._committed = False
        self._rolled_back = False
        # True when the session was injected externally (not created by this UoW)
        self._external_session: bool = session is not None
        # True while THIS instance's __aenter__ is currently active (not the
        # same as "has a session" — see __aenter__'s re-entrancy guard below).
        self._entered = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def __aenter__(self) -> "UnitOfWork":
        if self._entered:
            # A caller did `async with uow:` a SECOND time on the SAME
            # instance while it was still active (e.g. a service method
            # re-wrapping a uow that FastAPI's get_uow() dependency, or an
            # endpoint, already entered). This is NOT the supported nested
            # pattern — that requires a NEW `UnitOfWork()` instance, which
            # transparently joins the existing session via the contextvar
            # below (see the elif branch) without mutating this instance's
            # own `_owns`. Re-entering the SAME object flips `_owns` to
            # False on the OUTER owner too (same underlying `_owns` slot),
            # so its `__aexit__` silently skips `session.close()` — a
            # connection-pool leak, only surfaced later as SQLAlchemy's GC
            # "non-checked-in connection" warning under real concurrent
            # load (bkz. TASKS/bug-connection-pool-leak-under-load.md —
            # found live in `AuthService`, `MLService`, `AttributionService`).
            raise RuntimeError(
                "UnitOfWork instance re-entered via a second 'async with' "
                "on the SAME object. If you received an already-active "
                "`uow` (e.g. injected via FastAPI's get_uow() dependency, "
                "or passed into a service's __init__), use it directly — "
                "do NOT wrap it in another 'async with'. To share the "
                "active session across an independent call site instead, "
                "open a NEW `UnitOfWork()` there — it joins the existing "
                "session automatically."
            )
        self._entered = True
        existing = _session_ctx.get()
        if self._session is not None:
            self._owns = False
        elif existing is not None:
            self._session = existing
            self._owns = False
        else:
            self._session = AsyncSessionLocal()
            self._token = _session_ctx.set(self._session)
            self._owns = True
        # Mark session as active within a UoW so external code can detect it
        self._session.info["uow_active"] = True  # type: ignore[index]
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if not self._owns:
                # Nested (non-owning) UoW: if a DB error occurred inside, the shared
                # session is now in "pending rollback" state.  Rolling it back here
                # prevents PendingRollbackError on the next statement in the outer UoW.
                if exc_type is not None:
                    await self.rollback()
                return
            if exc_type is not None:
                await self.rollback()
            elif not (self._committed or self._rolled_back):
                # Ghost-transaction guard: if there are pending writes that were
                # never committed, treat it as a programmer error, log loudly,
                # and roll back to avoid silent data loss or partial mutations.
                session = self._session
                _has_pending = bool(
                    session is not None
                    and (session.new or session.dirty or session.deleted)
                )
                if _has_pending:
                    from app.infrastructure.logging.logger import get_logger as _gl

                    _log = _gl(__name__)
                    _log.error(
                        "GHOST TRANSACTION detected in UnitOfWork: session has "
                        "uncommitted changes (new=%d dirty=%d deleted=%d). "
                        "Safety rollback triggered.",
                        len(session.new),
                        len(session.dirty),
                        len(session.deleted),
                    )
                    await self.rollback()
                else:
                    # Clean exit (read-only usage): no writes → just close.
                    pass
        finally:
            # Clear the uow_active marker on the session before closing/releasing
            if self._session is not None:
                self._session.info["uow_active"] = False  # type: ignore[index]
            if self._owns:
                if self._token is not None:
                    _session_ctx.reset(self._token)
                await self._session.close()  # type: ignore[union-attr]
            self._entered = False
            self.__dict__.clear()

    # ── Transaction control ───────────────────────────────────────────────────
    async def commit(self) -> None:
        if self._session is None or self._committed or not self._owns:
            return
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self._session is None or self._rolled_back:
            return
        await self._session.rollback()
        self._rolled_back = True

    async def flush(self) -> None:
        if self._session is not None:
            await self._session.flush()

    # ── Session accessor ──────────────────────────────────────────────────────
    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active — use `async with`.")
        return self._session

    # ── Repositories (lazy, cached on the instance) ───────────────────────────
    arac_repo = _Lazy("arac_repo", lambda u: AracRepository(u.session))
    sefer_repo = _Lazy("sefer_repo", lambda u: SeferRepository(u.session))
    sofor_repo = _Lazy("sofor_repo", lambda u: SoforRepository(u.session))
    dorse_repo = _Lazy("dorse_repo", lambda u: DorseRepository(u.session))
    yakit_repo = _Lazy("yakit_repo", lambda u: YakitRepository(u.session))
    lokasyon_repo = _Lazy("lokasyon_repo", lambda u: LokasyonRepository(u.session))
    kullanici_repo = _Lazy("kullanici_repo", lambda u: KullaniciRepository(u.session))
    audit_repo = _Lazy("audit_repo", lambda u: AuditRepository(u.session))
    notification_repo = _Lazy(
        "notification_repo", lambda u: NotificationRepository(u.session)
    )
    setting_repo = _Lazy("setting_repo", lambda u: SettingRepository(u.session))
    maintenance_repo = _Lazy(
        "maintenance_repo", lambda u: MaintenanceRepository(u.session)
    )
    ml_training_repo = _Lazy(
        "ml_training_repo", lambda u: MLTrainingRepository(u.session)
    )
    model_versiyon_repo = _Lazy(
        "model_versiyon_repo", lambda u: ModelVersiyonRepository(u.session)
    )
    analiz_repo = _Lazy("analiz_repo", lambda u: AnalizRepository(u.session))
    admin_config_repo = _Lazy(
        "admin_config_repo", lambda u: AdminConfigRepository(u.session)
    )
    config_repo = _Lazy("config_repo", lambda u: ConfigRepository(u.session))
    import_repo = _Lazy("import_repo", lambda u: ImportHistoryRepository(u.session))
    session_repo = _Lazy("session_repo", lambda u: SessionRepository(u.session))
    rol_repo = _Lazy("rol_repo", lambda u: RolRepository(u.session))
    route_repo = _Lazy("route_repo", lambda u: RouteRepository(u.session))

    @property
    def event_bus(self) -> EventBus:
        return get_event_bus()


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    """FastAPI dependency: open a UoW for the request lifetime.

    Commit-on-success: the request UoW is the OUTERMOST owner, so it controls
    the transaction lifecycle (see module docstring). Service write methods that
    open their own ``async with UnitOfWork()`` become NON-owning nested UoWs when
    this dependency is active — their ``uow.commit()`` is a no-op (see
    ``UnitOfWork.commit``). Without committing here, those staged writes are
    rolled back on session close → silent data loss (observed on POST /fuel/,
    POST /drivers/). Committing after a clean ``yield`` persists them; any
    exception propagates into the ``async with`` and triggers rollback instead.
    """
    async with UnitOfWork() as uow:
        yield uow
        await uow.commit()


# ── Convenience context manager (non-FastAPI callers) ─────────────────────────
@asynccontextmanager
async def unit_of_work() -> AsyncIterator[UnitOfWork]:
    async with UnitOfWork() as uow:
        yield uow


__all__ = ["UnitOfWork", "get_uow", "unit_of_work"]
