"""Use-case: son N ayın aylık toplam yakıt tüketim trendi (kronolojik sırada)."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import YakitAlimi


async def get_consumption_trend(session: AsyncSession, months: int = 6) -> List[Dict]:
    month_col = func.to_char(YakitAlimi.tarih, "YYYY-MM")

    # Subquery: son N ayı DESC ile seç, dış sorgu ile ASC'ye çevir
    subq = (
        select(
            month_col.label("month"),
            func.sum(YakitAlimi.litre).label("consumption"),
        )
        .group_by(month_col)
        .order_by(desc(month_col))
        .limit(months)
    ).subquery()

    stmt = select(subq.c.month, subq.c.consumption).order_by(subq.c.month)

    result = await session.execute(stmt)
    return [
        {"month": row.month, "consumption": float(row.consumption)}
        for row in result.all()
    ]
