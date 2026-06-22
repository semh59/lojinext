# Feature D — Tahmine Dayalı Bakım Takvimi (Mini-Plan v3)

**Tarih:** 2026-05-26
**Status:** PLAN — uygulamaya hazır
**Önceki sürümler:** yok (Feature A/B/C v3 deneyiminden çıkarılan operasyonel
şablonla doğrudan v3 yazılmıştır)

---

## 0. Özet (TL;DR)

`/admin/maintenance` bugün statik liste + kural-tabanlı `get_maintenance_candidates()`
döndürüyor. Bu plan üç şey ekler:

1. **`MaintenancePredictor`** — her aktif araç için
   bakım_tipi başına bir *tahmini sonraki tarih* + güven skoru üretir.
   Hibrit: her bakım tipi için sabit interval (km veya ay) + aracın gerçek
   kullanım hızı + tüketim trendi düzeltmesi.
2. **Takvim UI** — FullCalendar ile aylık görünüm; tıklanan bakım kartı
   detay + "bu bakım yapılırsa %X yakıt tasarrufu" projeksiyonu.
3. **Bakım → yakıt tahmin geri besleme** (D.4) — `PredictionService.predict_consumption`
   yeni bir `maintenance_factor` çoğaltıcısı uygular; bakımı geciken
   araçlar daha yüksek L tahmin, taze bakım yapılmışsa daha düşük L tahmin
   üretir. Bu **kapalı döngü**: D.1'in tüketim trendine baktığı verinin
   doğruluğu yükselir, böylece bakım önerisi gerçek nedeni yansıtır.

Yeni ML modeli yok — mevcut `Sefer.tuketim` + `Arac.yil` + `AracBakim` verisi
üzerinde *tahmin formülü*. Eğitim/persistence gerekmez; her istekte hesaplanır
ve Redis'te 1 saat cache'lenir.

---

## 1. İş ihtiyacı (sorun → değer)

| Bugün | D ile |
|---|---|
| Bakım sadece tamamlandı/yaklaşıyor durumu gösteriyor; *ne zaman yapılmalı?* sorusu cevapsız | Her araç için bakım tipi başına tahmini tarih + güven |
| Takvim yok — sadece liste; planlama için "gelecek 30 günde hangi araçlar?" bilinmiyor | Aylık takvim görünümü, gün başına bakım kartı |
| "Bu bakım yapılırsa ne kazanırım?" sorusu cevapsız | Tasarruf projeksiyonu (aracın tüketim vs filo benchmark karşılaştırması) |
| Bakımı Outlook/Google Calendar'a aktaramıyor | `.ics` indirilir → tek tık takvim entegrasyonu |
| Az kullanılan araçlar ile yoğun kullanılan araçlar aynı interval'da uyarılıyor | Gerçek kullanım hızı (km/ay) ile düzeltme |

**Hedef KPI:** Önerilen tarihten ±5 gün sapma içinde tutturulan bakımların
oranı ≥ %60 (3 ay sonraki incelemeyle ölçülür).

---

## 2. Karar matrisi (4 kritik soru ve cevapları)

### Q1 — Tahmin formülü?

**Cevap:** Hibrit. Her bakım tipi için sabit interval + aracın gerçek
kullanım hızı + tüketim trend düzeltmesi.

#### Sabit intervaller (her bakım tipi için)

| Bakım tipi | Süre intervali | Mesafe intervali |
|---|---|---|
| PERIYODIK | 12 ay | 25.000 km |
| ARIZA | tahmin yok (reaktif) | — |
| ACIL | tahmin yok | — |

`ARIZA` ve `ACIL` için tahmin **döndürülmez** (`predictable=False`).

#### Aracın gerçek kullanım hızı
```
km_per_month = SUM(seferler.mesafe_km son 180 gün) / 6
```
- Son 180 gün ≥ 5 sefer yoksa: filo medyanı kullan (cold-start fallback).
- 0 km/ay ise araç fiilen kullanılmıyor → predictable=False.

#### Mesafeye-göre tahmini günler

```
ref_km = AracBakim.km_bilgisi (son tamamlanmış PERIYODIK)
current_km = ref_km + Σ(seferler.mesafe_km bakım sonrası)
remaining_km = 25000 - (current_km - ref_km)
days_by_km = remaining_km / km_per_day      # km_per_day = km_per_month / 30
```

`AracBakim` kaydı yok ise `ref_km=0` + `son_bakim_tarihi=None` →
fallback'a düşer.

#### Süreye-göre tahmini günler

```
days_by_time = max(0, 365 - days_since_last_periyodik)
```

`son_bakim_tarihi` yok ise araç yaşına göre (`365 * yas` gün) hesap. Eğer
365'ten büyükse "GECİKMİŞ" işaretle.

#### Final tahmin (hangisi daha erken)
```
days_remaining = min(days_by_km, days_by_time)
predicted_date = today + days_remaining
```

#### Tüketim trendi düzeltmesi

Son 90 gün vs önceki 90 gün tüketim karşılaştırması (`Sefer.tuketim`):
- `+10%` → düzeltme = -7 gün (daha erken bakım önerilir)
- `+20%` → düzeltme = -14 gün
- `< +5%` → düzeltme yok

Max düzeltme = -30 gün. Tahmini tarih bugünden önce çıkarsa "GECİKMİŞ".

#### Güven skoru (0..1)

```
confidence = clamp(
    0.5
    + 0.2 * (1 if has_periyodik_history else 0)
    + 0.2 * (1 if km_per_month >= 100 else 0)   # yeterli sefer var
    + 0.1 * (1 if has_consumption_trend else 0)
    , 0, 1
)
```

UI gösterimi: `>=0.8` yüksek (yeşil), `>=0.5` orta (sarı), `<0.5` düşük (gri).

### Q2 — Yakıt tasarrufu projeksiyonu?

**Cevap:** Filo benchmark karşılaştırması.

```
arac_avg = avg(seferler.tuketim son 90 gün)
filo_benchmark = median(seferler.tuketim son 90 gün, tüm araçlar)
if arac_avg <= filo_benchmark:
    savings_pct = 0     # zaten verimli
else:
    savings_pct = round(
        (arac_avg - filo_benchmark) / arac_avg * 100, 1
    )
```

Cap %20: gerçekçi üst sınır (tek bir bakım daha fazlasını sağlamaz).

UI: "Bu bakım sonrası tahmini tasarruf: **%X**"

### Q3 — Endpoint'ler nasıl şekillendirilsin?

**Cevap:** 3 yeni endpoint:

| Method | Path | Amaç |
|---|---|---|
| GET | `/admin/maintenance/predictions` | Tüm aktif araçlar için tahmin listesi |
| GET | `/admin/maintenance/predictions/{arac_id}` | Tek araç için detay (rapor / sebep dump) |
| GET | `/admin/maintenance/{bakim_id}/ics` | Tek bakım için `.ics` indir |

Mevcut `POST /` (create) ve `PATCH /{id}/complete` korunur.

**Cache:** `/predictions` Redis'te `maintenance:predictions:all` anahtarıyla
1 saat tutulur. Yeni bakım create/complete olunca invalidate edilir.

