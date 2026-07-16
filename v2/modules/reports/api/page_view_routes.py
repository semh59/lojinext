"""Faz 3 — kullanım analitiği endpoint'leri.

- POST /analytics/page-view  : authenticated kullanıcı sayfa görüntüleme kaydı
                               (best-effort; kayıt hatası 204'ü bozmaz).
- GET  /admin/analytics/page-views : admin aggregate (top/bottom routes).

dalga 11 (analytics_executive) sırasında reports'a taşındı —
`app/api/v1/endpoints/analytics.py` analytics_executive'in dosya
envanterinde duruyordu ama içeriği tamamen `page_views` tablosuna hizmet
ediyor (Feature-E Strategic Cockpit ile ilgisi yok); page_view_repo.py
kararıyla (tablo-sahipliği) tutarlı olarak buraya geldi.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import SessionDep, get_current_active_admin, get_current_active_user
from app.infrastructure.logging.logger import get_logger
from v2.modules.reports.infrastructure.page_view_repo import PageViewRepository
from v2.modules.reports.schemas import PageViewCreate, PageViewStats, RouteCount

logger = get_logger(__name__)

# Kullanıcı kanalı (kayıt)
router = APIRouter()
# Admin kanalı (aggregate) — /admin prefix ile include edilir
admin_router = APIRouter()


def _uid(user: Any) -> Optional[int]:
    uid = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    try:
        uid_int = int(uid) if uid is not None else None
    except (TypeError, ValueError):
        return None
    # Süper-admin synthetic id<=0 → analitikte anonim (None)
    return uid_int if uid_int and uid_int > 0 else None


@router.post("/page-view", status_code=204)
async def record_page_view(
    payload: PageViewCreate,
    db: SessionDep,
    user=Depends(get_current_active_user),
) -> Response:
    """Sayfa görüntüleme kaydı — best-effort, kullanıcı akışını bloklamaz."""
    try:
        repo = PageViewRepository(db)
        await repo.record(route=payload.route, user_id=_uid(user))
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — analitik best-effort
        await db.rollback()
        logger.warning("page-view kaydı başarısız: %s", exc)
    return Response(status_code=204)


@admin_router.get("/analytics/page-views", response_model=PageViewStats)
async def get_page_view_stats(
    db: SessionDep,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    _admin=Depends(get_current_active_admin),
) -> PageViewStats:
    repo = PageViewRepository(db)
    top = await repo.top_routes(days=days, limit=limit)
    bottom = await repo.bottom_routes(days=days, limit=limit)
    total = await repo.total_views(days=days)
    return PageViewStats(
        period_days=days,
        total_views=total,
        top_routes=[RouteCount(**r) for r in top],
        bottom_routes=[RouteCount(**r) for r in bottom],
    )
