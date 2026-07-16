"""Feature E.3 (foundation) — Euro emisyon sınıfı + CO2 faktörü, saf (I/O yok).

E.2 (what-if filo yenileme) ve E.3 (filo karbon raporu) için ortak
yardımcılar. E.2 sadece `euro_class_for_year` kullanır.

Plan kaynağı: docs/superpowers/plans/2026-05-26-feature-e-strategic-cockpit-v3.md §6
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


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