**RBAC:** `require_yetki(["admin", "super_admin", "fleet_manager", "bakim_oku"])`.

### Q4 — Frontend takvim entegrasyonu?

**Cevap:** FullCalendar + daygrid plugin.

Paketler:
```
@fullcalendar/react@^6
@fullcalendar/daygrid@^6
@fullcalendar/core@^6
```

Event mapping:
```ts
{
  id: prediction.id,           // arac_id:bakim_tipi
  title: `${plaka} — ${bakim_tipi}`,
  start: prediction.predicted_date,
  classNames: [riskClass],      // risk-overdue / risk-soon / risk-normal
  extendedProps: prediction,
}
```

Event tıklama → sağdan slide-in detay panel (tasarruf projeksiyonu + .ics
indir butonu).

---

## 3. Mimari (yeni + değişen dosyalar)

### Backend

```
app/
├── core/
│   └── ml/
│       ├── maintenance_predictor.py            # NEW (D.1) — Hibrit tahmin motoru
│       └── vehicle_health_factor.py            # NEW (D.4) — Bakım→yakıt çarpanı
├── api/v1/endpoints/
│   └── admin_maintenance.py                    # MODIFY (D.2) — +3 endpoint
├── schemas/
│   └── maintenance_prediction.py               # NEW (D.1/D.2) — Pydantic şemaları
├── core/services/
│   └── ics_generator.py                        # NEW (D.2) — RFC 5545 .ics üretici
├── services/
│   └── prediction_service.py                   # MODIFY (D.4) — maintenance_factor entegre
├── config.py                                   # MODIFY — MAINTENANCE_PREDICTOR_ENABLED
└── tests/
    ├── unit/
    │   ├── test_maintenance_predictor.py       # NEW (D.1) — saf formül testleri
    │   ├── test_vehicle_health_factor.py       # NEW (D.4) — saf çarpan testleri
    │   └── test_ics_generator.py               # NEW (D.2) — .ics format testleri
    └── integration/
        ├── test_maintenance_predictions.py     # NEW (D.2) — endpoint kontratı
        └── test_prediction_with_health.py      # NEW (D.4) — entegrasyon
```

### Frontend

```
frontend/
├── package.json                                # MODIFY — FullCalendar deps
├── src/
│   ├── pages/admin/
│   │   └── BakimPage.tsx                       # MODIFY (D.3) — yeni takvim sekmesi
│   ├── components/admin/maintenance/
│   │   ├── MaintenanceCalendar.tsx             # NEW (D.3) — FullCalendar wrapper
│   │   ├── MaintenanceDetailDrawer.tsx         # NEW (D.3) — sağdan açılan panel
│   │   ├── PredictionsTable.tsx                # NEW (D.3) — liste görünümü
│   │   └── __tests__/
│   │       ├── MaintenanceCalendar.test.tsx    # NEW
│   │       ├── MaintenanceDetailDrawer.test.tsx# NEW
│   │       └── PredictionsTable.test.tsx       # NEW
│   ├── services/api/
│   │   └── maintenance-predictions-service.ts  # NEW — API wrapper
│   ├── resources/tr/
│   │   └── maintenancePredictions.ts           # NEW — Türkçe metinler
│   └── hooks/
│       └── useMaintenancePredictions.ts        # NEW — React Query hook
```

**Dokunulmayan dosyalar (önemli):**
- `app/database/models.py` (AracBakim modeli — yeterli alan zaten var)
- `app/database/repositories/maintenance_repository.py` (mevcut metodlar yeterli)
- `app/database/repositories/arac_repo.py` `get_maintenance_candidates` —
  ayrı; D.1'in bunu çağırması gerekmez

**Migration gerekmez** — yeni tablo yok, sadece okunan veri üzerine türev hesap.

---

## 4. D.1 — Maintenance Predictor backend

### 4.1 Dosya: `app/core/ml/maintenance_predictor.py`

