# Feature E — Strategic Cockpit (Yönetici Paneli v3)

**Tarih:** 2026-05-26
**Status:** PLAN — uygulamaya hazır
**Önceki sürümler:** Plan §E (orijinal, 25 satır) "12 ay grafik + slider what-if"
düzeyinde idi; bu plan vizyonu **AI-powered TIR fleet management'a uygun
stratejik cockpit'e** yükseltir. Kullanıcı geri bildirimi (2026-05-26):
"yönetici paneli projenin vizyon ve hedeflerine uygun değil, daha derin plan".

---

## 0. Özet (TL;DR)

LojiNext'in farkı **AI motor + closed-loop feedback** (D.4'te gördüğümüz gibi).
Klasik BI dashboard her filo yöneticisinin Tableau ile yapabileceği şey;
**Strategic Cockpit** bu farkı işletme stratejisine taşımak için 8 modül:

1. **Filo Verimliliği Endeksi** (composite KPI, tek sayı)
2. **3 senaryo What-if** (filo yenileme ROI, koçluk ROI, güzergah portföy)
3. **Per-vehicle karbon ayak izi** (Euro emisyon sınıfı + sektör kıyas)
4. **Compliance heatmap** (muayene + ehliyet, gelecek iterasyonda SRC/K1)
5. **Predictive cashflow** (90 gün — D.1, A/B/D motorlarının aggregat'ı)
6. **Cross-feature aggregator** (D.4 bakım gecikme zararı + A.5 koçluk etkisi
   + B hırsızlık zararı tek panel'de)
7. **Bus factor / risk yoğunlaşması** (top-N şoför/araç bağımlılığı)
8. **CEO 1-pager PDF** (5 KPI + 90-gün projeksiyon + 3 stratejik öneri)

Yeni ML modeli yok — mevcut motorların **aggregat aktörü**: her alt-modül
mevcut servisleri (PredictionService, MaintenancePredictor,
TripPlannerEngine, FuelTheftClassifier, DriverCoachingEngine) sorgular ve
toplar.

---

## 1. İş ihtiyacı: vizyon karşılaştırması

### Mevcut DashboardPage (operasyonel)

```
+----------------------------+
| Aktif sefer: 23            |
| Bekleyen: 7                |
| Toplam km (ay): 142,000    |
| Yakıt L (ay): 45,800       |
+----------------------------+
| [Aylık tüketim grafiği]    |
+----------------------------+
```

**Hedef kullanıcı:** Operasyon yöneticisi, günlük takip.
**Karar destekleme:** "Bugün ne yapmalıyım?" — operasyonel.

### Strategic Cockpit (yeni)

```
+-----------------------------------------+
| Filo Verimliliği Endeksi: 78/100  ↑ 4   |
| (Yakıt verimi 82 · Bakım 75 ·           |
|  Şoför skor 80 · Anomali kalitesi 73)   |
+-----------------------------------------+
| 90-gün cashflow projeksiyonu: ₺3.2M     |
| (Yakıt: 2.8M · Bakım: 320K · Ceza: 80K) |
+-----------------------------------------+
| Bus factor risk: Top-3 şoför ayrılırsa  |
| filodan kaybedilecek tasarruf: ₺180K/yıl|
+-----------------------------------------+
| Bakım gecikme zararı YTD: ₺145K         |
| (Filodaki 12 araç ortalama %7 fazla     |
|  yakar — D.4 feedback)                  |
+-----------------------------------------+
| What-if: Filo yenileme (12 araç > 15y)  |
| ROI: 5-yıl payback 3.2y, karbon -180tCO2|
+-----------------------------------------+
| Compliance heatmap                       |
| 3 araç muayene < 30g · 7 ehliyet kontrol|
+-----------------------------------------+
| [CEO 1-pager PDF İndir]                 |
+-----------------------------------------+
```

**Hedef kullanıcı:** İcra Kurulu, CFO, Filo Direktörü.
**Karar destekleme:** "Önümüzdeki 12 ay nereye yatırmalıyım?" — stratejik.

### Hedef KPI

3 ay sonra ölçülecek:
- CEO 1-pager haftalık görüntülenme: ≥ %80 hafta
- What-if simülasyon kullanım: en az 2/hafta
- Compliance gecikme: ekstreme oranı %50 düşmeli (uyarılarla)

---

## 2. Karar matrisi (5 kritik soru ve cevapları)

### Q1 — Filo Verimliliği Endeksi formülü?

**Cevap:** 4 alt-skor weighted average + tek toplam (0-100).

```
fvi = round(
      0.35 * fuel_score
    + 0.25 * maintenance_score
    + 0.25 * driver_score
    + 0.15 * anomaly_quality_score
)
```

| Alt-skor | Veri kaynağı | Normalize |
|---|---|---|
| `fuel_score` | Aktif filo L/100km medyanı vs hedef (Arac.hedef_tuketim) | `100 * (1 - clamp((avg - target) / target, -0.3, 0.3) - 0.3) / 0.6` |
| `maintenance_score` | D.1 predictable=True araçların %50+ confidence + geciken oran düşük | `100 * (1 - overdue_count / total_active)` |
| `driver_score` | Şoför hibrit skorların ortalaması × 100 | `min(100, mean(sofor.score * 50))` |
| `anomaly_quality_score` | Anomali ack+resolved oranı / total open | `100 * resolved_or_ack / total_30d` |

**Cold-start:** Veri yoksa (filo yeni) → skor 75 (varsayılan nötr) +
`confidence` low.

### Q2 — What-if engine yaklaşımı?

**Cevap:** Her senaryo için en uygun method, ML modeli yok, deterministik
forward projection + lightweight stokastik.

| Senaryo | Method | Süre |
|---|---|---|
| **Filo yenileme ROI** | Lineer (Euro VI tasarrufu × yıl × araç) − yenileme maliyeti | <100ms |
| **Koçluk programı ROI** | Lineer (yakıt × improvement_pct × şoför sayısı) − eğitim maliyeti | <100ms |
| **Güzergah portföy** | Top-N worst-deviation route'ları çıkar, tasarruf hesapla; Monte Carlo 100 iterasyonla belirsizlik aralığı | ~500ms |

Tüm 3 senaryo aynı `/reports/what-if` endpoint'inde — `scenario_type` parametresi.

### Q3 — Per-vehicle karbon hesabı?

**Cevap:** Euro emisyon sınıfına göre dinamik faktör. `Arac.yil` →
class derivation → CO2/L çarpanı.

```python
EURO_CLASSES = [
    # (min_year, class, co2_factor_kg_per_l, description)
    (2014, "VI",  2.63, "Euro VI"),
    (2009, "V",   2.68, "Euro V"),
    (2006, "IV",  2.74, "Euro IV"),
    (2001, "III", 2.81, "Euro III"),
    (1996, "II",  2.92, "Euro II"),
    (1992, "I",   3.05, "Euro I"),
    (None, "0",   3.20, "Euro 0 / öncesi"),
]
```

(Defra UK 2024 ortalamasından + yaşa göre %5-20 artışla türetildi.)

**Filo karbon raporu:**
```
total_co2_kg = Σ (sefer.tuketim × EURO_FACTOR(arac.yil))
co2_per_km   = total_co2_kg / total_km
benchmark    = 0.72 kg/km (AB ortalama heavy-truck)
delta_pct    = (co2_per_km - benchmark) / benchmark * 100
```

UI: aylık trend + sektör karşılaştırma + araç bazında top-10 emitor.

### Q4 — Predictive cashflow nasıl hesaplanır?

**Cevap:** 3 ana kalem, 90-gün ileriye, mevcut servislerin aggregat'ı.

```
yakit_projection = Σ (active_plans × predict_consumption × birim_l_fiyat)
bakim_projection = Σ (D.1.predict_all() × avg_bakim_cost)
ceza_projection  = trailing_90d_ceza_avg × 1.0  (basit trailing)
```

**Birim fiyat:** `settings.LITRE_DIESEL_TL` (config, manuel güncellenir).
**Avg bakım maliyeti:** son 90 gün tamamlanmış bakım `maliyet` ortalama.
**Ceza:** mevcut `cezalar` tablosundan (varsa) trailing.

Sonuç: haftalık breakdown (12 hafta) + 3-kalem stack chart.

### Q5 — CEO 1-pager içerik?

**Cevap:** A4 dikey, 1 sayfa, görsel ağırlıklı.

```
┌─────────────────────────────────────────┐
│ LojiNext Strategic Cockpit              │
│ Hafta: 2026-05-26  · CEO görünümü       │
│─────────────────────────────────────────│
│ ┃ Filo Verimliliği Endeksi             ┃│
│ ┃        78 / 100   ↑ 4                ┃│
│ ┃ Yakıt: 82  Bakım: 75  Şoför: 80      ┃│
│─────────────────────────────────────────│
│ Bu Ay Performans                         │
│ • Toplam yakıt:    45,820 L  (-2.1%)    │
│ • Maliyet/km:      ₺ 8.42    (-1.8%)    │
│ • Bakım proaktif:  72%       (+5.0pt)    │
│ • Şoför skor avg:  1.18      (+0.04)    │
│ • Karbon t/CO2:    121.5     (-3.2%)    │
│─────────────────────────────────────────│
│ 90 Gün Projeksiyon                       │
│   [stack-bar grafik: Yakıt+Bakım+Ceza]  │
│   Toplam tahmin: ₺ 3,180,000             │
│─────────────────────────────────────────│
│ 🎯 Stratejik Öneriler                    │
│ 1. 4 araç > 15y — yenileme ROI 3.2y     │
│ 2. Top 3 şoför ayrılırsa risk ₺180K/yıl │
│ 3. Bakım gecikme YTD: ₺145K (D.4)       │
└─────────────────────────────────────────┘
```

Reportlab + matplotlib (chart PNG embed). Türkçe font (DejaVu Sans, mevcut
PDFReportGenerator'da kayıtlı).

---

## 3. Mimari (yeni + değişen dosyalar)

### Backend

```
app/
├── core/
│   ├── ml/
│   │   ├── fleet_efficiency_index.py        # NEW (E.1) — composite KPI
│   │   ├── bus_factor.py                    # NEW (E.7) — risk yoğunlaşması
│   │   └── carbon_footprint.py              # NEW (E.3) — Euro sınıf + CO2
│   └── services/
│       ├── what_if_engine.py                # NEW (E.2) — 3 senaryo
│       ├── cashflow_projector.py            # NEW (E.5) — 90g aggregator
│       ├── cross_feature_aggregator.py      # NEW (E.6) — D.4+A.5+B zarar
│       ├── compliance_scanner.py            # NEW (E.4) — muayene+ehliyet
│       └── executive_pdf_generator.py       # NEW (E.9) — CEO 1-pager
├── api/v1/endpoints/
│   └── executive.py                         # NEW (E.1-E.9) — 9 endpoint
├── schemas/
│   └── executive.py                         # NEW — tüm response schemas
├── config.py                                # MODIFY — EXECUTIVE_*_ENABLED +
│                                              LITRE_DIESEL_TL + benchmark'lar
└── tests/
    ├── unit/
    │   ├── test_fleet_efficiency_index.py   # NEW (E.1)
    │   ├── test_what_if_engine.py           # NEW (E.2)
    │   ├── test_carbon_footprint.py         # NEW (E.3)
    │   ├── test_compliance_scanner.py       # NEW (E.4)
    │   ├── test_cashflow_projector.py       # NEW (E.5)
    │   ├── test_cross_feature_aggregator.py # NEW (E.6)
    │   ├── test_bus_factor.py               # NEW (E.7)
    │   └── test_executive_pdf.py            # NEW (E.9)
    └── integration/
        └── test_executive_endpoints.py      # NEW (E.1-E.9)
```

### Frontend

```
frontend/src/
├── pages/
│   └── ExecutivePage.tsx                    # NEW (E.8) — strategic cockpit
├── components/executive/
│   ├── FleetEfficiencyCard.tsx              # NEW (E.1)
│   ├── WhatIfPanel.tsx                      # NEW (E.2)
│   ├── CarbonReportCard.tsx                 # NEW (E.3)
│   ├── ComplianceHeatmap.tsx                # NEW (E.4)
│   ├── CashflowProjectionChart.tsx          # NEW (E.5)
│   ├── CrossFeatureSavings.tsx              # NEW (E.6)
│   ├── BusFactorWidget.tsx                  # NEW (E.7)
│   ├── DownloadPdfButton.tsx                # NEW (E.9)
│   └── __tests__/
│       └── ...                              # NEW — 8 vitest dosyası
├── services/api/
│   └── executive-service.ts                 # NEW — 9 endpoint wrapper
├── resources/tr/
│   └── executive.ts                         # NEW — Türkçe metinler
├── hooks/
│   └── useExecutive.ts                      # NEW — 9 RQ hook
├── App.tsx                                  # MODIFY — /executive route
└── layouts/
    └── EliteLayout.tsx                      # MODIFY — sidebar item (RBAC)
```

**Migration gerekmez** — yeni tablo yok, sadece okunan veri üzerine türev hesap.

---

## 4. E.1 — Filo Verimliliği Endeksi

### 4.1 `app/core/ml/fleet_efficiency_index.py`

```python
"""Feature E.1 — Filo Verimliliği Endeksi (FVI).

4 alt-skorun ağırlıklı ortalaması; tek 0-100 sayı + alt-skor breakdown.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


SUBSCORE_WEIGHTS = {
    "fuel": 0.35,
    "maintenance": 0.25,
    "driver": 0.25,
    "anomaly_quality": 0.15,
}
COLD_START_DEFAULT = 75.0   # veri yokken nötr


@dataclass
class FleetEfficiencyBreakdown:
    """Alt-skor + toplam endeks + trend."""
    fvi: float                        # 0-100
    fuel_score: float                 # 0-100
    maintenance_score: float          # 0-100
    driver_score: float               # 0-100
    anomaly_quality_score: float      # 0-100
    confidence: float                 # 0-1
    trend_30d: Optional[float] = None # geçen aya göre delta
    reasons: List[str] = field(default_factory=list)
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _fuel_score(avg_l_100km: Optional[float], target: float) -> tuple[float, str]:
    """Filo ortalaması hedeften ne kadar sapıyor? Düşük tüketim = yüksek skor."""
    if avg_l_100km is None or target <= 0:
        return COLD_START_DEFAULT, "Yetersiz yakıt verisi (cold-start)"
    dev = (avg_l_100km - target) / target  # negatif = tasarruf
    clamped = max(-0.3, min(0.3, dev))     # [-30%, +30%]
    score = 100 * (1 - (clamped + 0.3) / 0.6)
    return round(score, 1), f"Filo ort. {avg_l_100km:.1f} L/100km, hedef {target:.1f}"


def _maintenance_score(overdue_count: int, total_active: int) -> tuple[float, str]:
    if total_active == 0:
        return COLD_START_DEFAULT, "Aktif araç yok"
    score = 100 * (1 - overdue_count / total_active)
    return round(score, 1), f"{overdue_count}/{total_active} araç bakım gecikmiş"


def _driver_score(avg_hybrid: Optional[float]) -> tuple[float, str]:
    """Sofor.score 0.1-2.0 aralığında; 1.0 = nötr, 2.0 = mükemmel."""
    if avg_hybrid is None:
        return COLD_START_DEFAULT, "Şoför skor verisi yok"
    score = min(100.0, max(0.0, (avg_hybrid - 0.5) * 100 / 1.5))
    return round(score, 1), f"Filo şoför avg skor: {avg_hybrid:.2f}"


def _anomaly_quality_score(
    resolved: int, acknowledged: int, total: int
) -> tuple[float, str]:
    """Resolved + acknowledged oranı / total. Düşük = anomali aksiyon
    alınmıyor."""
    if total == 0:
        return COLD_START_DEFAULT, "30 günde anomali yok"
    score = 100 * (resolved + acknowledged) / total
    return round(score, 1), (
        f"{resolved + acknowledged}/{total} anomali aksiyon almış (30g)"
    )


def compute_fvi(
    *,
    fuel_avg: Optional[float], fuel_target: float,
    overdue_maintenance: int, total_active_vehicles: int,
    driver_avg_hybrid: Optional[float],
    resolved_anomalies: int, acked_anomalies: int, total_anomalies: int,
    previous_fvi: Optional[float] = None,
) -> FleetEfficiencyBreakdown:
    f_score, f_reason = _fuel_score(fuel_avg, fuel_target)
    m_score, m_reason = _maintenance_score(overdue_maintenance, total_active_vehicles)
    d_score, d_reason = _driver_score(driver_avg_hybrid)
    a_score, a_reason = _anomaly_quality_score(
        resolved_anomalies, acked_anomalies, total_anomalies
    )

    fvi = round(
        SUBSCORE_WEIGHTS["fuel"] * f_score
        + SUBSCORE_WEIGHTS["maintenance"] * m_score
        + SUBSCORE_WEIGHTS["driver"] * d_score
        + SUBSCORE_WEIGHTS["anomaly_quality"] * a_score,
        1,
    )

    # Confidence: kaç alt-skor cold-start değil?
    real_signals = sum(
        1 for s in (f_score, m_score, d_score, a_score)
        if s != COLD_START_DEFAULT
    )
    confidence = round(real_signals / 4, 2)

    trend = None
    if previous_fvi is not None:
        trend = round(fvi - previous_fvi, 1)

    return FleetEfficiencyBreakdown(
        fvi=fvi, fuel_score=f_score, maintenance_score=m_score,
        driver_score=d_score, anomaly_quality_score=a_score,
        confidence=confidence, trend_30d=trend,
        reasons=[f_reason, m_reason, d_reason, a_reason],
    )


async def gather_fvi_inputs(uow, *, days_back: int = 30) -> Dict[str, Any]:
    """Endeks için gerekli tüm aggregat'ları tek round-trip'te DB'den çek."""
    from sqlalchemy import text
    cutoff = date.today() - timedelta(days=days_back)
    sql = """
        WITH active_arac AS (
            SELECT id, hedef_tuketim FROM araclar
            WHERE aktif = TRUE AND is_deleted = FALSE
        ),
        fuel AS (
            SELECT AVG(
                CASE WHEN s.mesafe_km > 0 THEN s.tuketim * 100 / s.mesafe_km END
            ) AS avg_l_100km
            FROM seferler s
            WHERE s.is_deleted = FALSE AND s.tuketim IS NOT NULL
              AND s.tarih >= :cutoff
        ),
        driver_avg AS (
            SELECT AVG(score) AS avg_score FROM soforler
            WHERE aktif = TRUE AND is_deleted = FALSE
        ),
        anomaly_30d AS (
            SELECT
                COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) AS resolved,
                COUNT(*) FILTER (WHERE acknowledged_at IS NOT NULL
                                  AND resolved_at IS NULL) AS acked,
                COUNT(*) AS total
            FROM anomalies WHERE tarih >= :cutoff
        ),
        overdue AS (
            SELECT COUNT(*) AS cnt FROM araclar a
            WHERE a.aktif = TRUE AND a.is_deleted = FALSE
              AND NOT EXISTS (
                SELECT 1 FROM arac_bakimlari b
                WHERE b.arac_id = a.id AND b.tamamlandi = TRUE
                  AND b.bakim_tipi = 'PERIYODIK'
                  AND b.bakim_tarihi >= CURRENT_DATE - INTERVAL '365 days'
              )
        )
        SELECT
            (SELECT AVG(hedef_tuketim) FROM active_arac) AS target,
            (SELECT COUNT(*) FROM active_arac) AS total_active,
            (SELECT avg_l_100km FROM fuel) AS fuel_avg,
            (SELECT avg_score FROM driver_avg) AS driver_avg,
            (SELECT resolved FROM anomaly_30d) AS resolved,
            (SELECT acked FROM anomaly_30d) AS acked,
            (SELECT total FROM anomaly_30d) AS total_anomalies,
            (SELECT cnt FROM overdue) AS overdue_count
    """
    row = (await uow.session.execute(text(sql), {"cutoff": cutoff})).mappings().one()
    return dict(row)
```

### 4.2 Endpoint

`GET /reports/executive/kpi`:
- Cache 30 dk Redis (`executive:fvi:current`)
- RBAC: `super_admin` veya `fleet_manager`
- Önceki 30g'lik FVI'yi history table'a yazılmıyor → trend için aynı SQL'i
  60g önceki kesimle ikinci kez çalıştırıp basit yaklaşıklık ya da
  v1'de trend=None (cold-start).

### 4.3 Test stratejisi

**Pure-unit:**
- `_fuel_score` (4 senaryo: cold-start, hedef altı, tam hedef, hedef üstü)
- `_maintenance_score` (3: total=0, hepsi geç, hepsi taze)
- `_driver_score` (3: None, min, max)
- `_anomaly_quality_score` (3)
- `compute_fvi` (3 e2e: full data, cold-start, partial)

**Integration:**
- DB seed: 3 araç + 5 sefer + 2 anomali → endpoint 200 + breakdown.

---

## 5. E.2 — What-if Simülatörü

### 5.1 `app/core/services/what_if_engine.py`

```python
"""Feature E.2 — 3 senaryo: filo yenileme, koçluk, güzergah portföy.

Tek endpoint /reports/what-if; scenario_type param ile yönlendirilir.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional


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
    monte_carlo: Optional[Dict[str, float]] = None   # P10/P50/P90 (route_portfolio için)
    reasons: List[str] = None


# ── Senaryo 1: Filo yenileme ROI ──────────────────────────────────────
async def simulate_fleet_renewal(
    uow, *, max_age_years: int, replacement_cost_per_vehicle_tl: float,
    expected_l_100km_improvement_pct: float = 15.0,
    diesel_price_tl: float = 50.0,
) -> WhatIfResult:
    """X yaş üstü araçları Euro VI ile değiştirirsem yıllık tasarruf?"""
    from sqlalchemy import text
    from app.core.ml.carbon_footprint import euro_class_for_year

    sql = """
        SELECT a.id, a.plaka, a.yil,
            COALESCE(SUM(s.tuketim), 0) AS yearly_consum_l,
            COALESCE(SUM(s.mesafe_km), 0) AS yearly_km
        FROM araclar a
        LEFT JOIN seferler s ON a.id = s.arac_id
            AND s.is_deleted = FALSE
            AND s.tarih >= CURRENT_DATE - INTERVAL '365 days'
        WHERE a.aktif = TRUE AND a.is_deleted = FALSE
            AND a.yil < EXTRACT(YEAR FROM NOW()) - :age_threshold
        GROUP BY a.id
    """
    rows = (await uow.session.execute(
        text(sql), {"age_threshold": max_age_years}
    )).mappings().all()

    eligible = list(rows)
    n = len(eligible)
    if n == 0:
        return WhatIfResult(
            scenario_type="fleet_renewal",
            inputs={"max_age_years": max_age_years},
            yearly_savings_tl=0, upfront_cost_tl=0,
            payback_years=None, five_year_roi_pct=0.0,
            confidence=1.0,
            reasons=["Bu yaş eşiğinin üstünde araç yok"],
        )

    yearly_l = sum(r["yearly_consum_l"] for r in eligible)
    yearly_savings_l = yearly_l * (expected_l_100km_improvement_pct / 100)
    yearly_savings_tl = yearly_savings_l * diesel_price_tl
    upfront = n * replacement_cost_per_vehicle_tl
    payback = upfront / yearly_savings_tl if yearly_savings_tl > 0 else None
    five_year_roi = (
        (5 * yearly_savings_tl - upfront) / upfront * 100
        if upfront > 0 else 0.0
    )

    # CO2 azaltımı: eski araçlar mevcut sınıflarından, yeni Euro VI'ya
    co2_reduction = 0.0
    for r in eligible:
        old_factor = euro_class_for_year(r["yil"]).co2_factor_kg_per_l
        new_factor = 2.63  # Euro VI
        co2_reduction += (r["yearly_consum_l"] * (old_factor - new_factor))

    reasons = [
        f"{n} araç {max_age_years}+ yaş",
        f"Toplam yıllık tüketim: {yearly_l:,.0f} L",
        f"%{expected_l_100km_improvement_pct} verimlilik iyileştirme",
    ]
    return WhatIfResult(
        scenario_type="fleet_renewal",
        inputs={"max_age_years": max_age_years,
                "replacement_cost_per_vehicle_tl": replacement_cost_per_vehicle_tl,
                "expected_l_100km_improvement_pct": expected_l_100km_improvement_pct},
        yearly_savings_tl=round(yearly_savings_tl, 0),
        upfront_cost_tl=round(upfront, 0),
        payback_years=round(payback, 2) if payback else None,
        five_year_roi_pct=round(five_year_roi, 1),
        co2_reduction_kg=round(co2_reduction, 0),
        confidence=0.8 if n >= 5 else 0.6,
        reasons=reasons,
    )


# ── Senaryo 2: Koçluk programı ROI ────────────────────────────────────
async def simulate_training_program(
    uow, *, improvement_pct: float, training_cost_per_driver_tl: float,
    diesel_price_tl: float = 50.0,
) -> WhatIfResult:
    """Tüm aktif şoförlere eğitim verirsem yıllık tasarruf?"""
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
            yearly_savings_tl=0, upfront_cost_tl=0,
            payback_years=None, five_year_roi_pct=0.0,
            confidence=0.5, reasons=["Aktif şoför veya sefer verisi yok"],
        )

    yearly_savings_l = yearly_l * (improvement_pct / 100)
    yearly_savings_tl = yearly_savings_l * diesel_price_tl
    upfront = n * training_cost_per_driver_tl
    payback = upfront / yearly_savings_tl if yearly_savings_tl > 0 else None
    five_year_roi = (
        (5 * yearly_savings_tl - upfront) / upfront * 100
        if upfront > 0 else 0.0
    )

    return WhatIfResult(
        scenario_type="training",
        inputs={"improvement_pct": improvement_pct,
                "training_cost_per_driver_tl": training_cost_per_driver_tl,
                "diesel_price_tl": diesel_price_tl},
        yearly_savings_tl=round(yearly_savings_tl, 0),
        upfront_cost_tl=round(upfront, 0),
        payback_years=round(payback, 2) if payback else None,
        five_year_roi_pct=round(five_year_roi, 1),
        confidence=0.7,
        reasons=[
            f"{n} aktif şoför",
            f"Filo yıllık tüketim: {yearly_l:,.0f} L",
            f"%{improvement_pct} iyileşme varsayımı",
        ],
    )


# ── Senaryo 3: Güzergah portföy optimizasyonu (Monte Carlo) ────────────
async def simulate_route_portfolio(
    uow, *, drop_bottom_n: int, iterations: int = 100,
    diesel_price_tl: float = 50.0,
) -> WhatIfResult:
    """En kötü performans gösteren N güzergahı çıkar; tasarruf belirsizlik ile."""
    import random
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
        GROUP BY lok.id
        HAVING COUNT(s.id) >= 3
        ORDER BY (AVG(s.tuketim) / AVG(s.tahmini_tuketim)) DESC
        LIMIT :n
    """
    rows = (await uow.session.execute(
        text(sql), {"n": drop_bottom_n}
    )).mappings().all()

    if not rows:
        return WhatIfResult(
            scenario_type="route_portfolio",
            inputs={"drop_bottom_n": drop_bottom_n},
            yearly_savings_tl=0, upfront_cost_tl=0,
            payback_years=None, five_year_roi_pct=0.0,
            confidence=0.5,
            reasons=["Yeterli güzergah verisi yok"],
        )

    # Yıllık tasarruf (deterministik base)
    yearly_savings_base = 0.0
    for r in rows:
        deviation = (r["avg_consum"] - r["avg_predicted"]) / r["avg_predicted"]
        # Bu güzergahtaki yıllık ekstra tüketim = trip × avg_consum × deviation × 2 (180g → 360g)
        yearly_extra_l = r["trip_count"] * 2 * r["avg_consum"] * deviation
        yearly_savings_base += max(0, yearly_extra_l) * diesel_price_tl

    # Monte Carlo: her güzergah için deviation varyansı ±%30 normal dağılım
    samples: List[float] = []
    for _ in range(iterations):
        total = 0.0
        for r in rows:
            base_dev = (r["avg_consum"] - r["avg_predicted"]) / r["avg_predicted"]
            jitter = random.gauss(0, abs(base_dev) * 0.3)
            sampled_dev = base_dev + jitter
            yearly_extra_l = r["trip_count"] * 2 * r["avg_consum"] * sampled_dev
            total += max(0, yearly_extra_l) * diesel_price_tl
        samples.append(total)
    samples.sort()
    p10 = samples[int(0.1 * len(samples))]
    p50 = samples[int(0.5 * len(samples))]
    p90 = samples[int(0.9 * len(samples))]

    return WhatIfResult(
        scenario_type="route_portfolio",
        inputs={"drop_bottom_n": drop_bottom_n, "iterations": iterations},
        yearly_savings_tl=round(p50, 0),
        upfront_cost_tl=0,  # operasyonel değişiklik
        payback_years=0.0,
        five_year_roi_pct=0.0,
        confidence=0.65,
        monte_carlo={"p10": round(p10, 0), "p50": round(p50, 0), "p90": round(p90, 0)},
        reasons=[
            f"{len(rows)} güzergah eleneceğinde tasarruf",
            f"Belirsizlik: P10 ₺{p10:,.0f} → P90 ₺{p90:,.0f}",
        ],
    )
```

### 5.2 Endpoint

```python
@router.post("/reports/what-if", response_model=WhatIfResponse)
async def run_what_if(
    payload: WhatIfRequest,
    current_admin: Annotated[Kullanici, Depends(
        require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])
    )],
):
    if not settings.EXECUTIVE_WHAT_IF_ENABLED:
        raise HTTPException(503, "What-if devre dışı")
    async with UnitOfWork() as uow:
        if payload.scenario_type == "fleet_renewal":
            result = await simulate_fleet_renewal(uow, **payload.fleet_renewal.dict())
        elif payload.scenario_type == "training":
            result = await simulate_training_program(uow, **payload.training.dict())
        elif payload.scenario_type == "route_portfolio":
            result = await simulate_route_portfolio(uow, **payload.route_portfolio.dict())
    await log_audit_event(...)  # PII'siz audit
    return WhatIfResponse.from_result(result)
```

### 5.3 Test

5+ pure-unit (her senaryo için happy + edge + cold-start) + 3 integration
(her senaryo için DB seed → endpoint).

---

## 6. E.3 — Per-Vehicle Karbon Ayak İzi

### 6.1 `app/core/ml/carbon_footprint.py`

```python
"""Feature E.3 — Euro emisyon sınıfından dinamik karbon faktörü."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


@dataclass
class EuroClass:
    name: str                 # "VI", "V", ...
    co2_factor_kg_per_l: float
    description: str          # "Euro VI" vb.


EURO_CLASSES = [
    (2014, EuroClass("VI",  2.63, "Euro VI")),
    (2009, EuroClass("V",   2.68, "Euro V")),
    (2006, EuroClass("IV",  2.74, "Euro IV")),
    (2001, EuroClass("III", 2.81, "Euro III")),
    (1996, EuroClass("II",  2.92, "Euro II")),
    (1992, EuroClass("I",   3.05, "Euro I")),
    (None, EuroClass("0",   3.20, "Euro 0 (öncesi)")),
]
SECTOR_BENCHMARK_CO2_PER_KM = 0.72   # kg CO2/km (AB ortalama heavy-truck)


def euro_class_for_year(yil: Optional[int]) -> EuroClass:
    """Araç yılına göre Euro sınıf + CO2 faktörü."""
    if not yil:
        return EURO_CLASSES[-1][1]
    for min_year, cls in EURO_CLASSES:
        if min_year is None or yil >= min_year:
            return cls
    return EURO_CLASSES[-1][1]


@dataclass
class FleetCarbonReport:
    period_start: date
    period_end: date
    total_co2_kg: float
    total_km: float
    co2_per_km: float
    benchmark_co2_per_km: float
    delta_pct: float           # benchmark üstü/altı
    by_euro_class: dict        # {"VI": 30000kg, "V": 25000kg, ...}
    top_emitters: list         # top 10 araç plaka + CO2


async def compute_fleet_carbon(
    uow, *, period_days: int = 30
) -> FleetCarbonReport:
    from sqlalchemy import text
    end = date.today()
    start = end - timedelta(days=period_days)

    sql = """
        SELECT a.id, a.plaka, a.yil,
            COALESCE(SUM(s.tuketim), 0) AS total_l,
            COALESCE(SUM(s.mesafe_km), 0) AS total_km
        FROM araclar a
        LEFT JOIN seferler s ON a.id = s.arac_id
            AND s.is_deleted = FALSE AND s.tuketim IS NOT NULL
            AND s.tarih BETWEEN :start AND :end
        WHERE a.aktif = TRUE AND a.is_deleted = FALSE
        GROUP BY a.id
    """
    rows = (await uow.session.execute(
        text(sql), {"start": start, "end": end}
    )).mappings().all()

    total_co2 = 0.0
    total_km = 0.0
    by_class: dict = {}
    per_arac = []
    for r in rows:
        cls = euro_class_for_year(r["yil"])
        co2 = float(r["total_l"]) * cls.co2_factor_kg_per_l
        total_co2 += co2
        total_km += float(r["total_km"])
        by_class[cls.name] = by_class.get(cls.name, 0) + co2
        per_arac.append({"plaka": r["plaka"], "co2_kg": round(co2, 0),
                         "euro_class": cls.name})

    co2_per_km = total_co2 / total_km if total_km > 0 else 0.0
    delta_pct = (
        (co2_per_km - SECTOR_BENCHMARK_CO2_PER_KM)
        / SECTOR_BENCHMARK_CO2_PER_KM * 100
        if SECTOR_BENCHMARK_CO2_PER_KM > 0 else 0.0
    )
    top_emitters = sorted(per_arac, key=lambda x: x["co2_kg"], reverse=True)[:10]

    return FleetCarbonReport(
        period_start=start, period_end=end,
        total_co2_kg=round(total_co2, 0),
        total_km=round(total_km, 0),
        co2_per_km=round(co2_per_km, 3),
        benchmark_co2_per_km=SECTOR_BENCHMARK_CO2_PER_KM,
        delta_pct=round(delta_pct, 1),
        by_euro_class={k: round(v, 0) for k, v in by_class.items()},
        top_emitters=top_emitters,
    )
```

### 6.2 Endpoint

`GET /reports/executive/carbon?days=30`:
- 1 saat cache
- Response: FleetCarbonReport + sectoral comparison + per-vehicle top-10

### 6.3 Test

- `euro_class_for_year` (7 senaryo, sınır yıllar)
- `compute_fleet_carbon` cold-start (boş veri)
- Aggregat doğruluğu (sentetik veri ile)

---

## 7. E.4 — Compliance Heatmap

### 7.1 Kapsam (v1)

Mevcut DB alanları:
- `araclar.muayene_tarihi`
- `dorseler.muayene_tarihi`
- `soforler.ehliyet_sinifi` (no expiry date stored — bu v1'de kapsamayız)

**v1 scope:** Sadece muayene takibi (araç + dorse). SRC/K1/tachograph
v2'de DB migration ile eklenecek (açık not §17).

### 7.2 `app/core/services/compliance_scanner.py`

```python
"""Feature E.4 — Compliance heatmap v1: muayene yaklaşma/gecikme."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List


@dataclass
class ComplianceItem:
    entity_type: str          # "arac" or "dorse"
    entity_id: int
    plaka: str
    field: str                # "muayene"
    expiry_date: date
    days_until: int           # negatif = geçmiş
    risk_level: str           # "overdue", "soon", "normal", "low"


def _risk_for_days(days: int) -> str:
    if days < 0:
        return "overdue"
    if days <= 14:
        return "soon"
    if days <= 60:
        return "normal"
    return "low"


async def scan_compliance(
    uow, *, days_horizon: int = 90
) -> List[ComplianceItem]:
    """Önümüzdeki N gün veya geçmiş muayeneleri liste."""
    from sqlalchemy import text
    today = date.today()
    horizon = today + timedelta(days=days_horizon)

    items: List[ComplianceItem] = []

    arac_rows = (await uow.session.execute(text("""
        SELECT id, plaka, muayene_tarihi FROM araclar
        WHERE aktif = TRUE AND is_deleted = FALSE
          AND muayene_tarihi IS NOT NULL
          AND muayene_tarihi <= :horizon
        ORDER BY muayene_tarihi
    """), {"horizon": horizon})).mappings().all()

    for r in arac_rows:
        days = (r["muayene_tarihi"] - today).days
        items.append(ComplianceItem(
            entity_type="arac", entity_id=int(r["id"]),
            plaka=str(r["plaka"]), field="muayene",
            expiry_date=r["muayene_tarihi"], days_until=days,
            risk_level=_risk_for_days(days),
        ))

    dorse_rows = (await uow.session.execute(text("""
        SELECT id, plaka, muayene_tarihi FROM dorseler
        WHERE aktif = TRUE AND is_deleted = FALSE
          AND muayene_tarihi IS NOT NULL
          AND muayene_tarihi <= :horizon
        ORDER BY muayene_tarihi
    """), {"horizon": horizon})).mappings().all()

    for r in dorse_rows:
        days = (r["muayene_tarihi"] - today).days
        items.append(ComplianceItem(
            entity_type="dorse", entity_id=int(r["id"]),
            plaka=str(r["plaka"]), field="muayene",
            expiry_date=r["muayene_tarihi"], days_until=days,
            risk_level=_risk_for_days(days),
        ))

    return sorted(items, key=lambda x: x.days_until)
```

### 7.3 Test

- `_risk_for_days` 4 sınır
- `scan_compliance` mock'lu integration: 2 araç + 1 dorse → 3 item

---

## 8. E.5 — Predictive Cashflow (90 gün)

### 8.1 `app/core/services/cashflow_projector.py`

```python
"""Feature E.5 — 90 gün cashflow projeksiyonu (yakıt + bakım + ceza)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List


@dataclass
class CashflowWeek:
    week_start: date
    fuel_tl: float
    maintenance_tl: float
    penalty_tl: float
    total_tl: float


@dataclass
class CashflowProjection:
    horizon_days: int
    weeks: List[CashflowWeek]
    total_fuel_tl: float
    total_maintenance_tl: float
    total_penalty_tl: float
    grand_total_tl: float
    confidence: float
    assumptions: Dict[str, float]   # diesel_price, avg_bakim_cost vb.


async def project_cashflow(
    uow, *, horizon_days: int = 90, diesel_price_tl: float = 50.0,
) -> CashflowProjection:
    """3 ana kalem aggregat — mevcut motorlardan + trailing avg."""
    from sqlalchemy import text
    from app.core.ml.maintenance_predictor import MaintenancePredictor

    # 1. Yakıt: aktif planlı seferlerin tahmini × litre fiyat
    fuel_rows = (await uow.session.execute(text("""
        SELECT tarih, COALESCE(SUM(tahmini_tuketim), 0) AS total_l
        FROM seferler
        WHERE is_deleted = FALSE AND durum = 'Planlandı'
          AND tarih BETWEEN CURRENT_DATE AND CURRENT_DATE + :h::INTEGER * INTERVAL '1 day'
        GROUP BY tarih ORDER BY tarih
    """), {"h": horizon_days})).mappings().all()

    # 2. Bakım: D.1 predictions (önümüzdeki N gün içine düşen)
    pred = MaintenancePredictor()
    preds = await pred.predict_all()
    upcoming_bakim = [
        p for p in preds
        if p.predictable and p.predicted_date
        and p.predicted_date <= date.today() + timedelta(days=horizon_days)
    ]

    # Avg bakım maliyeti (son 90g tamamlanmış bakım)
    avg_cost_row = (await uow.session.execute(text("""
        SELECT AVG(maliyet) AS avg_cost FROM arac_bakimlari
        WHERE tamamlandi = TRUE
          AND bakim_tarihi >= CURRENT_DATE - INTERVAL '90 days'
    """))).mappings().one()
    avg_bakim = float(avg_cost_row["avg_cost"] or 5000.0)

    # 3. Ceza: trailing 90g ortalama (basit; gelecek versiyonda gerçek ceza tablosu)
    # v1'de cezalar tablosu yoksa 0 döner; placeholder
    penalty_trailing = 0.0    # TODO: cezalar tablosu eklendiğinde doldur

    # Haftalık aggregate (12 hafta)
    weeks: List[CashflowWeek] = []
    for w in range(horizon_days // 7):
        week_start = date.today() + timedelta(days=w * 7)
        week_end = week_start + timedelta(days=7)
        week_fuel = sum(
            float(r["total_l"]) * diesel_price_tl
            for r in fuel_rows
            if week_start <= r["tarih"] < week_end
        )
        week_bakim = sum(
            avg_bakim for p in upcoming_bakim
            if p.predicted_date and week_start <= p.predicted_date < week_end
        )
        week_penalty = penalty_trailing / (horizon_days // 7)
        weeks.append(CashflowWeek(
            week_start=week_start,
            fuel_tl=round(week_fuel, 0),
            maintenance_tl=round(week_bakim, 0),
            penalty_tl=round(week_penalty, 0),
            total_tl=round(week_fuel + week_bakim + week_penalty, 0),
        ))

    total_fuel = sum(w.fuel_tl for w in weeks)
    total_bakim = sum(w.maintenance_tl for w in weeks)
    total_penalty = sum(w.penalty_tl for w in weeks)

    return CashflowProjection(
        horizon_days=horizon_days, weeks=weeks,
        total_fuel_tl=round(total_fuel, 0),
        total_maintenance_tl=round(total_bakim, 0),
        total_penalty_tl=round(total_penalty, 0),
        grand_total_tl=round(total_fuel + total_bakim + total_penalty, 0),
        confidence=0.65,
        assumptions={
            "diesel_price_tl": diesel_price_tl,
            "avg_bakim_cost_tl": round(avg_bakim, 0),
        },
    )
```

---

## 9. E.6 — Cross-Feature Aggregator

### 9.1 `app/core/services/cross_feature_aggregator.py`

```python
"""Feature E.6 — D.4 bakım gecikme + A.5 koçluk + B hırsızlık zarar toplam."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class CrossFeatureImpact:
    maintenance_delay_loss_tl: float       # D.4: factor > 1 araçlar × ekstra L × fiyat
    coaching_savings_tl: float             # A.5: score delta × yıllık km × birim
    theft_loss_tl: float                   # B: real_theft × ortalama L kayıp × fiyat
    period_days: int
    confidence: float


async def aggregate_cross_feature(
    uow, *, period_days: int = 90, diesel_price_tl: float = 50.0,
) -> CrossFeatureImpact:
    """3 motorun aggregat impact'i."""
    from sqlalchemy import text
    from app.core.ml.vehicle_health_factor import (
        compute_maintenance_factor, fetch_health_input,
    )

    # D.4 — Tüm aktif araçlar için factor hesapla, > 1 olanların ekstra L'ini topla
    arac_rows = (await uow.session.execute(text("""
        SELECT a.id,
            COALESCE(SUM(s.tuketim), 0) AS yearly_l
        FROM araclar a
        LEFT JOIN seferler s ON a.id = s.arac_id
            AND s.is_deleted = FALSE
            AND s.tarih >= CURRENT_DATE - INTERVAL :period_days::TEXT::INTERVAL
        WHERE a.aktif = TRUE AND a.is_deleted = FALSE
        GROUP BY a.id
    """), {"period_days": f"{period_days} days"})).mappings().all()

    maintenance_loss_l = 0.0
    for r in arac_rows:
        try:
            h_inp = await fetch_health_input(uow, int(r["id"]))
            h_res = compute_maintenance_factor(h_inp)
            if h_res.factor > 1.0:
                # Factor 1.07 → bu araç %7 fazla yakıyor; ekstra L
                extra_pct = h_res.factor - 1.0
                maintenance_loss_l += float(r["yearly_l"]) * extra_pct
        except Exception:
            continue

    # A.5 — Coaching deliveries with measured outcome
    a5_row = (await uow.session.execute(text("""
        SELECT
            COUNT(*) AS evaluated,
            COALESCE(AVG(score_after - score_before), 0) AS avg_delta
        FROM coaching_deliveries
        WHERE evaluated_at IS NOT NULL
          AND sent_at >= CURRENT_DATE - INTERVAL :period_days::TEXT::INTERVAL
    """), {"period_days": f"{period_days} days"})).mappings().one()
    a5_evaluated = int(a5_row["evaluated"] or 0)
    a5_delta = float(a5_row["avg_delta"] or 0)
    # Conservative: delta × ortalama yıllık km × birim L (placeholder)
    # Gerçek hesap için sefer-bazlı atfetme gerek; v1 lineer yaklaşıklık.
    coaching_savings = max(0, a5_delta * 50_000 * 0.3 * diesel_price_tl)

    # B — Resolved real_theft investigations
    b_row = (await uow.session.execute(text("""
        SELECT
            COUNT(*) AS real_thefts,
            COALESCE(AVG(a.sapma_yuzde), 0) AS avg_sapma
        FROM fuel_investigations i
        JOIN anomalies a ON i.anomaly_id = a.id
        WHERE i.resolution_type = 'real_theft'
          AND i.closed_at >= CURRENT_DATE - INTERVAL :period_days::TEXT::INTERVAL
    """), {"period_days": f"{period_days} days"})).mappings().one()
    b_count = int(b_row["real_thefts"] or 0)
    b_avg_sapma = float(b_row["avg_sapma"] or 0)
    # Sapma yüzdesinden kabaca L kayıp: ortalama sefer tüketimi × sapma%
    # v1: 200L ortalama sefer × sapma%
    theft_loss = b_count * 200 * (b_avg_sapma / 100) * diesel_price_tl

    return CrossFeatureImpact(
        maintenance_delay_loss_tl=round(maintenance_loss_l * diesel_price_tl, 0),
        coaching_savings_tl=round(coaching_savings, 0),
        theft_loss_tl=round(theft_loss, 0),
        period_days=period_days,
        confidence=0.55,   # düşük — heuristic hesaplar
    )
```

---

## 10. E.7 — Bus Factor / Risk Yoğunlaşması

### 10.1 `app/core/ml/bus_factor.py`

```python
"""Feature E.7 — En iyi N şoför/araç ayrılırsa filo verimi kaybı."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class BusFactorReport:
    top_n_drivers_loss_tl: float       # Top-N şoför ayrılırsa yıllık kayıp
    top_n_drivers: List[dict]          # Plaka/ad bilgisi yok PII koruma; sadece skor
    bottlenecked_routes: List[dict]    # Sadece N araç çalışan güzergahlar
    risk_level: str                    # "high"/"medium"/"low"


async def compute_bus_factor(
    uow, *, n: int = 3, diesel_price_tl: float = 50.0,
) -> BusFactorReport:
    from sqlalchemy import text
    # Top-N şoför vs medyanı
    rows = (await uow.session.execute(text("""
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
    """))).mappings().all()

    if not rows:
        return BusFactorReport(
            top_n_drivers_loss_tl=0, top_n_drivers=[],
            bottlenecked_routes=[], risk_level="low",
        )

    top_n = list(rows[:n])
    rest = list(rows[n:])
    median_score = sorted([r["score"] for r in rest])[len(rest) // 2] if rest else 1.0
    # Top-N ayrılırsa bunların seferleri medyan şoföre kayar → verim kaybı
    loss_l_per_km = 0.5  # her şoför 0.5 L/100km fark açabilir (heuristic)
    loss = 0.0
    for r in top_n:
        gap = max(0, r["score"] - median_score)
        loss += float(r["yearly_km"]) * gap * loss_l_per_km / 100
    loss_tl = loss * diesel_price_tl

    risk = "low"
    if loss_tl > 200_000:
        risk = "high"
    elif loss_tl > 50_000:
        risk = "medium"

    return BusFactorReport(
        top_n_drivers_loss_tl=round(loss_tl, 0),
        top_n_drivers=[
            {"score": round(r["score"], 2), "yearly_km": int(r["yearly_km"])}
            for r in top_n
        ],
        bottlenecked_routes=[],  # v2'de eklenir
        risk_level=risk,
    )
```

---

## 11. E.8 — Frontend Strategic Cockpit

### 11.1 `pages/ExecutivePage.tsx`

```tsx
export default function ExecutivePage() {
    return (
        <div className="space-y-6 p-6">
            <Header />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
                <FleetEfficiencyCard className="md:col-span-4" />
                <CashflowProjectionChart className="md:col-span-8" />
                <BusFactorWidget className="md:col-span-6" />
                <CrossFeatureSavings className="md:col-span-6" />
                <WhatIfPanel className="md:col-span-12" />
                <CarbonReportCard className="md:col-span-6" />
                <ComplianceHeatmap className="md:col-span-6" />
            </div>
            <DownloadPdfButton />
        </div>
    )
}
```

### 11.2 RBAC

`App.tsx`:
```tsx
<Route path="/executive" element={
    <RequirePermission perm={["super_admin", "fleet_manager", "yonetim_rapor"]}>
        <ExecutivePage />
    </RequirePermission>
} />
```

`EliteLayout.tsx` sidebar item — sadece yetkili görür.

### 11.3 Test

- Her bileşen için 1-2 vitest (loading, happy, error)
- ExecutivePage smoke test (RBAC + grid)

---

## 12. E.9 — CEO 1-pager PDF

### 12.1 `app/core/services/executive_pdf_generator.py`

```python
"""Feature E.9 — CEO 1-pager A4 dikey PDF."""
from __future__ import annotations
import io


def generate_executive_pdf(
    fvi: dict, cashflow: dict, cross_feature: dict, what_if_top: dict,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()

    flow = []
    flow.append(Paragraph("<b>LojiNext Strategic Cockpit</b>", styles["Title"]))
    # FVI kartı
    flow.append(Paragraph(
        f"<b>Filo Verimliliği Endeksi: {fvi['fvi']} / 100</b> "
        f"(trend: {fvi.get('trend_30d', '—')})",
        styles["Heading1"],
    ))
    flow.append(Paragraph(
        f"Yakıt: {fvi['fuel_score']} · Bakım: {fvi['maintenance_score']} · "
        f"Şoför: {fvi['driver_score']} · Anomali: {fvi['anomaly_quality_score']}",
        styles["Normal"],
    ))
    flow.append(Spacer(1, 12))

    # Cashflow
    flow.append(Paragraph("<b>90 Gün Projeksiyon</b>", styles["Heading1"]))
    flow.append(Paragraph(
        f"Yakıt: ₺{cashflow['total_fuel_tl']:,.0f} · "
        f"Bakım: ₺{cashflow['total_maintenance_tl']:,.0f}<br/>"
        f"Toplam: <b>₺{cashflow['grand_total_tl']:,.0f}</b>",
        styles["Normal"],
    ))
    flow.append(Spacer(1, 12))

    # Cross-feature
    flow.append(Paragraph("<b>Cross-Feature Etki (90g)</b>", styles["Heading1"]))
    flow.append(Paragraph(
        f"Bakım gecikme zararı: ₺{cross_feature['maintenance_delay_loss_tl']:,.0f}<br/>"
        f"Koçluk tasarrufu: ₺{cross_feature['coaching_savings_tl']:,.0f}<br/>"
        f"Hırsızlık zararı: ₺{cross_feature['theft_loss_tl']:,.0f}",
        styles["Normal"],
    ))
    flow.append(Spacer(1, 12))

    # Stratejik öneri (top what-if)
    if what_if_top:
        flow.append(Paragraph("<b>🎯 Top Öneri</b>", styles["Heading1"]))
        flow.append(Paragraph(
            f"{what_if_top['scenario_type']}: "
            f"Yıllık tasarruf ₺{what_if_top['yearly_savings_tl']:,.0f}, "
            f"payback {what_if_top.get('payback_years', '—')} yıl",
            styles["Normal"],
        ))

    doc.build(flow)
    return buf.getvalue()
```

Endpoint: `GET /reports/executive/pdf` → `application/pdf` döner.

---

## 13. Konfig + feature flag

```python
# app/config.py
# Feature E — Strategic Cockpit
EXECUTIVE_ENABLED: bool = True
EXECUTIVE_WHAT_IF_ENABLED: bool = True
EXECUTIVE_CACHE_TTL_S: int = 1800       # 30 dk
LITRE_DIESEL_TL: float = 50.0           # manuel güncellenir; what-if/cashflow
AVG_BAKIM_COST_TL: float = 5000.0       # fallback
```

---

## 14. Yol haritası

| Sıra | Alt görev | Çıktı | Test | Tahmini |
|---|---|---|---|---|
| E.1 | Filo Verimliliği Endeksi + endpoint | compute_fvi + gather_inputs SQL | 10+ unit + 2 integration | 2.5 sa |
| E.2 | What-if 3 senaryo + endpoint | 3 simulate fn + Pydantic schemas | 9 unit + 3 integration | 3.5 sa |
| E.3 | Per-vehicle karbon | euro_class_for_year + compute_fleet_carbon | 7 unit + 1 integration | 1.5 sa |
| E.4 | Compliance scanner | scan_compliance + risk_for_days | 4 unit + 1 integration | 1 sa |
| E.5 | Predictive cashflow | project_cashflow (D.1 aggregat'ı) | 5 unit + 1 integration | 2 sa |
| E.6 | Cross-feature aggregator | aggregate_cross_feature (D.4+A.5+B) | 4 unit + 1 integration | 2 sa |
| E.7 | Bus factor | compute_bus_factor | 4 unit + 1 integration | 1.5 sa |
| E.8 | Frontend cockpit | 7 widget + page + service + hooks | 8 vitest | 5 sa |
| E.9 | CEO 1-pager PDF | generate_executive_pdf + endpoint | 3 unit + 1 integration | 1.5 sa |

**Toplam tahmin:** ~21 saat.

### Gating

- E.1, E.3, E.4, E.7 bağımsız (paralel başlatılabilir)
- E.5 → E.1 + D.1'e bağlı
- E.6 → D.4 + A.5 + B'ye bağlı
- E.8 → tüm backend hazır olmalı
- E.9 → E.1 + E.5 + E.6 + E.2

---

## 15. Riskler ve azaltma

| Risk | Etki | Azaltma |
|---|---|---|
| Filo medyanı verisi az → FVI cold-start sürekli 75 | Yöneticiye yanıltıcı | `confidence` field UI'da rozet olarak gösterilir; <0.5 ise "düşük güven" uyarısı |
| What-if Monte Carlo random seed: aynı veri farklı sonuç | Karar tutarsızlığı | `random.seed(fixed)` test'te; üretimde her çağrı bağımsız sample |
| Cross-feature aggregat tek-tek araç sorgusu (E.6 N+1) | Yavaş | Bulk SQL ile fetch_health_input'u toplu çağrı yap (gelecek opt) |
| Karbon faktörleri eski (Defra 2024) | Doğruluk düşer | EURO_FACTORS config'e taşınabilir; yıllık update notu |
| Bus factor heuristic (0.5 L/100km gap) | Yanıltıcı | UI'da "heuristic" rozet + sayısal değer + sebep göster |
| PDF reportlab Türkçe font yok | ş/ğ render edilemez | DejaVu Sans font kaydı (mevcut PDFReportGenerator'da var, reuse) |
| Diesel fiyatı sabit (config) | Gerçek fiyat değişince stale | UI'da fiyatın gösterildiği "Varsayımlar" bölümü + manuel güncelleme linki |

---

## 16. PII ve güvenlik

- Tüm endpoint'ler `super_admin` veya `fleet_manager` gerektirir.
- LLM çağrısı **YOK** — tüm hesaplar deterministik / heuristic.
- Bus factor şoför adı **DÖNDÜRMEZ**, sadece skor + km (PII koruma).
- Compliance heatmap araç plakası içerir (admin görünür veri).
- Audit log: `executive_viewed`, `what_if_run` (PII'siz, scenario_type +
  inputs).
- CEO PDF: dosya yalnız authenticated user'a stream edilir; cache'lenmez.

---

## 17. Acceptance criteria

- [ ] `GET /reports/executive/kpi` → 200, FVI breakdown
- [ ] Cold-start senaryo (boş filo) → 75 + confidence düşük
- [ ] `POST /reports/what-if` 3 scenario_type için 200
- [ ] route_portfolio Monte Carlo response'da P10/P50/P90 dolu
- [ ] `GET /reports/executive/carbon` → Euro sınıfı breakdown
- [ ] `GET /reports/executive/compliance` → muayene yaklaşan/geçen
- [ ] `GET /reports/executive/cashflow?days=90` → 12 haftalık breakdown
- [ ] `GET /reports/executive/cross-feature` → 3 motor aggregat'ı
- [ ] `GET /reports/executive/bus-factor` → top-N skor (PII'siz)
- [ ] `GET /reports/executive/pdf` → application/pdf + 1-sayfa
- [ ] Feature flag `EXECUTIVE_ENABLED=False` → tüm endpoint 503
- [ ] RBAC: izleyici → 403; super_admin+fleet_manager → 200
- [ ] Frontend `/executive` route yalnız yetkili görür
- [ ] Tüm yeni unit/vitest yeşil
- [ ] `ruff check --ignore=E501`, `tsc --noEmit`, `vite build` clean
- [ ] Cross-feature aggregator D.4 factor>1 araçlar için doğru hesap

---

## 18. Açık notlar (uygulama sırasında karara bağlanacak)

1. **Compliance v2 alanları.** SRC belgesi, K1/K2/K3 belge, tachograph
   compliance — bunlar mevcut DB'de yok. Yeni migration gerekir:
   ```sql
   ALTER TABLE soforler ADD COLUMN src_belge_bitis DATE;
   ALTER TABLE soforler ADD COLUMN psikoteknik_bitis DATE;
   ALTER TABLE araclar ADD COLUMN k_belge_tipi VARCHAR(10);
   ALTER TABLE araclar ADD COLUMN k_belge_bitis DATE;
   ```
   E.4 v1 yalnız muayene'yi kapsar; v2'de yukarıdaki alanlar eklenip
   heatmap genişletilir.

2. **Ceza tablosu.** Cashflow projection E.5'te ceza kalemini placeholder=0
   tutuyor. Eğer ceza tablosu yoksa migration gerekir (`cezalar` tablosu:
   id, arac_id/sofor_id, tarih, miktar, sebep).

3. **Diesel fiyatı dinamik güncelleme.** v1'de `LITRE_DIESEL_TL` config
   manuel; v2'de petrol istasyonu API'sinden günlük çekilebilir.

4. **Trend hesabı (FVI delta_30d).** v1'de history tablosu yok → trend=None.
   v2'de `fleet_efficiency_history` tablosu eklenip her gün cron task
   ile snapshot alınabilir.

5. **Frontend chart library.** Mevcut projede Recharts var. ExecutivePage
   stack-bar + heatmap için yeterli; FullCalendar (D.3'te eklenmiş) burada
   kullanılmaz.

6. **PDF dil/font.** Türkçe karakter için DejaVu Sans (mevcut). Future:
   logo embed + multi-language.

7. **Bus factor — şoför mahremiyeti.** Top-N şoför adı **dahil edilmez**;
   sadece skor + km. Kullanıcı isterse "detayı göster" butonu ile
   yetkili kullanıcıya açılabilir (v2).

Bu 7 nokta E.1 başlangıcında doğrulanır, ardından plan kilitlenir.
