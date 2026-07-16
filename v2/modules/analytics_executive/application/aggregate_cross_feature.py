"""Feature E.6 — Cross-feature impact aggregator.

D.4 (bakım gecikme zararı) + A.5 (koçluk tasarrufu) + B (hırsızlık zararı)
toplam etkisini tek panel olarak döner. Üç motor için heuristic hesaplar;
plan §9 "v1 lineer yaklaşıklık, v2 sefer-bazlı atfetme".

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §9
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Sabitler (heuristic v1) ────────────────────────────────────────────
# Aşağıdaki katsayılar deneysel/sektör verisi tabanlı varsayımlar; ileri
# sürümlerde A/B test veya regresyon ile kalibre edilecek (Plan §9).
# Mevcut response.confidence=0.55 düşük tutuluyor çünkü kalibrasyon yok.
# Formül: skor_delta × yıllık_km × etki_katsayısı × birim_L_per_100km
COACHING_KM_PER_DRIVER_AVG = 50_000  # TIR şoförü ortalama yıllık km
COACHING_IMPACT_RATIO = 0.30  # skor delta 0.1 → ~%3 yakıt tasarrufu

# Hırsızlık zararı: real_theft sayısı × ortalama sefer L × sapma %
THEFT_AVG_TRIP_L = 200.0  # ortalama sefer tüketim L


@dataclass
class CrossFeatureImpact:
    period_days: int
    maintenance_delay_loss_tl: float  # D.4: factor > 1 araç ekstra L × fiyat
    coaching_savings_tl: float  # A.5: ölçülmüş delta'dan tasarruf
    theft_loss_tl: float  # B: resolved real_theft × kayıp L
    confidence: float  # 0..1; v1'de düşük (heuristic)


async def aggregate_cross_feature(
    uow,
    *,
    period_days: int = 90,
    diesel_price_tl: float = 50.0,
) -> CrossFeatureImpact:
    """3 motorun cross-feature etkisini topla (heuristic v1).

    Args:
        period_days: lookback penceresi (default 90)
        diesel_price_tl: dizel L birim fiyat

    Returns:
        CrossFeatureImpact — 3 kalem TL + confidence (v1 heuristic → 0.55).
    """
    from sqlalchemy import text

    # ── D.4: Bakım gecikme zararı ─────────────────────────────────────
    # Aktif araçların son N gün tüketim toplamı; her araç için maintenance_factor
    # hesapla → factor > 1 ise (factor-1) × yıllık L = ekstra L
    arac_rows = (
        (
            await uow.session.execute(
                text(
                    """
                SELECT a.id,
                    COALESCE(SUM(s.tuketim), 0) AS period_l
                FROM araclar a
                LEFT JOIN seferler s ON a.id = s.arac_id
                    AND s.is_deleted = FALSE
                    AND s.tuketim IS NOT NULL
                    AND s.tarih >= CURRENT_DATE
                        - (:period_days * INTERVAL '1 day')
                WHERE a.aktif = TRUE AND a.is_deleted = FALSE
                GROUP BY a.id
                """
                ),
                {"period_days": period_days},
            )
        )
        .mappings()
        .all()
    )

    maintenance_loss_l = 0.0
    try:
        from app.core.ml.vehicle_health_factor import (
            compute_maintenance_factor,
            fetch_health_input_batch,
        )

        arac_id_list = [int(r["id"]) for r in arac_rows]
        health_map = await fetch_health_input_batch(uow, arac_id_list)
        for r in arac_rows:
            try:
                h_inp = health_map.get(int(r["id"]))
                if h_inp is None:
                    continue
                h_res = compute_maintenance_factor(h_inp)
                if h_res.factor > 1.0:
                    extra_pct = h_res.factor - 1.0
                    maintenance_loss_l += float(r["period_l"] or 0) * extra_pct
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning("D.4 aggregat arac %s skipped: %s", r.get("id"), exc)
                continue
    except Exception as exc:
        logger.warning("D.4 module import failed in aggregator: %s", exc)

    # ── A.5: Koçluk tasarrufu ─────────────────────────────────────────
    # Evaluated deliveries (sent_at son N gün) → avg score delta
    # delta * KM_PER_DRIVER * IMPACT_RATIO * diesel = TL tasarruf
    coaching_savings_l = 0.0
    try:
        a5_row = (
            (
                await uow.session.execute(
                    text(
                        """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE evaluated_at IS NOT NULL
                        ) AS evaluated,
                        COALESCE(
                            AVG(score_after_2w - score_before)
                                FILTER (
                                    WHERE evaluated_at IS NOT NULL
                                    AND score_after_2w IS NOT NULL
                                ),
                            0
                        ) AS avg_delta
                    FROM coaching_deliveries
                    WHERE sent_at >= CURRENT_DATE
                        - (:period_days * INTERVAL '1 day')
                    """
                    ),
                    {"period_days": period_days},
                )
            )
            .mappings()
            .one()
        )
        a5_delta = float(a5_row.get("avg_delta") or 0)
        a5_evaluated = int(a5_row.get("evaluated") or 0)
        if a5_delta > 0 and a5_evaluated > 0:
            # Period-scaled km (yıllık km × period/365), sürücü sayısıyla çarp.
            period_km = COACHING_KM_PER_DRIVER_AVG * (period_days / 365.0)
            coaching_savings_l = (
                a5_evaluated * a5_delta * period_km * COACHING_IMPACT_RATIO
            )
    except Exception as exc:
        logger.warning("A.5 aggregat failed: %s", exc)

    # ── B: Hırsızlık zararı ───────────────────────────────────────────
    # resolved real_theft soruşturmalar × avg sapma % × THEFT_AVG_TRIP_L
    theft_loss_l = 0.0
    try:
        b_row = (
            (
                await uow.session.execute(
                    text(
                        """
                    SELECT
                        COUNT(*) AS real_thefts,
                        COALESCE(AVG(a.sapma_yuzde), 0) AS avg_sapma
                    FROM fuel_investigations i
                    JOIN anomalies a ON i.anomaly_id = a.id
                    WHERE i.resolution_type = 'real_theft'
                      AND i.closed_at >= CURRENT_DATE
                          - (:period_days * INTERVAL '1 day')
                    """
                    ),
                    {"period_days": period_days},
                )
            )
            .mappings()
            .one()
        )
        b_count = int(b_row.get("real_thefts") or 0)
        b_avg_sapma = float(b_row.get("avg_sapma") or 0)
        if b_count > 0 and b_avg_sapma > 0:
            theft_loss_l = b_count * THEFT_AVG_TRIP_L * (b_avg_sapma / 100.0)
    except Exception as exc:
        logger.warning("B aggregat failed: %s", exc)

    return CrossFeatureImpact(
        period_days=period_days,
        maintenance_delay_loss_tl=round(maintenance_loss_l * diesel_price_tl, 0),
        coaching_savings_tl=round(coaching_savings_l * diesel_price_tl, 0),
        theft_loss_tl=round(theft_loss_l * diesel_price_tl, 0),
        confidence=0.55,  # plan §9: v1 düşük (heuristic)
    )