```python
"""Feature D — Tahmine Dayalı Bakım motoru.

Hibrit: kural-tabanlı interval + aracın gerçek kullanım hızı + tüketim
trendi düzeltmesi. ML modeli eğitilmez; her istekte hesaplanır.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Sabitler ────────────────────────────────────────────────────────────
INTERVAL_MONTHS = {"PERIYODIK": 12}     # ARIZA/ACIL tahmin edilmez
INTERVAL_KM = {"PERIYODIK": 25_000}
CONSUMPTION_LOOKBACK_DAYS = 90
USAGE_LOOKBACK_DAYS = 180
MIN_TRIPS_FOR_USAGE = 5
MAX_TREND_CORRECTION_DAYS = 30
FILO_MIN_TRIPS_FOR_BENCHMARK = 20
SAVINGS_CAP_PCT = 20.0


@dataclass
class PredictionInput:
    arac_id: int
    plaka: str
    yil: Optional[int]
    last_periyodik_date: Optional[datetime]
    last_periyodik_km: Optional[int]
    km_per_month: float
    consumption_recent: Optional[float]    # son 90 gün avg
    consumption_previous: Optional[float]  # önceki 90 gün avg
    filo_consumption_median: Optional[float]


@dataclass
class Prediction:
    arac_id: int
    plaka: str
    bakim_tipi: str
    predictable: bool
    predicted_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    confidence: float = 0.0
    risk_level: str = "low"             # overdue|soon|normal|low
    savings_pct: float = 0.0
    reasons: List[str] = field(default_factory=list)


# ── Saf yardımcılar (test edilebilir) ───────────────────────────────────
def _days_by_km(inp: PredictionInput) -> Optional[int]:
    if inp.km_per_month <= 0:
        return None
    if inp.last_periyodik_km is None:
        # Bakım kaydı yok → son seferlerden tahmini current_km hesaplanamaz
        return None
    # Burada caller current_km bilgisini sağlamalı (data layer'dan)
    return None  # placeholder; gerçek hesap _predict_for_vehicle içinde


def _consumption_trend_pct(recent: Optional[float], previous: Optional[float]) -> Optional[float]:
    if recent is None or previous is None or previous == 0:
        return None
    return round((recent - previous) / previous * 100.0, 1)


def _trend_correction_days(trend_pct: Optional[float]) -> int:
    if trend_pct is None or trend_pct < 5.0:
        return 0
    # Doğrusal yaklaşım: %10 → -7 gün, %20 → -14 gün, %30+ → cap 30
    correction = -int(round(trend_pct * 0.7))
    return max(correction, -MAX_TREND_CORRECTION_DAYS)


def _risk_level(days_remaining: int) -> str:
    if days_remaining < 0:
        return "overdue"
    if days_remaining <= 14:
        return "soon"
    if days_remaining <= 60:
        return "normal"
    return "low"


def _confidence(
    *,
    has_periyodik_history: bool,
    enough_usage: bool,
    has_consumption_trend: bool,
) -> float:
    score = 0.5
    if has_periyodik_history:
        score += 0.2
    if enough_usage:
        score += 0.2
    if has_consumption_trend:
        score += 0.1
    return round(min(1.0, max(0.0, score)), 2)


def _savings_pct(arac_avg: Optional[float], filo_median: Optional[float]) -> float:
    if not arac_avg or not filo_median or arac_avg <= filo_median:
        return 0.0
    pct = (arac_avg - filo_median) / arac_avg * 100.0
    return round(min(pct, SAVINGS_CAP_PCT), 1)


# ── Engine ──────────────────────────────────────────────────────────────
class MaintenancePredictor:
    """Stateless; HTTP layer her istekte oluşturur."""

    async def predict_all(self) -> List[Prediction]:
        """Tüm aktif araçlar için PERIYODIK bakım tahmini döndürür."""
        # Implementation:
        # 1. UnitOfWork ile aktif araçları + son PERIYODIK bakımı çek (LEFT JOIN)
        # 2. Her araç için son 180 gün km toplamı, son 90+90 gün tüketim ortalamaları çek
        # 3. Filo medyanı (tüm araçlar son 90 gün)
        # 4. Her araç için _predict_for_vehicle çağır
        from app.database.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            inputs = await self._gather_inputs(uow)
        return [self._predict_for_vehicle(inp) for inp in inputs]

    async def predict_for_arac(self, arac_id: int) -> Optional[Prediction]:
        from app.database.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            inputs = await self._gather_inputs(uow, arac_id=arac_id)
        if not inputs:
            return None
        return self._predict_for_vehicle(inputs[0])

    async def _gather_inputs(self, uow, arac_id: Optional[int] = None) -> List[PredictionInput]:
        """Tek bir SQL ile tüm gerekli veriyi çek."""
        from sqlalchemy import text

        sql = """
            WITH last_bak AS (
                SELECT DISTINCT ON (b.arac_id)
                    b.arac_id, b.bakim_tarihi, b.km_bilgisi
                FROM arac_bakimlari b
                WHERE b.bakim_tipi = 'PERIYODIK' AND b.tamamlandi = TRUE
                ORDER BY b.arac_id, b.bakim_tarihi DESC
            ),
            usage_recent AS (
                SELECT s.arac_id, COALESCE(SUM(s.mesafe_km), 0) AS km_180d
                FROM seferler s
                WHERE s.is_deleted = FALSE
                  AND s.tarih >= CURRENT_DATE - INTERVAL '180 days'
                GROUP BY s.arac_id
            ),
            consum_recent AS (
                SELECT s.arac_id, AVG(s.tuketim) AS avg_t
                FROM seferler s
                WHERE s.is_deleted = FALSE AND s.tuketim IS NOT NULL
                  AND s.tarih >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY s.arac_id
            ),
            consum_previous AS (
                SELECT s.arac_id, AVG(s.tuketim) AS avg_t
                FROM seferler s
                WHERE s.is_deleted = FALSE AND s.tuketim IS NOT NULL
                  AND s.tarih BETWEEN
                        CURRENT_DATE - INTERVAL '180 days'
                    AND CURRENT_DATE - INTERVAL '90 days'
                GROUP BY s.arac_id
            )
            SELECT
                a.id, a.plaka, a.yil,
                lb.bakim_tarihi   AS last_periyodik_date,
                lb.km_bilgisi     AS last_periyodik_km,
                COALESCE(ur.km_180d, 0) AS km_180d,
                cr.avg_t          AS consum_recent,
                cp.avg_t          AS consum_previous
            FROM araclar a
            LEFT JOIN last_bak       lb ON lb.arac_id = a.id
            LEFT JOIN usage_recent   ur ON ur.arac_id = a.id
            LEFT JOIN consum_recent  cr ON cr.arac_id = a.id
            LEFT JOIN consum_previous cp ON cp.arac_id = a.id
            WHERE a.aktif = TRUE AND a.is_deleted = FALSE
                  {arac_filter}
            ORDER BY a.id
        """
        params: Dict[str, Any] = {}
        if arac_id is not None:
            sql = sql.format(arac_filter="AND a.id = :arac_id")
            params["arac_id"] = arac_id
        else:
            sql = sql.format(arac_filter="")
        rows = (await uow.session.execute(text(sql), params)).mappings().all()

        # Filo medyanı (ayrı sorgu) — yeterli sefer varsa
        filo_median: Optional[float] = None
        filo_rows = (
            await uow.session.execute(
                text(
                    "SELECT tuketim FROM seferler WHERE is_deleted = FALSE "
                    "AND tuketim IS NOT NULL "
                    "AND tarih >= CURRENT_DATE - INTERVAL '90 days'"
                )
            )
        ).all()
        if len(filo_rows) >= FILO_MIN_TRIPS_FOR_BENCHMARK:
            filo_median = statistics.median(r[0] for r in filo_rows)

        out: List[PredictionInput] = []
        for r in rows:
            km_per_month = float(r["km_180d"]) / 6.0
            out.append(PredictionInput(
                arac_id=int(r["id"]),
                plaka=str(r["plaka"]),
                yil=int(r["yil"]) if r["yil"] else None,
                last_periyodik_date=r["last_periyodik_date"],
                last_periyodik_km=(
                    int(r["last_periyodik_km"]) if r["last_periyodik_km"] is not None else None
                ),
                km_per_month=km_per_month,
                consumption_recent=(
                    float(r["consum_recent"]) if r["consum_recent"] is not None else None
                ),
                consumption_previous=(
                    float(r["consum_previous"]) if r["consum_previous"] is not None else None
                ),
                filo_consumption_median=filo_median,
            ))
        return out

    def _predict_for_vehicle(self, inp: PredictionInput) -> Prediction:
        """Saf hesaplama — inputs verili, DB'ye dokunmaz."""
        pred = Prediction(
            arac_id=inp.arac_id, plaka=inp.plaka, bakim_tipi="PERIYODIK",
            predictable=False,
        )

        # Önce ortak bir referans noktası — gerçek son PERIYODIK var mı?
        days_since: Optional[int] = None
        if inp.last_periyodik_date is not None:
            last_dt = inp.last_periyodik_date
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - last_dt).days

        # Süreye göre kalan gün
        days_by_time: Optional[int] = (
            365 - days_since if days_since is not None else None
        )

        # Mesafeye göre kalan gün — hem last_periyodik_km hem days_since gerekir;
        # ikisi de yoksa bu yol hesaplanamaz.
        days_by_km: Optional[int] = None
        if (
            inp.last_periyodik_km is not None
            and inp.km_per_month > 0
            and days_since is not None
        ):
            km_per_day = inp.km_per_month / 30.0
            elapsed_km = km_per_day * days_since
            remaining_km = INTERVAL_KM["PERIYODIK"] - elapsed_km
            days_by_km = int(remaining_km / km_per_day)

        # Hangisi daha erken? (her ikisi de None değilse)
        candidates = [d for d in (days_by_time, days_by_km) if d is not None]
        if not candidates:
            pred.reasons.append("Yeterli veri yok (bakım geçmişi veya kullanım eksik)")
            return pred  # predictable=False

        days_remaining = min(candidates)

        # Tüketim trendi düzeltmesi
        trend_pct = _consumption_trend_pct(
            inp.consumption_recent, inp.consumption_previous
        )
        correction = _trend_correction_days(trend_pct)
        days_remaining += correction

        pred.predictable = True
        pred.days_remaining = days_remaining
        pred.predicted_date = (datetime.now(timezone.utc) + timedelta(days=days_remaining)).date()
        pred.is_overdue = days_remaining < 0
        pred.risk_level = _risk_level(days_remaining)
        pred.confidence = _confidence(
            has_periyodik_history=inp.last_periyodik_date is not None,
            enough_usage=inp.km_per_month >= 100.0,
            has_consumption_trend=trend_pct is not None,
        )
        pred.savings_pct = _savings_pct(
            inp.consumption_recent, inp.filo_consumption_median
        )

        # Reasons
        if days_by_time is not None and days_by_time == min(candidates):
            pred.reasons.append(
                f"Son PERIYODIK bakımdan {365 - days_by_time} gün geçti"
            )
        if days_by_km is not None and days_by_km == min(candidates):
            pred.reasons.append(
                f"Tahmini {INTERVAL_KM['PERIYODIK'] - int(km_per_day * days_since_for_km):,} km kaldı"
            )
        if correction < 0:
            pred.reasons.append(
                f"Tüketim trendi %{trend_pct:+.1f} → {abs(correction)} gün erkene alındı"
            )
        if pred.is_overdue:
            pred.reasons.append("⚠ GECİKMİŞ — derhal planlanmalı")
        if pred.savings_pct > 0:
            pred.reasons.append(
                f"Bakım sonrası tahmini tasarruf: %{pred.savings_pct}"
            )

        return pred
```

