"""Feature E.2 — What-if simulator (3 senaryo).

Senaryolar:
  1. fleet_renewal: X yaş üstü araçları Euro VI ile değiştir → ROI + CO2
  2. training: tüm aktif şoförlere eğitim → improvement % × yıllık L
  3. route_portfolio: en kötü performans güzergahları çıkar → Monte Carlo
     P10/P50/P90 belirsizlik bandı

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §5
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

ScenarioType = Literal["fleet_renewal", "training", "route_portfolio"]


@dataclass
class WhatIfResult:
    scenario_type: ScenarioType
    inputs: Dict[str, Any]
    yearly_savings_tl: float
    upfront_cost_tl: float
    payback_years: Optional[float]
    five_year_roi_pct: float
    co2_reduction_kg: float = 0.0
    confidence: float = 0.7
    monte_carlo: Optional[Dict[str, float]] = None  # P10/P50/P90
    reasons: List[str] = field(default_factory=list)


# ── Senaryo 1: Filo yenileme ROI ──────────────────────────────────────
async def simulate_fleet_renewal(
    uow,
    *,
    max_age_years: int,
    replacement_cost_per_vehicle_tl: float,
    expected_l_100km_improvement_pct: float = 15.0,
    diesel_price_tl: float = 50.0,
) -> WhatIfResult:
    """X yaş üstü araçları Euro VI ile değiştirirsem yıllık tasarruf?

    Args:
        max_age_years: bu yaş ÜSTÜ araçlar yenileme adayı
        replacement_cost_per_vehicle_tl: tek araç değiştirme maliyeti
        expected_l_100km_improvement_pct: yeni araçtan beklenen verimlilik %
        diesel_price_tl: dizel L birim fiyat (settings.LITRE_DIESEL_TL fallback)
    """
    from sqlalchemy import text

    from v2.modules.analytics_executive.domain.carbon_footprint import (
        euro_class_for_year,
    )

    sql = """
        SELECT a.id, a.plaka, a.yil,
            COALESCE(SUM(s.tuketim), 0) AS yearly_consum_l,
            COALESCE(SUM(s.mesafe_km), 0) AS yearly_km
        FROM araclar a
        LEFT JOIN seferler s ON a.id = s.arac_id
            AND s.is_deleted = FALSE
            AND s.tarih >= CURRENT_DATE - INTERVAL '365 days'
        WHERE a.aktif = TRUE AND a.is_deleted = FALSE
            AND a.yil IS NOT NULL
            AND a.yil < EXTRACT(YEAR FROM NOW()) - :age_threshold
        GROUP BY a.id, a.plaka, a.yil
    """
    rows = (
        (await uow.session.execute(text(sql), {"age_threshold": max_age_years}))
        .mappings()
        .all()
    )

    eligible = list(rows)
    n = len(eligible)
    if n == 0:
        return WhatIfResult(
            scenario_type="fleet_renewal",
            inputs={"max_age_years": max_age_years},
            yearly_savings_tl=0.0,
            upfront_cost_tl=0.0,
            payback_years=None,
            five_year_roi_pct=0.0,
            confidence=1.0,
            reasons=["Bu yaş eşiğinin üstünde aktif araç yok"],
        )

    yearly_l = sum(float(r["yearly_consum_l"] or 0) for r in eligible)
    yearly_savings_l = yearly_l * (expected_l_100km_improvement_pct / 100.0)
    yearly_savings_tl = yearly_savings_l * diesel_price_tl
    upfront = n * replacement_cost_per_vehicle_tl
    payback = upfront / yearly_savings_tl if yearly_savings_tl > 0 else None
    five_year_roi = (
        (5 * yearly_savings_tl - upfront) / upfront * 100 if upfront > 0 else 0.0
    )

    # CO2 azaltımı: (eski yıllık tüketim × eski faktör) − (yeni tüketim × Euro VI faktörü)
    # Yeni tüketim = eski × (1 − verimlilik iyileştirme %)
    co2_reduction = 0.0
    new_factor = 2.63  # Euro VI kg CO2/L
    improvement_ratio = 1.0 - expected_l_100km_improvement_pct / 100.0
    for r in eligible:
        old_factor = euro_class_for_year(r["yil"]).co2_factor_kg_per_l
        consum_l = float(r["yearly_consum_l"] or 0)
        co2_reduction += (
            consum_l * old_factor - consum_l * improvement_ratio * new_factor
        )

    confidence = 0.8 if n >= 5 else 0.6
    reasons = [
        f"{n} araç {max_age_years}+ yaş",
        f"Toplam yıllık tüketim: {yearly_l:,.0f} L",
        f"%{expected_l_100km_improvement_pct} verimlilik iyileştirme varsayımı",
    ]
    if payback is not None:
        reasons.append(f"Yatırım geri ödeme: {payback:.2f} yıl")

    return WhatIfResult(
        scenario_type="fleet_renewal",
        inputs={
            "max_age_years": max_age_years,
            "replacement_cost_per_vehicle_tl": replacement_cost_per_vehicle_tl,
            "expected_l_100km_improvement_pct": (expected_l_100km_improvement_pct),
            "diesel_price_tl": diesel_price_tl,
        },
        yearly_savings_tl=round(yearly_savings_tl, 0),
        upfront_cost_tl=round(upfront, 0),
        payback_years=round(payback, 2) if payback is not None else None,
        five_year_roi_pct=round(five_year_roi, 1),
        co2_reduction_kg=round(co2_reduction, 0),
        confidence=confidence,
        reasons=reasons,
    )


# ── Senaryo 2: Koçluk programı ROI ────────────────────────────────────
async def simulate_training_program(
    uow,
    *,
    improvement_pct: float,
    training_cost_per_driver_tl: float,
    diesel_price_tl: float = 50.0,
) -> WhatIfResult:
    """Tüm aktif şoförlere eğitim verirsem yıllık tasarruf?

    Konservatif lineer projeksiyon: filo yıllık L × improvement_pct.
    """
    from sqlalchemy import text

    sql = """
        SELECT
            COUNT(DISTINCT s.id) AS driver_count,
            COALESCE(SUM(t.tuketim), 0) AS yearly_l
        FROM soforler s
        LEFT JOIN seferler t ON t.sofor_id = s.id
            AND t.is_deleted = FALSE
            AND t.tarih >= CURRENT_DATE - INTERVAL '365 days'
        WHERE s.aktif = TRUE AND s.is_deleted = FALSE
    """
    row = (await uow.session.execute(text(sql))).mappings().one()
    n = int(row["driver_count"] or 0)
    yearly_l = float(row["yearly_l"] or 0)

    if n == 0 or yearly_l == 0:
        return WhatIfResult(
            scenario_type="training",
            inputs={"improvement_pct": improvement_pct},
            yearly_savings_tl=0.0,
            upfront_cost_tl=0.0,
            payback_years=None,
            five_year_roi_pct=0.0,
            confidence=0.5,
            reasons=["Aktif şoför veya yıllık sefer verisi yok"],
        )

    yearly_savings_l = yearly_l * (improvement_pct / 100.0)
    yearly_savings_tl = yearly_savings_l * diesel_price_tl
    upfront = n * training_cost_per_driver_tl
    payback = upfront / yearly_savings_tl if yearly_savings_tl > 0 else None
    five_year_roi = (
        (5 * yearly_savings_tl - upfront) / upfront * 100 if upfront > 0 else 0.0
    )

    return WhatIfResult(
        scenario_type="training",
        inputs={
            "improvement_pct": improvement_pct,
            "training_cost_per_driver_tl": training_cost_per_driver_tl,
            "diesel_price_tl": diesel_price_tl,
        },
        yearly_savings_tl=round(yearly_savings_tl, 0),
        upfront_cost_tl=round(upfront, 0),
        payback_years=round(payback, 2) if payback is not None else None,
        five_year_roi_pct=round(five_year_roi, 1),
        confidence=0.7,
        reasons=[
            f"{n} aktif şoför",
            f"Filo yıllık tüketim: {yearly_l:,.0f} L",
            f"%{improvement_pct} davranış iyileşmesi varsayımı",
        ],
    )


# ── Senaryo 3: Güzergah portföy (Monte Carlo) ─────────────────────────
async def simulate_route_portfolio(
    uow,
    *,
    drop_bottom_n: int,
    iterations: int = 100,
    diesel_price_tl: float = 50.0,
    random_seed: Optional[int] = None,
) -> WhatIfResult:
    """En kötü performans gösteren N güzergah çıkartılırsa tasarruf?

    Args:
        drop_bottom_n: kaç güzergah eleyeceğiz (en kötü deviation)
        iterations: Monte Carlo örnekleme sayısı (default 100)
        random_seed: test determinizmi için; None → her çağrı bağımsız
    """
    from sqlalchemy import text

    sql = """
        SELECT lok.id, lok.cikis_yeri, lok.varis_yeri,
            COUNT(s.id) AS trip_count,
            AVG(s.tuketim) AS avg_consum,
            AVG(s.tahmini_tuketim) AS avg_predicted,
            AVG(s.mesafe_km) AS avg_km
        FROM lokasyonlar lok
        JOIN seferler s ON s.guzergah_id = lok.id
            AND s.is_deleted = FALSE
            AND s.tuketim IS NOT NULL AND s.tahmini_tuketim > 0
            AND s.tarih >= CURRENT_DATE - INTERVAL '180 days'
        WHERE lok.aktif = TRUE AND lok.is_deleted = FALSE
        GROUP BY lok.id, lok.cikis_yeri, lok.varis_yeri
        HAVING COUNT(s.id) >= 3
        ORDER BY (AVG(s.tuketim) / NULLIF(AVG(s.tahmini_tuketim), 0)) DESC
        LIMIT :n
    """
    rows = (await uow.session.execute(text(sql), {"n": drop_bottom_n})).mappings().all()

    if not rows:
        return WhatIfResult(
            scenario_type="route_portfolio",
            inputs={"drop_bottom_n": drop_bottom_n},
            yearly_savings_tl=0.0,
            upfront_cost_tl=0.0,
            payback_years=None,
            five_year_roi_pct=0.0,
            confidence=0.5,
            reasons=[
                "Yeterli sefer-bazlı güzergah verisi yok (en az 3 sefer/güzergah)"
            ],
        )

    # Monte Carlo: her iterasyon farklı bir tasarruf örnekler
    rng = random.Random(random_seed) if random_seed is not None else random
    samples: List[float] = []
    for _ in range(iterations):
        total = 0.0
        for r in rows:
            avg_pred = float(r["avg_predicted"] or 0)
            if avg_pred <= 0:
                continue
            base_dev = (float(r["avg_consum"] or 0) - avg_pred) / avg_pred
            jitter_sigma = abs(base_dev) * 0.3
            jitter = rng.gauss(0, jitter_sigma) if jitter_sigma > 0 else 0
            sampled_dev = base_dev + jitter
            # 180g sample → yıllık × 2
            yearly_extra_l = (
                int(r["trip_count"]) * 2 * float(r["avg_consum"] or 0) * sampled_dev
            )
            total += max(0, yearly_extra_l) * diesel_price_tl
        samples.append(total)
    samples.sort()
    p10 = samples[int(0.1 * len(samples))]
    p50 = samples[int(0.5 * len(samples))]
    p90 = samples[int(0.9 * len(samples))]

    return WhatIfResult(
        scenario_type="route_portfolio",
        inputs={
            "drop_bottom_n": drop_bottom_n,
            "iterations": iterations,
            "diesel_price_tl": diesel_price_tl,
        },
        yearly_savings_tl=round(p50, 0),
        upfront_cost_tl=0.0,  # operasyonel değişiklik
        payback_years=0.0,
        five_year_roi_pct=0.0,
        confidence=0.65,
        monte_carlo={
            "p10": round(p10, 0),
            "p50": round(p50, 0),
            "p90": round(p90, 0),
            "iterations": iterations,
        },
        reasons=[
            f"{len(rows)} güzergah elenecek",
            (
                f"Belirsizlik bandı (Monte Carlo {iterations}×): "
                f"₺{p10:,.0f} → ₺{p90:,.0f}"
            ),
        ],
    )
