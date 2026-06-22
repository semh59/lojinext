# Faz 3 — Kullanım Analitiği Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kendi DB'sinde page-view kaydı (route, user_id, timestamp; dış servis yok) + basit admin görünümü (en çok/az kullanılan sayfalar) + kontrollü kayıt hacmi (retention task'i).

**Architecture:** Backend: `page_views` tablosu (migration 0024) → `PageViewRepository` (record / top-bottom aggregate / prune) → `POST /analytics/page-view` (auth user, best-effort kayıt) + `GET /admin/analytics/page-views` (admin aggregate) → gece retention Celery task'i. Frontend: `analytics-service.recordPageView` → `usePageViewTracking` hook (react-router `useLocation` değişiminde fire-and-forget POST, EliteLayout'ta mount) → `AdminAnalyticsPage` (React Query ile aggregate'i çizer, `/admin/analitik` route).

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, Celery beat, React + react-router + React Query, vitest, pytest. Yeni bağımlılık yok.

**Önkoşul bilgiler (kod doğrulandı, 2026-06-13):**
- Alembic head = `0023_schema_consistency_p2`; yeni migration `0024`, `down_revision="0023_schema_consistency_p2"`. Manuel migration formatı: bkz `alembic/versions/0023_schema_consistency_p2.py` (revision/down_revision str, `op`, `sa`).
- Model'ler `app/database/models.py`; `Base` ortak. `BaseRepository[T]` generic CRUD (`app/database/base_repository.py`); domain repo'lar `app/database/repositories/`.
- Endpoint auth dep: `app/api/deps.py` → `get_current_active_user`, `get_current_active_admin`. Mevcut kullanıcı id'si dep'ten gelen user objesinden (`user.get("id")` / `.id`).
- Endpoint router include: `app/api/v1/api.py` (`from app.api.v1.endpoints import (...)` + `api_router.include_router(x.router, prefix=..., tags=[...])`). Admin endpoint'leri `prefix="/admin"`.
- Celery beat: `app/infrastructure/background/celery_app.py` `beat_schedule={...}` + altta `import app.workers.tasks.<mod>  # noqa: E402,F401`. Task pattern: `@celery_app.task(bind=True, name="...", ...)` + `loop=asyncio.new_event_loop(); loop.run_until_complete(_run())` (bkz `theft_tasks.py`).
- Config: `app/config.py` `pydantic_settings.BaseSettings`; `from app.config import settings`.
- Frontend router: `frontend/src/App.tsx` — `BrowserRouter`>`Routes`; `/admin` altında lazy page'ler (`const AdminOverviewPage = lazy(() => import("./pages/admin/OverviewPage"))`, `<Route path="ml" element={<AdminMlManagementPage/>}/>`). Auth gate: `<Route element={<PrivateRoute requiredPermission="admin:read" />}>`.
- Frontend API: `frontend/src/services/api/*.ts`, hepsi `import axiosInstance from "./axios-instance"`. Authenticated layout: `frontend/src/layouts/EliteLayout.tsx` (PrivateRoute altında, tüm authenticated sayfaları sarar).
- Frontend test: `frontend/src/test/test-utils.tsx`'ten `render`/`renderHook` (QueryClientProvider+AuthProvider+MemoryRouter sarmalı). vitest. `npx vitest --run <path>`.
- Lokal faithful backend test reçetesi: bkz memory `local-test-db-execution` (Py3.12 container + throwaway testdb + full-repo mount + `localhost:5432` forwarder; integration testleri `localhost:5432` reachable ister).

---

### Task 1: Faz 3 çalışma branch'ini aç

**Files:** Yok (git).

- [ ] **Step 1: main güncel + branch**

Run: `git checkout main && git pull --ff-only neworigin main 2>&1 | tail -2; git checkout -b feat/faz3-kullanim-analitigi main`
Expected: `Switched to a new branch 'feat/faz3-kullanim-analitigi'` (main `389727a8` veya sonrası).

---

### Task 2: `page_views` migration + PageView model

**Files:**
- Create: `alembic/versions/0024_page_views.py`
- Modify: `app/database/models.py` (PageView model ekle)
- Test: `app/tests/integration/test_page_view_repo.py` (Task 3'te; bu task'ta migration+model+alembic check)

- [ ] **Step 1: Migration dosyasını oluştur**

`alembic/versions/0024_page_views.py`:

```python
"""page_views table — Faz 3 kullanım analitiği (route/user/timestamp).

Revision ID: 0024_page_views
Revises: 0023_schema_consistency_p2
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0024_page_views"
down_revision: Union[str, Sequence[str], None] = "0023_schema_consistency_p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route", sa.String(length=255), nullable=False),
        # user_id FK YOK — analitik decoupled/best-effort; süper-admin synthetic
        # id'leri ve silinmiş kullanıcılar FK violation yaratmasın.
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_page_views_created_at", "page_views", ["created_at"])
    op.create_index("idx_page_views_route", "page_views", ["route"])


def downgrade() -> None:
    op.drop_index("idx_page_views_route", table_name="page_views")
    op.drop_index("idx_page_views_created_at", table_name="page_views")
    op.drop_table("page_views")
```

- [ ] **Step 2: PageView model'i ekle**

`app/database/models.py` — dosyanın sonuna yakın (diğer model'lerin yanına), `Base` ve `Mapped`/`mapped_column` zaten import'lu:

```python
class PageView(Base):
    """Faz 3 — sayfa görüntüleme kaydı (kullanım analitiği)."""

    __tablename__ = "page_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    route: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
        index=True,
    )
```

> Not: `String`, `DateTime`, `text`, `Optional`, `datetime`, `Mapped`, `mapped_column` import'larının `models.py` başında olduğunu doğrula (mevcut model'ler kullanıyor; eksikse ekle).

- [ ] **Step 3: alembic check drift yok (model ↔ migration uyumu)**

Run (faithful container, bkz reçete): `alembic upgrade head && alembic check`
Expected: upgrade `0023 -> 0024` çalışır; `alembic check` → "No new upgrade operations detected." (model ve migration uyumlu — drift yoksa). Drift raporlarsa migration'ı modele göre düzelt.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/0024_page_views.py app/database/models.py
git commit -m "feat(analytics): page_views tablosu + PageView model (migration 0024)"
```

---

### Task 3: `PageViewRepository`

**Files:**
- Create: `app/database/repositories/page_view_repo.py`
- Test: `app/tests/integration/test_page_view_repo.py` (create)

- [ ] **Step 1: Failing integration test yaz**

`app/tests/integration/test_page_view_repo.py`:

```python
"""PageViewRepository integration testleri."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.database.repositories.page_view_repo import PageViewRepository

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_record_inserts_row(db_session):
    repo = PageViewRepository(db_session)
    await repo.record(route="/trips", user_id=5)
    await db_session.commit()

    count = (
        await db_session.execute(text("SELECT count(*) FROM page_views"))
    ).scalar()
    assert count == 1


async def test_top_routes_orders_by_count(db_session):
    repo = PageViewRepository(db_session)
    for _ in range(3):
        await repo.record(route="/trips", user_id=1)
    await repo.record(route="/fuel", user_id=1)
    await db_session.commit()

    top = await repo.top_routes(days=30, limit=10)
    routes = [r["route"] for r in top]
    counts = {r["route"]: r["count"] for r in top}
    assert routes[0] == "/trips"
    assert counts["/trips"] == 3
    assert counts["/fuel"] == 1


async def test_prune_older_than_deletes_old_rows(db_session):
    repo = PageViewRepository(db_session)
    await repo.record(route="/old", user_id=1)
    await db_session.commit()
    # Bir satırı 100 gün eskiye çek
    await db_session.execute(
        text("UPDATE page_views SET created_at = :ts WHERE route = '/old'"),
        {"ts": datetime.now(timezone.utc) - timedelta(days=100)},
    )
    await repo.record(route="/new", user_id=1)
    await db_session.commit()

    deleted = await repo.prune_older_than(days=90)
    await db_session.commit()

    remaining = [
        r[0]
        for r in (
            await db_session.execute(text("SELECT route FROM page_views"))
        ).all()
    ]
    assert deleted == 1
    assert remaining == ["/new"]
```

- [ ] **Step 2: Testin FAIL ettiğini doğrula**

Run: `python -m pytest app/tests/integration/test_page_view_repo.py -m integration -q`
Expected: FAIL — `ModuleNotFoundError: ...page_view_repo`.

- [ ] **Step 3: Repo'yu implemente et**

`app/database/repositories/page_view_repo.py`:

```python
"""Faz 3 — sayfa görüntüleme (page_views) repository."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PageViewRepository:
    """page_views CRUD + aggregate + retention. Raw SQL (basit tablo)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, *, route: str, user_id: Optional[int]) -> None:
        await self.session.execute(
            text(
                "INSERT INTO page_views (route, user_id) VALUES (:route, :user_id)"
            ),
            {"route": route[:255], "user_id": user_id},
        )

    async def _aggregate(self, *, days: int, limit: int, asc: bool) -> list[dict[str, Any]]:
        order = "ASC" if asc else "DESC"
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT route, COUNT(*) AS cnt
                    FROM page_views
                    WHERE created_at >= now() - make_interval(days => :days)
                    GROUP BY route
                    ORDER BY cnt {order}, route ASC
                    LIMIT :limit
                    """
                ),
                {"days": days, "limit": limit},
            )
        ).all()
        return [{"route": r[0], "count": int(r[1])} for r in rows]

    async def top_routes(self, *, days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
        return await self._aggregate(days=days, limit=limit, asc=False)

    async def bottom_routes(self, *, days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
        return await self._aggregate(days=days, limit=limit, asc=True)

    async def total_views(self, *, days: int = 30) -> int:
        return int(
            (
                await self.session.execute(
                    text(
                        "SELECT COUNT(*) FROM page_views "
                        "WHERE created_at >= now() - make_interval(days => :days)"
                    ),
                    {"days": days},
                )
            ).scalar()
            or 0
        )

    async def prune_older_than(self, *, days: int = 90) -> int:
        result = await self.session.execute(
            text(
                "DELETE FROM page_views "
                "WHERE created_at < now() - make_interval(days => :days)"
            ),
            {"days": days},
        )
        return int(result.rowcount or 0)
```

- [ ] **Step 4: Testin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/integration/test_page_view_repo.py -m integration -q`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/database/repositories/page_view_repo.py app/tests/integration/test_page_view_repo.py
git commit -m "feat(analytics): PageViewRepository (record/top-bottom/prune)"
```

---

### Task 4: Endpoint'ler — record + admin aggregate

**Files:**
- Create: `app/schemas/analytics.py`
- Create: `app/api/v1/endpoints/analytics.py`
- Modify: `app/api/v1/api.py` (router include)
- Test: `app/tests/api/test_analytics_endpoints.py` (create)

- [ ] **Step 1: Schema'yı oluştur**

`app/schemas/analytics.py`:

```python
"""Faz 3 — kullanım analitiği request/response şemaları."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageViewCreate(BaseModel):
    route: str = Field(..., min_length=1, max_length=255)


class RouteCount(BaseModel):
    route: str
    count: int


class PageViewStats(BaseModel):
    period_days: int
    total_views: int
    top_routes: list[RouteCount]
    bottom_routes: list[RouteCount]
```

- [ ] **Step 2: api.py admin include pattern'ini incele**

Run: `grep -nE "admin_fuel_accuracy|include_router.*admin|from app.api.v1.endpoints import" app/api/v1/api.py | head`
Expected: include kalıbını gör (`prefix="/admin"`). analytics router iki prefix'te include edilecek (`/analytics` user kayıt + `/admin` aggregate) — bu yüzden iki ayrı router kullanılacak (aşağıda).

- [ ] **Step 3: Failing test yaz**

`app/tests/api/test_analytics_endpoints.py`:

```python
"""Analytics endpoint testleri."""

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_record_page_view(async_client, normal_auth_headers):
    resp = await async_client.post(
        "/api/v1/analytics/page-view",
        json={"route": "/trips"},
        headers=normal_auth_headers,
    )
    assert resp.status_code == 204


async def test_record_requires_auth(async_client):
    resp = await async_client.post(
        "/api/v1/analytics/page-view", json={"route": "/trips"}
    )
    assert resp.status_code == 401


async def test_admin_stats_aggregates(async_client, admin_auth_headers):
    # Birkaç kayıt at
    for _ in range(2):
        await async_client.post(
            "/api/v1/analytics/page-view",
            json={"route": "/fuel"},
            headers=admin_auth_headers,
        )
    resp = await async_client.get(
        "/api/v1/admin/analytics/page-views?days=30",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_views"] >= 2
    assert any(r["route"] == "/fuel" for r in body["top_routes"])


async def test_admin_stats_requires_admin(async_client, normal_auth_headers):
    resp = await async_client.get(
        "/api/v1/admin/analytics/page-views", headers=normal_auth_headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 4: Testin FAIL ettiğini doğrula**

Run: `python -m pytest app/tests/api/test_analytics_endpoints.py -m integration -q`
Expected: FAIL — 404 (route yok).

- [ ] **Step 5: Endpoint'leri implemente et**

`app/api/v1/endpoints/analytics.py`:

```python
"""Faz 3 — kullanım analitiği endpoint'leri.

- POST /analytics/page-view  : authenticated kullanıcı sayfa görüntüleme kaydı
                               (best-effort; kayıt hatası 204'ü bozmaz).
- GET  /admin/analytics/page-views : admin aggregate (top/bottom routes).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_current_active_admin, get_current_active_user
from app.database.repositories.page_view_repo import PageViewRepository
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from app.schemas.analytics import PageViewCreate, PageViewStats, RouteCount

logger = get_logger(__name__)

# Kullanıcı kanalı (kayıt)
router = APIRouter()
# Admin kanalı (aggregate) — /admin prefix ile include edilir
admin_router = APIRouter()


def _uid(user) -> int | None:
    if isinstance(user, dict):
        uid = user.get("id")
    else:
        uid = getattr(user, "id", None)
    try:
        uid_int = int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None
    # Süper-admin synthetic id<=0 → analitikte anonim (None)
    return uid_int if uid_int and uid_int > 0 else None


@router.post("/page-view", status_code=204)
async def record_page_view(
    payload: PageViewCreate,
    user=Depends(get_current_active_user),
) -> Response:
    """Sayfa görüntüleme kaydı — best-effort, kullanıcı akışını bloklamaz."""
    try:
        async with UnitOfWork() as uow:
            repo = PageViewRepository(uow.session)
            await repo.record(route=payload.route, user_id=_uid(user))
            await uow.commit()
    except Exception as exc:  # noqa: BLE001 — analitik best-effort
        logger.warning("page-view kaydı başarısız: %s", exc)
    return Response(status_code=204)


@admin_router.get("/analytics/page-views", response_model=PageViewStats)
async def get_page_view_stats(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    _admin=Depends(get_current_active_admin),
) -> PageViewStats:
    async with UnitOfWork() as uow:
        repo = PageViewRepository(uow.session)
        top = await repo.top_routes(days=days, limit=limit)
        bottom = await repo.bottom_routes(days=days, limit=limit)
        total = await repo.total_views(days=days)
    return PageViewStats(
        period_days=days,
        total_views=total,
        top_routes=[RouteCount(**r) for r in top],
        bottom_routes=[RouteCount(**r) for r in bottom],
    )
```

> Not: `UnitOfWork`'ın `.session` attribute'ü ve `get_current_active_user`'ın döndürdüğü tip (dict vs obj) için `_uid` her ikisini de tolere eder. `UnitOfWork` kullanımını mevcut bir endpoint'le (örn. `admin_fuel_accuracy.py` `async with` kalıbı) teyit et; farklıysa o kalıba uydur.

- [ ] **Step 6: Router'ları api.py'ye ekle**

`app/api/v1/api.py` — import bloğuna `analytics` ekle; include'lara:

```python
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(
    analytics.admin_router, prefix="/admin", tags=["admin-analytics"]
)
```

- [ ] **Step 7: Testin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/api/test_analytics_endpoints.py -m integration -q`
Expected: `4 passed` (204 record, 401 no-auth, 200 admin stats, 403 non-admin).

- [ ] **Step 8: Commit**

```bash
git add app/schemas/analytics.py app/api/v1/endpoints/analytics.py app/api/v1/api.py app/tests/api/test_analytics_endpoints.py
git commit -m "feat(analytics): POST /analytics/page-view + GET /admin/analytics/page-views"
```

---

### Task 5: Retention task + config (kontrollü hacim)

**Files:**
- Modify: `app/config.py` (`ANALYTICS_RETENTION_DAYS`)
- Create: `app/workers/tasks/analytics_tasks.py`
- Modify: `app/infrastructure/background/celery_app.py` (beat + import)
- Test: `app/tests/unit/test_analytics_prune_task.py` (create)

- [ ] **Step 1: Config ekle**

`app/config.py` — `Settings` sınıfına (ML grubunun yanına):

```python
    ANALYTICS_RETENTION_DAYS: int = 90
```

- [ ] **Step 2: Failing test yaz**

`app/tests/unit/test_analytics_prune_task.py`:

```python
"""analytics.prune_page_views task wrapper testi."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_prune_task_invokes_repo_and_returns_count():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    uow.session = MagicMock()
    uow.commit = AsyncMock()

    with (
        patch("app.workers.tasks.analytics_tasks.UnitOfWork", return_value=uow),
        patch(
            "app.workers.tasks.analytics_tasks.PageViewRepository"
        ) as repo_cls,
    ):
        repo_cls.return_value.prune_older_than = AsyncMock(return_value=7)
        from app.workers.tasks.analytics_tasks import prune_page_views

        result = prune_page_views.run()

    assert result == {"deleted": 7}
```

- [ ] **Step 3: Testin FAIL ettiğini doğrula**

Run: `python -m pytest app/tests/unit/test_analytics_prune_task.py -q`
Expected: FAIL — `ModuleNotFoundError: ...analytics_tasks`.

- [ ] **Step 4: Task'i implemente et**

`app/workers/tasks/analytics_tasks.py`:

```python
"""Faz 3 — kullanım analitiği retention task'i (gece prune)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.database.repositories.page_view_repo import PageViewRepository
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.background.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="analytics.prune_page_views",
    max_retries=1,
    acks_late=True,
)
def prune_page_views(self) -> dict[str, Any]:  # noqa: ARG001
    """ANALYTICS_RETENTION_DAYS'ten eski page_views satırlarını siler."""

    async def _run() -> dict[str, Any]:
        async with UnitOfWork() as uow:
            repo = PageViewRepository(uow.session)
            deleted = await repo.prune_older_than(
                days=settings.ANALYTICS_RETENTION_DAYS
            )
            await uow.commit()
        return {"deleted": deleted}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:  # noqa: BLE001
        logger.error("analytics prune failed: %s", exc, exc_info=True)
        return {"deleted": 0, "error": str(exc)}
    finally:
        loop.close()
```

- [ ] **Step 5: Beat schedule + import ekle**

`app/infrastructure/background/celery_app.py` — `beat_schedule` içine (Faz 1 entry'sinin yanına):

```python
            # Faz 3 — Her gün 04:00 UTC, retention: eski page_views temizliği.
            "analytics-prune-page-views-nightly": {
                "task": "analytics.prune_page_views",
                "schedule": crontab(hour=4, minute=0),
            },
```

Import bloğuna:

```python
import app.workers.tasks.analytics_tasks  # noqa: E402,F401
```

- [ ] **Step 6: Testin PASS ettiğini doğrula**

Run: `python -m pytest app/tests/unit/test_analytics_prune_task.py -q`
Expected: `1 passed`.

- [ ] **Step 7: Beat/task kaydını doğrula**

Run: `python -c "from app.infrastructure.background.celery_app import celery_app as c; assert 'analytics.prune_page_views' in c.tasks; assert 'analytics-prune-page-views-nightly' in c.conf.beat_schedule; print('OK')"`
Expected: `OK`.

- [ ] **Step 8: Commit**

```bash
git add app/config.py app/workers/tasks/analytics_tasks.py app/infrastructure/background/celery_app.py app/tests/unit/test_analytics_prune_task.py
git commit -m "feat(analytics): retention task analytics.prune_page_views + gece beat (04:00)"
```

---

### Task 6: Frontend — analytics-service + page-view tracking hook

**Files:**
- Create: `frontend/src/services/api/analytics-service.ts`
- Create: `frontend/src/hooks/usePageViewTracking.ts`
- Test: `frontend/src/services/api/__tests__/analytics-service.test.ts` (create)
- Test: `frontend/src/hooks/__tests__/usePageViewTracking.test.tsx` (create)

- [ ] **Step 1: Failing service testi yaz**

`frontend/src/services/api/__tests__/analytics-service.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../axios-instance", () => ({
  default: { post: vi.fn().mockResolvedValue({ status: 204 }) },
}));

describe("analytics-service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("recordPageView POSTs route to /analytics/page-view", async () => {
    const axiosInstance = (await import("../axios-instance")).default;
    const { recordPageView } = await import("../analytics-service");
    await recordPageView("/trips");
    expect(axiosInstance.post).toHaveBeenCalledWith("/analytics/page-view", {
      route: "/trips",
    });
  });

  it("recordPageView swallows errors (best-effort)", async () => {
    const axiosInstance = (await import("../axios-instance")).default;
    (axiosInstance.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("network"),
    );
    const { recordPageView } = await import("../analytics-service");
    await expect(recordPageView("/fuel")).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 2: Service testinin FAIL ettiğini doğrula**

Run: `cd frontend && npx vitest --run src/services/api/__tests__/analytics-service.test.ts`
Expected: FAIL — cannot resolve `../analytics-service`.

- [ ] **Step 3: Service'i implemente et**

`frontend/src/services/api/analytics-service.ts`:

```typescript
import axiosInstance from "./axios-instance";

/**
 * Faz 3 — sayfa görüntüleme kaydı. Best-effort: hata yutulur, UI'ı bozmaz.
 */
export async function recordPageView(route: string): Promise<void> {
  try {
    await axiosInstance.post("/analytics/page-view", { route });
  } catch {
    // analitik best-effort — sessizce geç
  }
}
```

- [ ] **Step 4: Service testinin PASS ettiğini doğrula**

Run: `cd frontend && npx vitest --run src/services/api/__tests__/analytics-service.test.ts`
Expected: 2 passed.

- [ ] **Step 5: Failing hook testi yaz**

`frontend/src/hooks/__tests__/usePageViewTracking.test.tsx`:

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

vi.mock("../../services/api/analytics-service", () => ({
  recordPageView: vi.fn().mockResolvedValue(undefined),
}));

describe("usePageViewTracking", () => {
  beforeEach(() => vi.clearAllMocks());

  it("records the current route on mount", async () => {
    const { recordPageView } = await import(
      "../../services/api/analytics-service"
    );
    const { usePageViewTracking } = await import("../usePageViewTracking");
    renderHook(() => usePageViewTracking(), {
      wrapper: ({ children }) => (
        <MemoryRouter initialEntries={["/trips"]}>{children}</MemoryRouter>
      ),
    });
    expect(recordPageView).toHaveBeenCalledWith("/trips");
  });
});
```

- [ ] **Step 6: Hook testinin FAIL ettiğini doğrula**

Run: `cd frontend && npx vitest --run src/hooks/__tests__/usePageViewTracking.test.tsx`
Expected: FAIL — cannot resolve `../usePageViewTracking`.

- [ ] **Step 7: Hook'u implemente et**

`frontend/src/hooks/usePageViewTracking.ts`:

```typescript
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { recordPageView } from "../services/api/analytics-service";

/**
 * Faz 3 — route değişiminde sayfa görüntüleme kaydı (fire-and-forget).
 * Aynı path için arka arkaya tekrar göndermez (dedup).
 */
export function usePageViewTracking(): void {
  const location = useLocation();
  const lastPath = useRef<string | null>(null);

  useEffect(() => {
    if (lastPath.current === location.pathname) return;
    lastPath.current = location.pathname;
    void recordPageView(location.pathname);
  }, [location.pathname]);
}
```

- [ ] **Step 8: Hook testinin PASS ettiğini doğrula**

Run: `cd frontend && npx vitest --run src/hooks/__tests__/usePageViewTracking.test.tsx`
Expected: 1 passed.

- [ ] **Step 9: Hook'u EliteLayout'a mount et**

`frontend/src/layouts/EliteLayout.tsx` — component gövdesinin başında çağır:

```typescript
import { usePageViewTracking } from "../hooks/usePageViewTracking";
```
ve component fonksiyonunun ilk satırlarında:
```typescript
  usePageViewTracking();
```

> EliteLayout PrivateRoute altında olduğundan yalnız authenticated sayfa görüntülemeleri kaydedilir. Mevcut EliteLayout testinin (`__tests__/EliteLayout.test.tsx`) hâlâ geçtiğini Step 11'de doğrula (analytics-service mock'lanmamışsa axios çağrısı sessiz fail → UI etkilenmez; gerekirse test wrapper'ı zaten MemoryRouter sağlıyor).

- [ ] **Step 10: Commit**

```bash
git add frontend/src/services/api/analytics-service.ts frontend/src/hooks/usePageViewTracking.ts frontend/src/layouts/EliteLayout.tsx frontend/src/services/api/__tests__/analytics-service.test.ts frontend/src/hooks/__tests__/usePageViewTracking.test.tsx
git commit -m "feat(analytics): recordPageView service + usePageViewTracking hook (EliteLayout mount)"
```

- [ ] **Step 11: EliteLayout testi hâlâ geçiyor mu**

Run: `cd frontend && npx vitest --run src/layouts/__tests__/EliteLayout.test.tsx`
Expected: pass (regresyon yok). Fail ederse: analytics-service'i o testte mock'la (`vi.mock("../../services/api/analytics-service", () => ({ recordPageView: vi.fn() }))`) ve tekrar koş, commit'i amend et.

---

### Task 7: Frontend — Admin analitik görünümü

**Files:**
- Create: `frontend/src/pages/admin/AnalyticsPage.tsx`
- Modify: `frontend/src/services/api/analytics-service.ts` (fetchPageViewStats ekle)
- Modify: `frontend/src/App.tsx` (lazy import + route)
- Test: `frontend/src/pages/admin/__tests__/AnalyticsPage.test.tsx` (create)

- [ ] **Step 1: Service'e fetchPageViewStats ekle**

`frontend/src/services/api/analytics-service.ts` — sonuna:

```typescript
export interface RouteCount {
  route: string;
  count: number;
}

export interface PageViewStats {
  period_days: number;
  total_views: number;
  top_routes: RouteCount[];
  bottom_routes: RouteCount[];
}

export async function fetchPageViewStats(
  days = 30,
): Promise<PageViewStats> {
  const { data } = await axiosInstance.get<PageViewStats>(
    "/admin/analytics/page-views",
    { params: { days } },
  );
  return data;
}
```

- [ ] **Step 2: Failing page testi yaz**

`frontend/src/pages/admin/__tests__/AnalyticsPage.test.tsx`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../../../test/test-utils";

vi.mock("../../../services/api/analytics-service", () => ({
  fetchPageViewStats: vi.fn().mockResolvedValue({
    period_days: 30,
    total_views: 42,
    top_routes: [{ route: "/trips", count: 30 }],
    bottom_routes: [{ route: "/profile", count: 1 }],
  }),
}));

describe("AnalyticsPage", () => {
  it("renders top and bottom routes from the API", async () => {
    const { default: AnalyticsPage } = await import("../AnalyticsPage");
    render(<AnalyticsPage />);
    expect(await screen.findByText("/trips")).toBeInTheDocument();
    expect(await screen.findByText("/profile")).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Testin FAIL ettiğini doğrula**

Run: `cd frontend && npx vitest --run src/pages/admin/__tests__/AnalyticsPage.test.tsx`
Expected: FAIL — cannot resolve `../AnalyticsPage`.

- [ ] **Step 4: Page'i implemente et**

`frontend/src/pages/admin/AnalyticsPage.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchPageViewStats } from "../../services/api/analytics-service";

function RouteList({
  title,
  rows,
}: {
  title: string;
  rows: { route: string; count: number }[];
}) {
  return (
    <div className="rounded-modal border border-border bg-surface p-4">
      <h3 className="mb-2 text-sm font-semibold text-secondary">{title}</h3>
      <ul className="space-y-1">
        {rows.map((r) => (
          <li
            key={r.route}
            className="flex justify-between text-sm text-primary"
          >
            <span className="font-mono">{r.route}</span>
            <span className="text-tertiary">{r.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pageViewStats", 30],
    queryFn: () => fetchPageViewStats(30),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-primary">Kullanım Analitiği</h1>
        <span className="text-sm text-tertiary">
          Son {data?.period_days ?? 30} gün — toplam {data?.total_views ?? 0}{" "}
          görüntüleme
        </span>
      </div>
      {isLoading ? (
        <p className="text-sm text-tertiary">Yükleniyor…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <RouteList title="En çok kullanılan" rows={data?.top_routes ?? []} />
          <RouteList title="En az kullanılan" rows={data?.bottom_routes ?? []} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Testin PASS ettiğini doğrula**

Run: `cd frontend && npx vitest --run src/pages/admin/__tests__/AnalyticsPage.test.tsx`
Expected: 1 passed.

- [ ] **Step 6: Route'u App.tsx'e ekle**

`frontend/src/App.tsx` — diğer admin lazy import'larının yanına:

```typescript
const AdminAnalyticsPage = lazy(() => import("./pages/admin/AnalyticsPage"));
```
ve `/admin` alt route'larına (örn. `ml` route'unun yanına):

```typescript
                        <Route path="analitik" element={<AdminAnalyticsPage />} />
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/admin/AnalyticsPage.tsx frontend/src/services/api/analytics-service.ts frontend/src/App.tsx frontend/src/pages/admin/__tests__/AnalyticsPage.test.tsx
git commit -m "feat(analytics): admin /admin/analitik görünümü (top/bottom routes)"
```

---

### Task 8: Gate'ler + uçtan uca kabul + merge

**Files:** Yok.

- [ ] **Step 1: Backend ruff + mypy**

Run: `ruff check app --select E,F,W,I && mypy app --ignore-missing-imports --no-strict-optional 2>&1 | tail -2`
Expected: ruff temiz; mypy `Success: no issues found`.

- [ ] **Step 2: Backend yeni testler (faithful Py3.12)**

Run: `python -m pytest app/tests/integration/test_page_view_repo.py app/tests/api/test_analytics_endpoints.py app/tests/unit/test_analytics_prune_task.py -q`
Expected: 8 passed (3 repo + 4 endpoint + 1 task).

- [ ] **Step 3: alembic check (drift yok)**

Run: `alembic upgrade head && alembic check`
Expected: head `0024_page_views`; "No new upgrade operations detected."

- [ ] **Step 4: Frontend lint + yeni testler + build**

Run: `cd frontend && npm run lint && npx vitest --run src/services/api/__tests__/analytics-service.test.ts src/hooks/__tests__/usePageViewTracking.test.tsx src/pages/admin/__tests__/AnalyticsPage.test.tsx src/layouts/__tests__/EliteLayout.test.tsx && npm run build`
Expected: lint temiz; testler pass; `vite build` başarılı.

- [ ] **Step 5: Uçtan uca kabul (canlı stack)**

Önkoşul: backend image rebuild + stack healthy (`docker compose up -d --build backend`; migration entrypoint'te `alembic upgrade head` ile 0024'ü uygular). Doğrula:

Run: `docker compose exec backend curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/analytics/page-view -H "Authorization: Bearer <user_token>" -H "Content-Type: application/json" -d '{"route":"/trips"}'`
Expected: `204`. Sonra `GET /api/v1/admin/analytics/page-views?days=30` (admin token) → `total_views>=1`, `top_routes` içinde `/trips`. DB: `SELECT count(*) FROM page_views` ≥1. Frontend'de bir sayfada gezinince (authenticated) `page_views` satırı artar.

- [ ] **Step 6: main'e merge + push**

```bash
git checkout main
git merge --ff-only feat/faz3-kullanim-analitigi
git push neworigin main
```

Expected: `Fast-forward` + push. Faz 3 TAMAM — sıradaki: Faz 4 (Web push).

---

## Self-Review Notu (2026-06-13)

- **Spec kapsaması:** "Kendi DB'sinde page-view kaydı (route, user_id, timestamp)": Task 2 (tablo) + Task 3 (record) + Task 4 (POST endpoint) + Task 6 (frontend tracking). "Basit admin görünümü (en çok/az kullanılan sayfalar)": Task 4 (admin aggregate endpoint) + Task 7 (admin page). "Kayıt hacmi kontrollü (retention)": Task 5 (prune task + ANALYTICS_RETENTION_DAYS). "Dış servis yok": tümü kendi DB + kendi endpoint'leri.
- **Placeholder taraması:** Yok — her adımda tam kod/komut. İki teyit notu (Task 4 Step 5 UnitOfWork.session kalıbı; Task 6 Step 11 EliteLayout test mock'u) codebase-doğrulama gerektiren noktalar, doğrulama komutuyla.
- **Tip/isim tutarlılığı:** `PageViewRepository.record/top_routes/bottom_routes/total_views/prune_older_than` Task 3'te tanımlı; Task 4 (endpoint) ve Task 5 (task) aynı imzalarla çağırıyor. `recordPageView`/`fetchPageViewStats`/`PageViewStats`/`RouteCount` frontend'de tutarlı (Task 6 service tanımlar, Task 7 fetch + page kullanır). Endpoint yolları: `POST /api/v1/analytics/page-view`, `GET /api/v1/admin/analytics/page-views` — test, frontend service ve e2e'de aynı.
- **Sıra bağımlılığı:** Task 2 (tablo) → 3 (repo) → 4 (endpoint) / 5 (task) repo'ya bağlı; Task 6 (service+hook) → 7 (page service'i genişletir); Task 8 hepsini doğrular. Her task kendi başına commit'lenebilir.
- **best-effort sözleşmesi:** record endpoint (Task 4) ve recordPageView (Task 6) hata yutar — analitik asıl akışı/UI'ı bozmaz (audit best-effort deseniyle tutarlı).