### 4.2 Test stratejisi

**Pure-unit (DB yok):**
- `_consumption_trend_pct` (None / 0 / pozitif / negatif sapma)
- `_trend_correction_days` (eşik altı / lineer / cap)
- `_risk_level` (4 bölge sınır testi)
- `_confidence` (kombinasyon matrisi)
- `_savings_pct` (None / equal / above / cap)
- `_predict_for_vehicle` — sentetik input → beklenen Prediction (8+ senaryo)

**Integration (DB var, sonraki adım):**
- D.2'de endpoint testleri DB seed + gerçek SQL çalışacak.

---

## 5. D.2 — Endpoints + .ics generator

### 5.1 Yeni endpoint'ler (`app/api/v1/endpoints/admin_maintenance.py`)

```python
# Tüm araçlar — Predictions listesi
@router.get("/predictions", response_model=List[MaintenancePrediction])
async def get_all_predictions(
    current_admin: Annotated[Kullanici, Depends(require_yetki(["bakim_oku", "admin", "super_admin"]))],
) -> List[MaintenancePrediction]:
    if not settings.MAINTENANCE_PREDICTOR_ENABLED:
        raise HTTPException(503, "Bakım tahmin modülü kapalı")
    # Redis cache (1 saat)
    redis = get_redis_client()
    cache_key = "maintenance:predictions:all"
    cached = await redis.get(cache_key)
    if cached:
        return [MaintenancePrediction.model_validate_json(j) for j in json.loads(cached)]

    predictor = MaintenancePredictor()
    preds = await predictor.predict_all()
    result = [MaintenancePrediction.model_validate(p) for p in preds]

    # Cache + audit
    try:
        await redis.setex(
            cache_key, settings.MAINTENANCE_PREDICTOR_CACHE_TTL_S,
            json.dumps([p.model_dump_json() for p in result]),
        )
    except Exception as exc:
        logger.warning("predictions cache write failed: %s", exc)
    creator_id = (
        current_admin.id if current_admin.id and current_admin.id > 0 else None
    )
    await log_audit_event(
        action="predictions_viewed", module="maintenance",
        entity_id=None, user_id=creator_id,
        new_value={"count": len(result), "scope": "all"},
    )
    return result


# Tek araç — detay
@router.get("/predictions/{arac_id}", response_model=MaintenancePrediction)
async def get_prediction_for_arac(arac_id: int, ...):
    if not settings.MAINTENANCE_PREDICTOR_ENABLED:
        raise HTTPException(503, "Bakım tahmin modülü kapalı")
    pred = await MaintenancePredictor().predict_for_arac(arac_id)
    if not pred:
        raise HTTPException(404, "Araç bulunamadı")
    await log_audit_event(
        action="predictions_viewed", module="maintenance",
        entity_id=str(arac_id), user_id=current_admin.id,
        new_value={"scope": "single"},
    )
    return MaintenancePrediction.model_validate(pred)


# Tek bakım için .ics indir
@router.get(
    "/{bakim_id}/ics",
    dependencies=[Depends(RateLimiterDependency("ics_download", rate=10, period=60))],
)
async def download_ics(bakim_id: int, ...) -> Response:
    from app.core.services.ics_generator import generate_ics_for_maintenance
    async with UnitOfWork() as uow:
        bakim = await uow.maintenance_repo.get_by_id(bakim_id)
        if not bakim:
            raise HTTPException(404, "Bakım bulunamadı")
        arac = await uow.arac_repo.get_by_id(bakim.arac_id)
    ics_body = generate_ics_for_maintenance(bakim, arac)
    # UTF-8 charset zorunlu — Türkçe ş/ğ/ı render edilebilsin
    return Response(
        content=ics_body.encode("utf-8"),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="bakim-{bakim_id}.ics"'
            ),
        },
    )
```

### 5.2 `app/core/services/ics_generator.py` — **DÜZELTME**

RFC 5545 iki sert kural:

1. Her satır CRLF (`\r\n`) ile biter; metin içinde `\n`/`,`/`;`/`\\` escape
   edilir (`\\n`, `\,`, `\;`, `\\\\`).
2. Satırlar 75 oktet'i geçemez — uzun değerler **CRLF + tek boşluk** ile
   katlanır ("line folding").

Uygulamada bu iki kuralı **helper fonksiyonlarla** kapsıyoruz:

```python
"""RFC 5545 .ics üretici (UTF-8, line folding dahil)."""
from datetime import datetime, timezone
from uuid import uuid4


def _escape_text(s: str) -> str:
    """RFC 5545 §3.3.11 — TEXT value escape sırası kritik:
    önce backslash, sonra special char'lar.
    """
    return (
        s.replace("\\", "\\\\")
         .replace("\n", "\\n")
         .replace("\r", "")
         .replace(",", "\\,")
         .replace(";", "\\;")
    )


def _fold_line(line: str, max_bytes: int = 75) -> str:
    """RFC 5545 §3.1 — satırı 75 oktet'i geçmeyecek şekilde katla.
    UTF-8 multi-byte karakteri ortadan ayırma; en yakın güvenli bayttan
    böl ve devam satırına TEK boşluk koy.
    """
    raw = line.encode("utf-8")
    if len(raw) <= max_bytes:
        return line
    parts: list[str] = []
    buf = b""
    for ch in line:
        ch_bytes = ch.encode("utf-8")
        # +1 = devam satırına eklenen leading SPACE; ilk satır için 0
        budget = max_bytes if not parts else max_bytes - 1
        if len(buf) + len(ch_bytes) > budget:
            parts.append(buf.decode("utf-8"))
            buf = ch_bytes
        else:
            buf += ch_bytes
    if buf:
        parts.append(buf.decode("utf-8"))
    return "\r\n ".join(parts)


def _line(name: str, value: str) -> str:
    return _fold_line(f"{name}:{value}") + "\r\n"


def generate_ics_for_maintenance(bakim, arac) -> str:
    dt = bakim.bakim_tarihi.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plaka = arac.plaka if arac else "?"
    description_raw = (
        f"Plaka: {plaka}\n"
        f"Bakım tipi: {bakim.bakim_tipi}\n"
        f"Km: {bakim.km_bilgisi}\n"
        f"Detaylar: {(bakim.detaylar or '').strip()}"
    )
    summary = f"Bakım — {plaka} ({bakim.bakim_tipi})"

    parts = [
        "BEGIN:VCALENDAR\r\n",
        "VERSION:2.0\r\n",
        "PRODID:-//LojiNext//Maintenance//TR\r\n",
        "CALSCALE:GREGORIAN\r\n",
        "BEGIN:VEVENT\r\n",
        _line("UID", f"bakim-{bakim.id}-{uuid4().hex[:8]}@lojinext"),
        _line(
            "DTSTAMP",
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        ),
        _line("DTSTART", dt),
        _line("DTEND", dt),
        _line("SUMMARY", _escape_text(summary)),
        _line("DESCRIPTION", _escape_text(description_raw)),
        "END:VEVENT\r\n",
        "END:VCALENDAR\r\n",
    ]
    return "".join(parts)
```

