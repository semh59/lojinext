"""PageViewRepository integration testleri."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.tests._helpers.seed import seed_kullanici
from v2.modules.reports.infrastructure.page_view_repo import PageViewRepository

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_record_inserts_row(db_session):
    user = await seed_kullanici(db_session)
    repo = PageViewRepository(db_session)
    await repo.record(route="/trips", user_id=user.id)
    await db_session.commit()

    count = (await db_session.execute(text("SELECT count(*) FROM page_views"))).scalar()
    assert count == 1


async def test_record_rejects_nonexistent_user_id(db_session):
    """2026-07-02 prod-grade denetimi P2 (Tier A madde 4): `page_views.user_id`
    artık gerçek bir FK — var olmayan bir kullanıcı id'siyle kayıt eklemeye
    çalışmak IntegrityError fırlatmalı (diğer tüm audit alanları gibi)."""
    repo = PageViewRepository(db_session)
    with pytest.raises(IntegrityError):
        await repo.record(route="/trips", user_id=999_999)
    await db_session.rollback()


async def test_top_routes_orders_by_count(db_session):
    user = await seed_kullanici(db_session)
    repo = PageViewRepository(db_session)
    for _ in range(3):
        await repo.record(route="/trips", user_id=user.id)
    await repo.record(route="/fuel", user_id=user.id)
    await db_session.commit()

    top = await repo.top_routes(days=30, limit=10)
    routes = [r["route"] for r in top]
    counts = {r["route"]: r["count"] for r in top}
    assert routes[0] == "/trips"
    assert counts["/trips"] == 3
    assert counts["/fuel"] == 1


async def test_prune_older_than_deletes_old_rows(db_session):
    user = await seed_kullanici(db_session)
    repo = PageViewRepository(db_session)
    await repo.record(route="/old", user_id=user.id)
    await db_session.commit()
    # Bir satırı 100 gün eskiye çek
    await db_session.execute(
        text("UPDATE page_views SET created_at = :ts WHERE route = '/old'"),
        {"ts": datetime.now(timezone.utc) - timedelta(days=100)},
    )
    await repo.record(route="/new", user_id=user.id)
    await db_session.commit()

    deleted = await repo.prune_older_than(days=90)
    await db_session.commit()

    remaining = [
        r[0]
        for r in (await db_session.execute(text("SELECT route FROM page_views"))).all()
    ]
    assert deleted == 1
    assert remaining == ["/new"]
