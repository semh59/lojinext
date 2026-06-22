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
            text("INSERT INTO page_views (route, user_id) VALUES (:route, :user_id)"),
            {"route": route[:255], "user_id": user_id},
        )

    async def _aggregate(
        self, *, days: int, limit: int, asc: bool
    ) -> list[dict[str, Any]]:
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

    async def top_routes(
        self, *, days: int = 30, limit: int = 10
    ) -> list[dict[str, Any]]:
        return await self._aggregate(days=days, limit=limit, asc=False)

    async def bottom_routes(
        self, *, days: int = 30, limit: int = 10
    ) -> list[dict[str, Any]]:
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
        # Runtime CursorResult'ta rowcount var; SQLAlchemy stub'ı Result[Any]
        # olarak daraltıp rowcount'u görmüyor → getattr ile güvenli eriş.
        return int(getattr(result, "rowcount", 0) or 0)