#### .ics test stratejisi (genişletildi)

`test_ics_generator.py` (6 unit):
1. `_escape_text` sırası: backslash önce, sonra special char (`a\nb,c` → `a\\nb\\,c`)
2. `_fold_line` 75 bayt altında değişmez
3. `_fold_line` UTF-8 multi-byte (Türkçe ş/ğ) ortadan kırılmaz
4. `_fold_line` çıktıda CRLF+space delimiter
5. `generate_ics_for_maintenance` — BEGIN/END:VCALENDAR + 1 VEVENT
6. `generate_ics_for_maintenance` — multiline detaylar tek `DESCRIPTION` satırında, `\n` escape edilmiş

### 5.3 Schemas (`app/schemas/maintenance_prediction.py`)

```python
from datetime import date
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["overdue", "soon", "normal", "low"]

class MaintenancePrediction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    arac_id: int
    plaka: str
    bakim_tipi: str
    predictable: bool
    predicted_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_overdue: bool = False
    confidence: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    savings_pct: float = Field(0.0, ge=0, le=100)
    reasons: List[str] = Field(default_factory=list, max_length=10)
```

### 5.4 Cache invalidation tetikleyicileri

`/predictions` Redis key'i (`maintenance:predictions:all`) **şu olaylarda
invalidate edilir:**

```python
async def _invalidate_predictions_cache():
    redis = get_redis_client()
    await redis.delete("maintenance:predictions:all")
    # Tek araç cache'leri:
    cursor = 0
    while True:
        cursor, keys = await redis.scan(
            cursor, match="maintenance:predictions:arac:*", count=100
        )
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break
```

Çağrılacağı yerler:
- `MaintenanceService.create_maintenance_record` — yeni bakım eklendiğinde
- `MaintenanceService.mark_as_completed` — bakım tamamlandığında
- `POST /api/v1/admin/maintenance` (oluştur)
- `PATCH /api/v1/admin/maintenance/{id}/complete`

`MAINTENANCE_PREDICTOR_CACHE_TTL_S` yine 1 saat, ama bu hook'lar olduğunda
TTL beklenmez.

### 5.5 Endpoint integration test stratejisi (genişletildi)

- `GET /predictions` → 200 + liste döner (DB seed: 3 araç + 2 bakım)
- `GET /predictions/{id}` → 200 / 404 / 503
- `GET /{bakim_id}/ics` → 200 + `Content-Type: text/calendar; charset=utf-8` + Content-Disposition
- `.ics` gövdesi UTF-8 decode edilebilir + Türkçe karakter korunmuş
- Feature flag kapalı → 503
- RBAC: yetkisiz → 403
- Audit log: `predictions_viewed` (entity_id=None, count=N) yazılmış
- Cache invalidation: bakım create → ardından `/predictions` cache miss

---

## 6. D.3 — Frontend Calendar UI

### 6.1 package.json değişikliği

```json
{
  "dependencies": {
    "@fullcalendar/react": "^6.1.11",
    "@fullcalendar/daygrid": "^6.1.11",
    "@fullcalendar/core": "^6.1.11"
  }
}
```

`npm install @fullcalendar/react @fullcalendar/daygrid @fullcalendar/core`

**Bundle ölçüm planı** — kurulum sonrası `npx vite build`'ten önce/sonra
`dist/assets/*.js.gz` toplamlarını karşılaştır. Tahmin ~150 KB gzip;
gerçek ölçümü D.3 commit mesajına ekle.

**CSS import zorunluluğu** — FullCalendar v6 stil dosyaları otomatik
inject olmaz; bileşenin yüklendiği ilk yer için (BakimPage veya
MaintenanceCalendar) açıkça import edilmeli:

```ts
import '@fullcalendar/core/main.css'
import '@fullcalendar/daygrid/main.css'
```

