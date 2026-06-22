"""Feature E.3 (foundation) — Euro emisyon sınıfı + CO2 faktörü.

E.2 (what-if filo yenileme) ve E.3 (filo karbon raporu) için ortak
yardımcılar. E.2 sadece `euro_class_for_year` kullanır; tam `compute_fleet_carbon`
fonksiyonu E.3'te eklenecek.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §6
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EuroClass:
    name: str  # "VI", "V", ..., "0"
    co2_factor_kg_per_l: float  # dizel L başına kg CO2
    description: str  # "Euro VI" vb.


# Türkiye'de Euro sınıf zorunluluğu:
#   Euro VI — 2014+ (yeni araçlar)
#   Euro V  — 2009+
#   Euro IV — 2006+
#   Euro III— 2001+
#   Euro II — 1996+
#   Euro I  — 1992+
#   Euro 0  — 1991 ve öncesi
#
# CO2 faktörleri:
#   Baz: 2.63 kg CO2/L (Euro VI temiz dizel — Defra UK 2024)
#   Daha eski sınıflar yaş + bakım gerilemesi ile %5-22 artar.
#   Bu varsayım: literatür (ATA TMC 2021, ICCT 2023) ve filo gözleminden.
EURO_CLASSES: List[Tuple[Optional[int], EuroClass]] = [
    (2014, EuroClass("VI", 2.63, "Euro VI")),
    (2009, EuroClass("V", 2.68, "Euro V")),
    (2006, EuroClass("IV", 2.74, "Euro IV")),
    (2001, EuroClass("III", 2.81, "Euro III")),
    (1996, EuroClass("II", 2.92, "Euro II")),
    (1992, EuroClass("I", 3.05, "Euro I")),
    (None, EuroClass("0", 3.20, "Euro 0 (öncesi)")),
]
SECTOR_BENCHMARK_CO2_PER_KM = 0.72  # kg CO2/km — AB ortalama heavy-truck


def euro_class_for_year(yil: Optional[int]) -> EuroClass:
    """Araç imal yılına göre Euro emisyon sınıfı + CO2 faktörü.

    yil None ya da 0 → Euro 0 (en yüksek faktör; bilinmiyorsa konservatif).
    """
    if not yil or yil <= 0:
        return EURO_CLASSES[-1][1]
    for min_year, cls in EURO_CLASSES:
        if min_year is None or yil >= min_year:
            return cls
    return EURO_CLASSES[-1][1]


# ── E.3: compute_fleet_carbon ──────────────────────────────────────────


@dataclass
class TopEmitter:
    plaka: str
    co2_kg: float
    euro_class: str
    yearly_l: float


@dataclass
class FleetCarbonReport:
    period_start: date
    period_end: date
    total_co2_kg: float
    total_km: float
    co2_per_km: float
    benchmark_co2_per_km: float
    delta_pct: float  # benchmark üstü pozitif, altı negatif
    by_euro_class: Dict[str, float]  # {"VI": 30000, "V": 25000, ...}
    top_emitters: List[TopEmitter] = field(default_factory=list)
    vehicle_count: int = 0


async def compute_fleet_carbon(uow, *, period_days: int = 30) -> FleetCarbonReport:
    """Filo bazlı karbon raporu — Euro sınıfı bazında aggregat + top-10 emitor.

    Args:
        period_days: rapor periyodu (default 30 gün)

    Sonuç:
        FleetCarbonReport — total_co2 + km + benchmark karşılaştırma +
        Euro sınıfı bazında kırılım + top-10 emitor.
    """
    from sqlalchemy import text

    end = date.today()
    start = end - timedelta(days=period_days)

    sql = """
        SELECT a.id, a.plaka, a.yil,
            COALESCE(SUM(s.tuketim), 0)   AS total_l,
            COALESCE(SUM(s.mesafe_km), 0) AS total_km
        FROM araclar a
        LEFT JOIN seferler s ON a.id = s.arac_id
            AND s.is_deleted = FALSE
            AND s.tuketim IS NOT NULL
            AND s.tarih BETWEEN :start AND :end
        WHERE a.aktif = TRUE AND a.is_deleted = FALSE
        GROUP BY a.id, a.plaka, a.yil
    """
    rows = (
        (await uow.session.execute(text(sql), {"start": start, "end": end}))
        .mappings()
        .all()
    )

    total_co2 = 0.0
    total_km = 0.0
    by_class: Dict[str, float] = {}
    per_arac: List[TopEmitter] = []
    for r in rows:
        cls = euro_class_for_year(r["yil"])
        litres = float(r["total_l"] or 0)
        km = float(r["total_km"] or 0)
        co2 = litres * cls.co2_factor_kg_per_l
        total_co2 += co2
        total_km += km
        by_class[cls.name] = by_class.get(cls.name, 0.0) + co2
        if co2 > 0:
            per_arac.append(
                TopEmitter(
                    plaka=str(r["plaka"]),
                    co2_kg=round(co2, 0),
                    euro_class=cls.name,
                    yearly_l=round(litres, 0),
                )
            )

    co2_per_km = (total_co2 / total_km) if total_km > 0 else 0.0
    benchmark = SECTOR_BENCHMARK_CO2_PER_KM
    delta_pct = (co2_per_km - benchmark) / benchmark * 100 if benchmark > 0 else 0.0
    top_emitters = sorted(per_arac, key=lambda x: x.co2_kg, reverse=True)[:10]

    return FleetCarbonReport(
        period_start=start,
        period_end=end,
        total_co2_kg=round(total_co2, 0),
        total_km=round(total_km, 0),
        co2_per_km=round(co2_per_km, 3),
        benchmark_co2_per_km=benchmark,
        delta_pct=round(delta_pct, 1),
        by_euro_class={k: round(v, 0) for k, v in by_class.items()},
        top_emitters=top_emitters,
        vehicle_count=len(rows),
    )
