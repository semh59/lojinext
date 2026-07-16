"""Use-case: top-N şoför ayrılırsa filo verim kaybı (E.7)."""

from __future__ import annotations

from v2.modules.analytics_executive.domain.bus_factor_scoring import (
    BusFactorReport,
    compute_loss_tl,
    median_score,
    risk_level_for_loss,
)


async def compute_bus_factor(
    uow,
    *,
    n: int = 3,
    diesel_price_tl: float = 50.0,
) -> BusFactorReport:
    """Top-N şoför ayrılırsa filo verim kaybını hesapla.

    Args:
        n: top-N şoför (default 3)
        diesel_price_tl: dizel L birim fiyat

    Returns:
        BusFactorReport — kayıp TL + top-N (PII'siz) + risk_level
    """
    from sqlalchemy import text

    rows = (
        (
            await uow.session.execute(
                text(
                    """
                WITH driver_perf AS (
                    SELECT s.id, s.score,
                        COALESCE(SUM(t.mesafe_km), 0) AS yearly_km
                    FROM soforler s
                    LEFT JOIN seferler t ON t.sofor_id = s.id
                        AND t.is_deleted = FALSE
                        AND t.tarih >= CURRENT_DATE - INTERVAL '365 days'
                    WHERE s.aktif = TRUE AND s.is_deleted = FALSE
                    GROUP BY s.id
                )
                SELECT * FROM driver_perf ORDER BY score DESC
                """
                )
            )
        )
        .mappings()
        .all()
    )

    if not rows:
        return BusFactorReport(
            top_n_drivers_loss_tl=0.0,
            top_n_drivers=[],
            bottlenecked_routes=[],
            risk_level="low",
            n=n,
        )

    top_n = [dict(r) for r in rows[:n]]
    rest = [dict(r) for r in rows[n:]]
    median = median_score(rest)
    loss_tl = compute_loss_tl(top_n, median, diesel_price_tl)

    return BusFactorReport(
        top_n_drivers_loss_tl=round(loss_tl, 0),
        # PII koruma: yalnız score + km (plan §15)
        top_n_drivers=[
            {
                "score": round(float(r["score"]), 2),
                "yearly_km": int(r["yearly_km"]),
            }
            for r in top_n
        ],
        bottlenecked_routes=[],  # v2'de eklenir (plan §10.1 yorum)
        risk_level=risk_level_for_loss(loss_tl),
        n=n,
    )