Veya tek seferlik `frontend/src/main.tsx`'e ekle. Eğer atlanırsa kalender
stilsiz görünür (test'te yakalanmaz çünkü vitest CSS'i mock'lar).

### 6.2 Bileşen ağacı

```
BakimPage.tsx (MODIFY)
├─ TabBar: [Tahminler] [Liste] [Geçmiş]  (3 sekme)
├─ {activeTab === 'predictions' && <MaintenanceCalendar />}
└─ {activeTab === 'list' && <PredictionsTable />}

MaintenanceCalendar.tsx (NEW)
├─ FullCalendar dayGridPlugin
├─ events: useMaintenancePredictions().data → mapPredictionToEvent
├─ eventClick → setSelectedPrediction()
└─ <MaintenanceDetailDrawer prediction={selected} />

MaintenanceDetailDrawer.tsx (NEW)
├─ Header: plaka + bakım tipi + risk badge
├─ Predicted date + days_remaining + confidence
├─ Reasons listesi (PII'siz)
├─ Tasarruf projeksiyonu (savings_pct varsa)
├─ ".ics indir" butonu → window.location = `/admin/maintenance/{id}/ics`
└─ "Tamamlandı olarak işaretle" butonu (RBAC ile)

PredictionsTable.tsx (NEW)
├─ Sortable kolon: plaka | tip | predicted_date | risk | confidence
├─ Risk badge renkli
└─ Click row → MaintenanceDetailDrawer
```

### 6.3 API hook

```typescript
// hooks/useMaintenancePredictions.ts
export function useMaintenancePredictions() {
    return useQuery({
        queryKey: ['maintenance', 'predictions'],
        queryFn: () => maintenancePredictionsService.getAll(),
        staleTime: 60 * 60 * 1000,  // backend zaten 1 saat cache
        refetchOnWindowFocus: false,
    })
}
```

### 6.4 Test

- `MaintenanceCalendar.test.tsx` — 3 prediction render edilir, eventClick handler çağrılır
- `MaintenanceDetailDrawer.test.tsx` — open/close, .ics buton link doğru
- `PredictionsTable.test.tsx` — sıralama + risk badge renk

---

## 7. D.4 — Bakım → yakıt tahmin geri besleme (kapalı döngü)

### 7.1 Motivasyon

Mevcut `PredictionService.predict_consumption` çoğaltıcı zinciri:

```
fallback_l_100km = physics_l_100km × sofor_influence × ramp_factor
```

Burada `weather_factor` zaten physics modeline giriyor. Eksik olan: **araç
sağlığı**. Bakımı geciken bir araç ile taze bakım yapılmış aracın yakıt
tüketimleri eşit olamaz — yağ/filtre/lastik vb. eskime literatürde %5-15
arası fark yaratır.

D.1 bu farkı *tüketim verisinden geriye* okuyor ama tahmin tarafı bu
bilgiyi *ileriye* kullanmıyor. D.4 bunu kapatır:

```
fallback_l_100km = physics_l_100km
                 × sofor_influence
                 × ramp_factor
                 × maintenance_factor   ← YENİ
```

### 7.2 `app/core/ml/vehicle_health_factor.py`

```python
"""Feature D.4 — Bakım statüsünden yakıt tahmin çarpanı.

Saf fonksiyon: AracBakim listesinden + bugünkü tarihten → 0.95..1.25 arası
çarpan döndürür. PredictionService bu çarpanı physics + sofor + ramp
zincirine ekler.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


# ── Sabitler ────────────────────────────────────────────────────────────
# PERIYODIK_AGE_TIERS — başlangıç değerleri pratik kullanımdan kalibre,
# literatür: dizel ağır vasıta yağ değişimi geciktiğinde tüketim
# +%2 ila +%10 arası artar (ATA Technology & Maintenance Council 2021).
# Tier eşikleri 12 aylık (365 gün) PERIYODIK interval'i etrafında simetrik:
#   < 90 gün   = bakım taze, peak verim
#   90-300     = normal aralık (interval'in %25-82'si)
#   300-365    = yaklaşıyor (interval'in %82-100'ü)
#   365-450    = geçti %0-23
#   450-600    = ciddi geçti %23-64
#   600+       = cap (interval'in %64+'ı gecikme)
# ÖNEMLİ: Bu sayılar v1; üretimde 3 ay sonra gerçek tüketim sapması ile
# kalibre edilmeli (telemetry: maintenance_factor vs gerçek L/100km).
PERIYODIK_AGE_TIERS = [
    # (max_days_since_last, factor, label)
    (90,   0.96, "Taze PERIYODIK — verim peak"),
    (300,  1.00, "Normal PERIYODIK aralığı"),
    (365,  1.03, "PERIYODIK yaklaşıyor"),
    (450,  1.07, "PERIYODIK gecikti"),
    (600,  1.12, "PERIYODIK ciddi gecikti"),
    (None, 1.15, "PERIYODIK çok ciddi gecikti (cap)"),
]
NO_HISTORY_FACTOR = 1.05            # PERIYODIK kaydı hiç yok
OPEN_ARIZA_PENALTY = 1.05           # tamamlanmamış ARIZA başı çarpan
OPEN_ACIL_PENALTY = 1.10            # tamamlanmamış ACIL
FACTOR_FLOOR = 0.95
FACTOR_CAP = 1.25


@dataclass
class HealthInput:
    """PredictionService → maintenance_factor için gerekli minimal veri."""
    last_periyodik_date: Optional[datetime]   # son tamamlanmış PERIYODIK
    open_ariza_count: int = 0                 # tamamlanmamış ARIZA sayısı
    open_acil_count: int = 0                  # tamamlanmamış ACIL


@dataclass
class HealthResult:
    factor: float
    base_factor: float                # PERIYODIK katkısı
    arac_penalty: float = 1.0         # ARIZA çarpanı (1.0+)
    acil_penalty: float = 1.0         # ACIL çarpanı (1.0+)
    reason: str = ""                  # UI / log için


def _periyodik_age_factor(
    last_dt: Optional[datetime], now: Optional[datetime] = None
) -> tuple[float, str]:
    if last_dt is None:
        return NO_HISTORY_FACTOR, "PERIYODIK kaydı yok"
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    if now is None:
        now = datetime.now(timezone.utc)
    days = (now - last_dt).days
    for max_days, factor, label in PERIYODIK_AGE_TIERS:
        if max_days is None or days <= max_days:
            return factor, f"{label} ({days} gün)"
    return PERIYODIK_AGE_TIERS[-1][1], PERIYODIK_AGE_TIERS[-1][2]


def compute_maintenance_factor(
    inp: HealthInput, *, now: Optional[datetime] = None
) -> HealthResult:
    base, reason = _periyodik_age_factor(inp.last_periyodik_date, now=now)
    ariza_part = OPEN_ARIZA_PENALTY if inp.open_ariza_count > 0 else 1.0
    acil_part = OPEN_ACIL_PENALTY if inp.open_acil_count > 0 else 1.0
    raw = base * ariza_part * acil_part
    clamped = max(FACTOR_FLOOR, min(FACTOR_CAP, raw))
    return HealthResult(
        factor=round(clamped, 3),
        base_factor=base,
        arac_penalty=ariza_part,
        acil_penalty=acil_part,
        reason=reason,
    )


async def fetch_health_input(uow, arac_id: int) -> HealthInput:
    """DB'den son PERIYODIK + açık ARIZA/ACIL sayısını çeker."""
    from sqlalchemy import text
    sql = """
        SELECT
            (SELECT MAX(bakim_tarihi) FROM arac_bakimlari
             WHERE arac_id = :aid AND tamamlandi = TRUE
                   AND bakim_tipi = 'PERIYODIK') AS last_periyodik,
            (SELECT COUNT(*) FROM arac_bakimlari
             WHERE arac_id = :aid AND tamamlandi = FALSE
                   AND bakim_tipi = 'ARIZA') AS open_ariza,
            (SELECT COUNT(*) FROM arac_bakimlari
             WHERE arac_id = :aid AND tamamlandi = FALSE
                   AND bakim_tipi = 'ACIL') AS open_acil
    """
    row = (await uow.session.execute(text(sql), {"aid": int(arac_id)})).mappings().one()
    return HealthInput(
        last_periyodik_date=row["last_periyodik"],
        open_ariza_count=int(row["open_ariza"] or 0),
        open_acil_count=int(row["open_acil"] or 0),
    )
```

### 7.3 PredictionService entegrasyonu — **DÜZELTME**

#### Eski yaklaşımdaki iki hata

1. **Ensemble path'ini etkilemiyordu.** Mevcut `predict_consumption`
   akışında ensemble başarılı olunca (satır 671) `process_ensemble_result()`
   `fallback_l_100km`'ı kullanmaz → `maintenance_factor` *uygulanmaz*.
   Yeni araçlar (ensemble görenler) bakım gecikmesinden etkilenmiyor olur.
2. **Nested UnitOfWork.** `fetch_health_input` ayrı bir UoW açıyor; mevcut
   adım 1 zaten bir UoW açtı (arac/sofor/dorse fetch). İç içe transaction
   ve gereksiz round-trip.

#### Düzeltilmiş tasarım

**(a) Veri çekme aynı UoW içinde:** Mevcut "1. Fetch entities" bloğunu
genişlet — aynı UoW içinde `last_periyodik_date`, `open_ariza_count`,
`open_acil_count` alanlarını da çek ve `arac` dict'ine `_health_input`
anahtarı altında inject et:

```python
# ── 1. Fetch entities (genişletilmiş — D.4) ───────────────────────────
async with UnitOfWork() as uow:
    if arac_id > 0:
        raw = await uow.arac_repo.get_by_id(arac_id)
        if raw:
            arac = raw.__dict__ if hasattr(raw, "__dict__") else dict(raw)
            # D.4: aynı UoW üzerinden bakım metadata'sı
            from app.core.ml.vehicle_health_factor import fetch_health_input
            arac["_health_input"] = await fetch_health_input(uow, arac_id)
        # ... sofor + dorse aynen ...
```

**(b) Faktör hesaplama erken aşamada:** Adım 4'ten önce (ensemble veya
physics çağrılmadan), maintenance_factor hesapla ve `base_factors`'a yaz:

```python
# ── 2.5. Vehicle health (D.4) — hem ensemble hem physics path'i etkiler
maintenance_factor = 1.0
maintenance_reason: Optional[str] = None
if settings.MAINTENANCE_FACTOR_ENABLED and arac and arac.get("_health_input"):
    try:
        from app.core.ml.vehicle_health_factor import compute_maintenance_factor
        h_res = compute_maintenance_factor(arac["_health_input"])
        maintenance_factor = h_res.factor
        maintenance_reason = h_res.reason
    except Exception as exc:
        logger.warning(
            "maintenance_factor fallback to 1.0 for arac %s: %s", arac_id, exc
        )
```

**(c) Çarpanı *prediction_liters* çıktısına uygula** (ensemble ya da
fallback fark etmeksizin, tek nokta):

`_process_ensemble_result` ve `_run_physics_fallback` iki yerde de aynı
düzeltme: çıktı `prediction_liters`'ı `maintenance_factor` ile çarp.

En temizi: `predict_consumption` *çağırma sonrasında* tek noktada uygulamak.
Mevcut akışta her iki path da bir `dict` (payload) döndürüyor:

```python
# Akışın iki dönüş yolu da bir payload dict üretir (satır 537-553 vs
# _run_physics_fallback). Her ikisinde de "prediction_liters" anahtarı var.
# Tek noktada D.4'i uygula:

def _apply_maintenance_factor(payload: Dict, factor: float, reason: Optional[str]) -> Dict:
    if factor == 1.0:
        return payload  # no-op (flag kapalı veya nötr)
    payload["prediction_liters"] = round(
        float(payload["prediction_liters"]) * factor, 2
    )
    # XAI: Faktörler listesine ekle (zaten orada var ise üstüne yazma)
    payload.setdefault("faktorler", {})["maintenance_factor"] = round(factor, 3)
    if reason:
        payload.setdefault("faktorler", {})["maintenance_reason"] = reason
    # Insight metnine de ekle (operatöre görünür)
    if reason and "Bakım" not in (payload.get("explanation_summary") or ""):
        payload["explanation_summary"] = (
            (payload.get("explanation_summary") or "")
            + f" | Bakım faktörü: {factor:.2f} ({reason})"
        ).strip(" |")
    return payload
```

`predict_consumption`'ın return'lerinden önce çağrılır:

```python
# Ensemble path (mevcut satır 672 civarında)
result = self._process_ensemble_result(...)
return _apply_maintenance_factor(result, maintenance_factor, maintenance_reason)

# Physics fallback path (mevcut satır 694 civarında)
result = self._run_physics_fallback(...)
return _apply_maintenance_factor(result, maintenance_factor, maintenance_reason)
```

#### Neden bu yaklaşım

- **Ensemble retrain gerektirmez.** Modelin görmediği bir feature eklemiyoruz;
  son çıktıyı post-process ediyoruz.
- **Tek noktada uygulama.** İki path için aynı kod → tutarsızlık yok.
- **Geri uyumlu.** Flag kapalı veya `_health_input` yok → factor=1.0 → no-op.
- **XAI görünür.** `faktorler` dict'i frontend "Faktörler" paneline geçer;
  `maintenance_reason` operatöre neden çarpanın bu olduğunu söyler.

#### Sınır durumu — gelecek bakım kayıtları

`fetch_health_input` SQL'i `MAX(bakim_tarihi) WHERE tamamlandi = TRUE`
kullanıyor. `tamamlandi=False` ama `bakim_tarihi` gelecekte olan kayıtlar
(planlanmış ama yapılmamış) burada *open* sayılır → ARIZA/ACIL counters'a
dahildir. PERIYODIK için ise son **tamamlanmış** PERIYODIK temel alınır;
gelecekte yapılacak PERIYODIK durumu etkilemez (henüz bakım yapılmadı).

### 7.4 Feature flag

```python
# app/config.py
MAINTENANCE_FACTOR_ENABLED: bool = True   # D.4 — bakım→yakıt geri besleme
```

Kapalıyken faktör 1.0 → davranış değişmez (geri uyumluluk).

### 7.5 Test stratejisi

**Pure-unit (`test_vehicle_health_factor.py`):**
1. `_periyodik_age_factor` tier sınırları (7 senaryo: None, 0, 89, 90, 299, 364, 600+)
2. `compute_maintenance_factor` — bakım yok + açık arıza
3. `compute_maintenance_factor` — taze PERIYODIK + açık ACIL → ACIL penalty effective
4. Clamp: PERIYODIK 600+ + ARIZA + ACIL → max 1.25
5. Floor: tarihten önce gelecek tarih (clock skew) → factor 0.95 değil 0.96 (taze gibi)
6. Reason metnine bakım tarihinden gün sayısı dahil ediliyor

**Integration (`test_prediction_with_health.py`):**
- DB seed: 1 araç, son PERIYODIK 400 gün önce → `predict_consumption` çıktısında
  `faktorler["maintenance_factor"] >= 1.07`
- DB seed: aynı araç + 1 hafta önce PERIYODIK → factor ≈ 0.96
- DB seed: flag kapalı → factor = 1.0
- predict_consumption sayısal sonuç: bakım faktörü uygulanmış vs uygulanmamış
  arasında yaklaşık %7 fark

### 7.6 D.1 / D.2 / D.3 ile etkileşim

- **D.1 (MaintenancePredictor)**: `_consumption_trend_pct` ile aynı verileri
  kullanıyor. D.4 tahmine factor ekledikçe gerçek tüketim daha doğru tahmin
  ediliyor → sefer formülünde sapma azalır → trend daha temiz görünür → D.1
  daha kararlı çıktı verir.
- **D.2 (endpoint)**: `/predictions` endpoint çıktısına `maintenance_factor`
  alanı *eklenmez* — bu PredictionService'in iç bilgisi. Ama D.3'te araç
  detayı görüntülenirken faktör Faktörler panelinde gösterilir.
- **D.3 (UI)**: PlanWizard XAI panelindeki "Faktörler" listesine
  `maintenance_factor` rozeti olarak da görünür (yeşil <1.0, sarı 1.05-1.10,
  kırmızı >1.10).

---

## 8. Konfig + feature flag

`app/config.py`:

```python
# Feature D — Tahmine dayalı bakım
MAINTENANCE_PREDICTOR_ENABLED: bool = True
MAINTENANCE_PREDICTOR_CACHE_TTL_S: int = 3600   # 1 saat
MAINTENANCE_FACTOR_ENABLED: bool = True         # D.4 — bakım→yakıt
```

Flag KAPALI iken endpoint `503` döner; frontend hata mesajı gösterir.

---

## 9. Yol haritası (alt görevler ve gating)

| Sıra | Alt görev | Çıktı | Test | Tahmini |
|---|---|---|---|---|
| D.1 | maintenance_predictor.py + schema + saf yardımcılar | Engine + Prediction dataclass | 12 unit | 2.5 sa |
| D.2 | 3 endpoint + .ics generator | API routes + audit + 503/403 | 7 integration + 4 ics unit | 2 sa |
| D.3 | Frontend calendar + drawer + table + service + hook | UI + RQ hook + Türkçe metinler | 3 vitest | 3 sa |
| D.4 | vehicle_health_factor + PredictionService entegrasyonu | maintenance_factor faktörler'e dahil | 6 unit + 2 integration | 1.5 sa |

**Toplam tahmin:** ~9 saat.

### Gating

- D.1 → D.2 (D.2 engine'i çağırır)
- D.2 → D.3 (frontend backend'e bağımlı)
- D.4 bağımsız — D.1 ile paralel başlatılabilir, ama sırayla işlersek D.1 sonrası
  yapmak daha doğru (D.1'in çıktıları D.4 testlerinde input olarak kullanılır)

---

## 10. Riskler ve azaltma

| Risk | Etki | Azaltma |
|---|---|---|
| Çok az `seferler.tuketim` verisi olan araçlar → confidence çok düşük | UI'da "yetersiz veri" rozeti |
| Filo medyanı < FILO_MIN_TRIPS_FOR_BENCHMARK → savings_pct = 0 | Beklenen davranış, mesaj göster |
| `arac_bakimlari` PERIYODIK kaydı yok → bazı araçlar `predictable=False` | UI: "Bakım geçmişi eksik" rozeti + manuel ekleme linki |
| FullCalendar bundle artışı (~150 KB gzip) | Sadece BakimPage'de lazy import; ana bundle etkilenmez |
| .ics karakter encoding (Türkçe ş/ğ/ı/ü) | RFC 5545 UTF-8 kabul ediyor; `Content-Type: text/calendar; charset=utf-8` |
| Cache miss çok sık → her istekte tüm araçlar için ağır SQL | Redis 1 saat cache + create/complete'ta invalidate |

---

## 11. PII ve güvenlik

- Endpoint dönüş **şoför adı içermez** (sadece araç plakası + bakım metadata).
- LLM çağrısı **YOK** — tüm karar deterministik formül.
- `reasons` PII'siz, sadece sayısal/kategorik bilgi.
- `.ics` description'ında plaka var (admin'in göreceği veri); Telegram'a otomatik gönderim yok.
- Audit log: `predictions_viewed` (entity_id=None, user_id, count).

---

## 12. Acceptance criteria

- [ ] `GET /admin/maintenance/predictions` happy path 200 + liste döner
- [ ] Yetersiz veri olan araç → `predictable=False`, `reasons` doldurulmuş
- [ ] PERIYODIK bakım tarihi yok + son 6 ayda sefer yok → `predictable=False`
- [ ] `.ics` endpoint Content-Type=text/calendar + valid RFC 5545
- [ ] Feature flag kapalı → 503
- [ ] RBAC: yetkisiz → 403
- [ ] Frontend takvim: 3+ event görünür, eventClick drawer açar
- [ ] Drawer: "İndirme" butonu doğru URL'e gider
- [ ] **D.4:** PERIYODIK 400 gün gecikmiş araç → `predict_consumption` çıktısında
      `faktorler["maintenance_factor"] >= 1.07`
- [ ] **D.4:** Taze PERIYODIK (≤90 gün) → `maintenance_factor ≤ 0.97`
- [ ] **D.4:** `MAINTENANCE_FACTOR_ENABLED=False` → factor = 1.0 (geri uyumlu)
- [ ] **D.4:** Açık ACIL bakım → factor cap (1.25)'e doğru artar
- [ ] Tüm yeni unit/vitest testleri yeşil
- [ ] `ruff check --ignore=E501`, `tsc`, `vite build` temiz
- [ ] `npm install` ile yeni dependency eklenmiş; ana bundle artışı raporlanmış

---

## 13. Açık notlar (uygulama sırasında karara bağlanacak)

1. **D.1 — Sefer km verisi.** `seferler.mesafe_km` toplamından kullanım
   hızı çıkarıyoruz. Eksik/null `tuketim` olan seferler `km_per_month`
   hesabını etkilemez ama trend hesabında dışlanır. Veri kalitesi
   sorgu sonucunu loglayalım (count of nulls).
2. **ARIZA/ACIL semantiği.** İki farklı kullanım:
   - **D.1** PERIYODIK için *tahmin* yapar; ARIZA/ACIL için tahmin
     üretmez (reaktif olaylar).
   - **D.4** AÇIK (tamamlanmamış) ARIZA/ACIL'ı *penalty* olarak kullanır
     (faktör çarpanı). Çelişki değil, ayrı amaç.
3. **BakimPage URL state.** Yeni takvim sekmesi mevcut BakimPage'a eklenir;
   sekme durumu `?view=calendar|list` URL parametresinde tutulur (paylaşılabilir).
4. **Çoklu bakım tipi.** D scope dışı (yağ + balata ayrı interval). Sonraki
   iterasyonda interval tablosu DB'ye taşınır; v1'de PERIYODIK tek tip.
5. **Dorse (treyler) bakımı.** `AracBakim.dorse_id` mevcut ama bu plan
   sadece `arac_id` üzerinden çalışır. Treyler bakımı yakıt faktörüne
   dahil edilmez (yalnız PERIYODIK çekici interval). Sonraki iterasyonda
   `vehicle_health_factor` dorse'yi de okuyabilir.
6. **Gelecek-tarihli bakım kayıtları** (`bakim_tarihi > now() AND
   tamamlandi=False`) — bunlar "planlanmış ama yapılmamış". D.1
   `MaintenancePredictor.fetch_inputs` SQL'i `tamamlandi=TRUE` filtresi
   kullandığı için bunları dışlar. D.4 `fetch_health_input` ise
   tamamlanmamış kayıtları ARIZA/ACIL count'larına dahil eder; PERIYODIK
   için `tamamlandi=TRUE` filtresi var → tutarlı.
7. **Telemetri/observability.** D.4 verimini değerlendirmek için 3 ay
   sonra şu metriği topla: araç başına `maintenance_factor` × gerçek
   tüketim sapması. Eğer çarpan ile sapma korelasyonu zayıfsa tier
   eşiklerini güncelle. v1'de Prometheus counter `maintenance_factor_applied_total{tier="..."}`.

Bu 7 nokta D.1 başlangıcında doğrulanır, ardından plan kilitlenir.
