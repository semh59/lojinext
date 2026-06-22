# Feature C — Akıllı Sefer Planlama Sihirbazı (Mini-Plan v3)

**Tarih:** 2026-05-26
**Status:** PLAN — uygulamaya hazır
**Önceki sürümler:** yok (Feature A/B v3 deneyiminden çıkarılan operasyonel
şablonla doğrudan v3 yazılmıştır).

---

## 0. Özet (TL;DR)

Yeni bir sefer planlanırken yönetici hâlâ araç + şoför + tarih bilgisini manuel
seçiyor. Bu plan, mevcut üç motoru —
`app/core/ml/route_similarity.py`, `app/core/ml/driver_route_profile.py`,
`app/api/v1/endpoints/weather.py`'deki `/weather/trip-impact` — tek bir
**Trip Planner** karar fonksiyonunda birleştirir. Çıktı: 3 araç + 3 şoför
adayı, her birinin tahmini yakıt/maliyet/süre/risk skoru ile.

Mevcut `predict_consumption()` pipeline'ı zaten weather + ensemble + driver
düzeltmesini yapıyor — yeniden yazmıyoruz; *adaylar üzerinde döngüye sokuyoruz*.

---

## 1. İş ihtiyacı (sorun → değer)

| Bugün | C ile |
|---|---|
| Yönetici planlama sırasında "bu güzergaha en uygun araç hangisi" diye tek tek geçmişe bakıyor | Wizard 3 araç + 3 şoför adayını skor ile listeler |
| Hava risk bilgisi planlama anında değil, sefer kaydedildikten sonra hesaplanıyor | Wizard adımı tarih + güzergah seçilince anında `fuel_impact_factor` döndürür |
| Şoför × güzergah tipi performansı (`/drivers/{id}/route-profile`) görselleştirilmiş ama planlamaya bağlı değil | Şoför skorlaması bu profili ağırlık olarak kullanır |
| Yeni bir araç filoya eklenince "geçmiş yok, ne kadar yakar?" sorusu cevapsız | Cold-start: aynı segment/yıl araçların ortalaması (physics fallback `predict_consumption` zaten yapıyor) |

**Hedef KPI:** Manuel planlama süresi (admin start→submit) ≥ %40 düşmeli.
Plan başlangıç için her admin'in araç/şoför değiştirme oranı ölçümlenir
(Sentry breadcrumb veya `audit_log` `trip_plan_wizard_used`).

---

## 2. Karar matrisi (4 kritik soru ve cevapları)

### Q1 — Adayları nasıl seçeceğiz? (universe sorusu)

**Cevap:** İki katmanlı **shortlisting**.

1. **Hard filter** (aktif + uygun):
   - `arac.aktif=True`, `arac.muayene_bitis>tarih`, `arac.deleted_at IS NULL`
   - `sofor.aktif=True`, `sofor.deleted_at IS NULL`
   - Çakışma kontrolü: aynı `tarih`'te `arac_id`/`sofor_id` zaten
     `planlandi|yolda` durumunda olan sefer varsa **eler**.
2. **Soft scoring** (rank): kalan adaylarda kompozit skor.

Hard filter sonucu boş ise wizard `{"candidates": [], "reason":
"no_eligible_resources"}` döner — UI "uygun araç/şoför yok" mesajı gösterir.

### Q2 — Skorlama formülü? (anchor sorusu)

**Cevap:** Araç ve şoför için ayrı, ama benzer normalize edilmiş kompozit.

#### Araç skoru (0..1, yüksek = iyi):
```
arac_score =
    0.40 * fuel_efficiency_score     # 1 - normalize(predicted_liters)
  + 0.25 * route_history_score       # tarihsel benzer güzergah uyumu
  + 0.20 * vehicle_health_score      # yaş + bakım uyarısı yok
  + 0.15 * availability_score        # son 7 gün sefer sayısı (overuse penalty)
```

- `fuel_efficiency_score`: Adayın `predict_consumption()` çıktısı normalize
  edilir → en az tüketen 1.0, en çok 0.0 (min-max içinde aday seti üzerinden).
- `route_history_score`: `find_similar_trips()` ile aday aracın son 90 gün
  benzer güzergah seferi sayısı → `min(count/5, 1.0)`.
- `vehicle_health_score`: `(1 - age/25) * (no_open_maintenance_alert ? 1 : 0.5)`.
  Yaş cap=25 (eski TIR'lar tipik).
- `availability_score`: Son 7 gün sefer sayısı; `7-count` → max 0, normalize
  `min(idle_days/7, 1.0)`. Az kullanılan araca öncelik.

#### Şoför skoru (0..1):
```
sofor_score =
    0.50 * route_type_performance    # driver_route_profile sapma_pct → ters
  + 0.30 * overall_hybrid_score      # /drivers/{id}/score-breakdown.total / 100
  + 0.20 * availability_score        # son 7 gün sefer sayısı
```

- `route_type_performance`: Aday güzergah `classify_route()` ile sınıflandırılır
  → `driver_route_profile.get(rtype).deviation_pct`. Düşük = iyi.
  Normalizasyon: `score = max(0, 1 - abs(deviation_pct)/30)`. Yeterli veri yoksa
  (`trip_count < 5`) 0.5 (nötr/orta).
- `overall_hybrid_score`: `get_score_breakdown(sofor_id).total / 100` (zaten 0..100).
- `availability_score`: yukarıdakiyle aynı.

### Q3 — Cold-start ve eksik veri davranışı?

**Cevap:**

| Senaryo | Davranış |
|---|---|
| Yeni araç (sefer geçmişi 0) | `route_history_score=0`, `fuel_efficiency_score=physics_estimate` (predict_consumption zaten cold-start için physics_fuel_predictor'a düşer). UI'da rozet: "Yeni araç — tahmin fizik motorundan" |
| Yeni şoför | `route_type_performance=0.5` (nötr), `overall_hybrid_score=0.5` (manuel skor varsayılan). UI: "Yeni şoför — performans verisi yok" |
| Hava verisi yok (geocoding fail / 503) | `weather_impact=1.0` (nötr), `risk_label="unknown"`. Sefer planı bloklamaz |
| Hard filter boş | `candidates=[]`, `reason` set |

### Q4 — Gerçek zamanlı vs cache?

**Cevap:** Hibrit.

- **Plan endpoint** (`POST /trips/plan-wizard`) **gerçek zamanlı** çalışır
  (admin tetikler, beklemeye razı — UI loading spinner). Tahmin için adaylar
  üzerinde paralel `asyncio.gather` ile maks 10 araç + 10 şoför kombinasyonu
  hesaplanır.
- **Şoför profil** ve **araç tarihçesi** sorgular: Redis cache, TTL=5 dk
  (`trip_planner:driver_profile:{sofor_id}`, ...). Cache kapatma için aynı
  flag pattern (settings.TRIP_PLANNER_CACHE_TTL_S).
- **Hava** zaten cache'lendiği için endpoint'i doğrudan çağırırız
  (mevcut WeatherService cache'i).

Maks aday sayısı: **top-10 araç + top-10 şoför hard-filter sonucu**, sonra
ranking, sonra **top-3 araç + top-3 şoför** UI'a döner. UI 3+3=6 öneri
gösterir ama backend `top_n` query param ile 1..5 arası seçilebilir kılınır
(default 3).

---

## 3. Mimari (yeni + değişen dosyalar)

### Backend

```
app/
├── core/
│   └── ai/
│       └── trip_planner.py                    # NEW (C.1) — TripPlanner engine
├── api/v1/endpoints/
│   └── trips.py                                # MODIFY (C.3) — POST /plan-wizard
├── schemas/
│   └── trip_planner.py                         # NEW (C.1/C.3) — Pydantic schemas
├── config.py                                   # MODIFY — TRIP_PLANNER_ENABLED + TTL
└── tests/
    ├── unit/
    │   ├── test_trip_planner_scoring.py        # NEW (C.1) — pure scoring logic
    │   └── test_trip_planner_filters.py        # NEW (C.1) — hard filter rules
    └── integration/
        └── test_plan_wizard_endpoint.py        # NEW (C.3) — endpoint contract
```

### Frontend

```
frontend/src/
├── components/trips/
│   ├── PlanWizardStep.tsx                     # NEW (C.4) — wizard step
│   ├── PlanWizardCard.tsx                     # NEW (C.4) — single suggestion card
│   ├── PlanWizardXaiPanel.tsx                 # NEW (C.5) — "neden bu?" panel
│   ├── TripFormModal.tsx                      # MODIFY (C.4) — wizard adımı
│   └── __tests__/
│       ├── PlanWizardStep.test.tsx            # NEW
│       ├── PlanWizardCard.test.tsx            # NEW
│       └── PlanWizardXaiPanel.test.tsx        # NEW
├── services/api/
│   └── trip-planner-service.ts                # NEW — API wrapper
├── resources/tr/
│   └── tripPlanner.ts                         # NEW — Turkish strings
└── hooks/
    └── usePlanWizard.ts                       # NEW — React Query hook
```

**Dokunulmayan dosyalar (önemli):**
- `app/core/ml/ensemble_predictor.py` — kullanılacak ama dokunulmayacak
- `app/core/ml/route_similarity.py` — kullanılacak
- `app/core/services/sofor_service.get_route_profile()` — kullanılacak
- `app/api/v1/endpoints/weather.py /trip-impact` — fetch edilecek
- Sefer create endpoint — wizard sadece **öneri** döner, gerçek create
  hâlâ mevcut `POST /trips` çağırılır (UI form prefill yapar)

---

## 4. C.1 — Trip Planner backend logic

### 4.1 Dosya: `app/core/ai/trip_planner.py`

```python
"""Feature C — Akıllı sefer planlama motoru.

Verilen güzergah + tarih + yük için 3 araç + 3 şoför adayı önerir.
Mevcut motorları (ensemble predict, route_similarity, driver_route_profile,
weather/trip-impact) birleştirir; yeni ML modeli eğitmez.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.ml.driver_route_profile import classify_route
from app.core.ml.route_similarity import find_similar_trips
from app.core.services.sofor_service import SoforService
from app.database.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


# ── Sabitler ────────────────────────────────────────────────────────────
ARAC_WEIGHTS = {
    "fuel": 0.40,
    "route_history": 0.25,
    "vehicle_health": 0.20,
    "availability": 0.15,
}
SOFOR_WEIGHTS = {
    "route_type_perf": 0.50,
    "overall_hybrid": 0.30,
    "availability": 0.20,
}
SHORTLIST_SIZE = 10           # hard filter sonrası top-N
DEFAULT_TOP_N = 3             # UI'a dönen öneri sayısı
DRIVER_PROFILE_DEV_NORM = 30  # |dev_pct| <= 30 → 0..1 normalize
VEHICLE_AGE_CAP = 25
AVAILABILITY_WINDOW_DAYS = 7


# ── Veri sınıfları ──────────────────────────────────────────────────────
@dataclass
class PlanInput:
    cikis_yeri: str
    varis_yeri: str
    mesafe_km: float
    tarih: date
    ascent_m: float = 0.0
    descent_m: float = 0.0
    flat_distance_km: float = 0.0
    route_analysis: Optional[Dict[str, Any]] = None
    weight_kg: float = 0.0      # net_kg
    guzergah_id: Optional[int] = None


@dataclass
class VehicleCandidate:
    arac_id: int
    plaka: str
    yas: int
    score: float                              # 0..1 final
    predicted_liters: float
    fuel_score: float
    route_history_score: float
    vehicle_health_score: float
    availability_score: float
    similar_trip_count: int
    cold_start: bool                          # geçmiş yok
    reasons: List[str]                        # XAI gerekçeleri (PII yok)


@dataclass
class DriverCandidate:
    sofor_id: int
    ad_soyad: str
    score: float
    route_type_perf: float
    overall_hybrid: float
    availability_score: float
    route_type: str
    deviation_pct: float
    cold_start: bool
    reasons: List[str]


@dataclass
class PlanResult:
    weather_impact: float                     # 1.0 = nötr
    risk_label: str                           # low|medium|high|unknown
    route_type: str                           # classify_route sonucu
    vehicles: List[VehicleCandidate]
    drivers: List[DriverCandidate]
    generated_at: datetime
    cache_hit: bool = False


# ── Ana giriş ──────────────────────────────────────────────────────────
class TripPlannerEngine:
    """Stateless engine; HTTP layer her istekte yeniden başlatır."""

    def __init__(self, prediction_service):
        self.predictor = prediction_service     # PredictionService instance

    async def plan(self, inp: PlanInput, top_n: int = DEFAULT_TOP_N) -> PlanResult:
        top_n = max(1, min(top_n, 5))
        route_type = self._classify(inp)
        # 1. Hava (paralel)
        weather_task = asyncio.create_task(self._weather_impact(inp))
        # 2. Adaylar (hard filter)
        vehicles_raw, drivers_raw = await self._shortlist(inp)
        weather_impact = await weather_task
        # 3. Skorla
        vehicles = await self._score_vehicles(vehicles_raw, inp, weather_impact)
        drivers = await self._score_drivers(drivers_raw, inp, route_type)
        vehicles.sort(key=lambda v: v.score, reverse=True)
        drivers.sort(key=lambda d: d.score, reverse=True)
        return PlanResult(
            weather_impact=weather_impact,
            risk_label=_risk_label(weather_impact),
            route_type=route_type,
            vehicles=vehicles[:top_n],
            drivers=drivers[:top_n],
            generated_at=datetime.now(timezone.utc),
        )

    # —— Aşamalı yardımcılar (her biri unit-test edilebilir) ————————
    def _classify(self, inp: PlanInput) -> str:
        ra = inp.route_analysis or {
            "motorway": {"flat": inp.flat_distance_km},
            "ascent_m": inp.ascent_m,
            "descent_m": inp.descent_m,
        }
        try:
            return classify_route(ra)
        except Exception:
            return "mixed"

    async def _weather_impact(self, inp: PlanInput) -> float:
        """Hava etkisi: 1.0 nötr; başarısız ise nötr döner."""
        # WeatherService'i container'dan al — service mantığı zaten cache yapıyor
        from app.core.container import container
        svc = container.weather_service
        try:
            async with UnitOfWork() as uow:
                # Guzergah varsa koord oradan; yoksa nötr
                if not inp.guzergah_id:
                    return 1.0
                route = await uow.lokasyon_repo.get_by_id(inp.guzergah_id)
                if not route or not route.get("cikis_lat") or not route.get("varis_lat"):
                    return 1.0
            result = await svc.get_trip_impact_analysis(
                route["cikis_lat"], route["cikis_lon"],
                route["varis_lat"], route["varis_lon"],
            )
            if not result.get("success"):
                return 1.0
            return float(result.get("fuel_impact_factor") or 1.0)
        except Exception as exc:
            logger.warning("Weather fetch failed for planner: %s", exc)
            return 1.0

    async def _shortlist(self, inp: PlanInput):
        """Aktif + müsait + uygun araç/şoför listesini SHORTLIST_SIZE'a indirir."""
        async with UnitOfWork() as uow:
            # Hard filter — repo-level
            vehicles = await uow.arac_repo.get_eligible_for_planning(
                trip_date=inp.tarih, limit=SHORTLIST_SIZE
            )
            drivers = await uow.sofor_repo.get_eligible_for_planning(
                trip_date=inp.tarih, limit=SHORTLIST_SIZE
            )
        return vehicles, drivers

    async def _score_vehicles(
        self,
        vehicles: List[Dict[str, Any]],
        inp: PlanInput,
        weather_impact: float,
    ) -> List[VehicleCandidate]:
        # 1. Predict in parallel
        async def _predict(v):
            return await self.predictor.predict_consumption(
                arac_id=int(v["id"]),
                mesafe_km=inp.mesafe_km,
                ton=inp.weight_kg / 1000.0,
                ascent_m=inp.ascent_m,
                descent_m=inp.descent_m,
                flat_distance_km=inp.flat_distance_km,
                route_analysis=inp.route_analysis,
                target_date=inp.tarih,
                use_ensemble=True,
            )

        preds = await asyncio.gather(*[_predict(v) for v in vehicles])

        # 2. Similar trip counts (paralel)
        similar_counts = await asyncio.gather(*[
            self._count_similar(v, inp) for v in vehicles
        ])

        # 3. Normalize fuel scores across the candidate set
        liters = [
            float(p.get("prediction_liters") or 0) for p in preds
        ]
        min_l, max_l = min(liters) if liters else 0, max(liters) if liters else 0
        spread = (max_l - min_l) or 1.0

        out: List[VehicleCandidate] = []
        for v, pred, sim_count in zip(vehicles, preds, similar_counts):
            litres = float(pred.get("prediction_liters") or 0)
            fuel_score = 1.0 - (litres - min_l) / spread        # 0..1
            route_history_score = min(sim_count / 5.0, 1.0)
            age = _vehicle_age_years(v)
            has_open_alert = bool(v.get("has_open_maintenance_alert"))
            vehicle_health_score = (1 - min(age / VEHICLE_AGE_CAP, 1.0)) * (
                0.5 if has_open_alert else 1.0
            )
            availability_score = _availability_score(v.get("recent_trip_count", 0))
            score = (
                ARAC_WEIGHTS["fuel"] * fuel_score
                + ARAC_WEIGHTS["route_history"] * route_history_score
                + ARAC_WEIGHTS["vehicle_health"] * vehicle_health_score
                + ARAC_WEIGHTS["availability"] * availability_score
            )
            reasons = _vehicle_reasons(
                fuel_score, route_history_score, vehicle_health_score,
                availability_score, sim_count, age, has_open_alert
            )
            out.append(VehicleCandidate(
                arac_id=int(v["id"]),
                plaka=v.get("plaka") or "",
                yas=age,
                score=round(score, 3),
                predicted_liters=round(litres, 1),
                fuel_score=round(fuel_score, 3),
                route_history_score=round(route_history_score, 3),
                vehicle_health_score=round(vehicle_health_score, 3),
                availability_score=round(availability_score, 3),
                similar_trip_count=sim_count,
                cold_start=(sim_count == 0),
                reasons=reasons,
            ))
        return out

    async def _count_similar(self, v: Dict[str, Any], inp: PlanInput) -> int:
        if not inp.route_analysis:
            return 0
        try:
            sims = await find_similar_trips(
                inp.route_analysis, inp.mesafe_km, limit=10
            )
            # find_similar_trips şu an arac filtrelemiyor — sadece güzergah uyumu;
            # Bu C.1'in scope'unda kabul edilebilir bir yaklaşıklık.
            return len(sims)
        except Exception:
            return 0

    async def _score_drivers(
        self,
        drivers: List[Dict[str, Any]],
        inp: PlanInput,
        route_type: str,
    ) -> List[DriverCandidate]:
        out: List[DriverCandidate] = []
        # SoforService'i singleton değil, repo bazlı çağırıyoruz (UoW içinde)
        async with UnitOfWork() as uow:
            svc = SoforService(repo=uow.sofor_repo)
            for d in drivers:
                sofor_id = int(d["id"])
                try:
                    score_breakdown = await svc.get_score_breakdown(sofor_id)
                    route_profile = await svc.get_route_profile(sofor_id)
                except Exception as exc:
                    logger.warning("Driver profile fetch failed: %s", exc)
                    score_breakdown = {"total": 50.0, "has_trips": False}
                    route_profile = {"profiles": []}
                profile_for_type = next(
                    (p for p in route_profile.get("profiles", []) if p["route_type"] == route_type),
                    None,
                )
                cold_start = not bool(score_breakdown.get("has_trips"))
                if not profile_for_type or profile_for_type.get("trip_count", 0) < 5:
                    route_type_perf = 0.5
                    deviation_pct = 0.0
                else:
                    deviation_pct = float(profile_for_type.get("deviation_pct", 0))
                    route_type_perf = max(
                        0.0,
                        1.0 - min(abs(deviation_pct) / DRIVER_PROFILE_DEV_NORM, 1.0),
                    )
                overall_hybrid = max(0.0, min(1.0, float(score_breakdown.get("total", 50.0)) / 100.0))
                availability_score = _availability_score(d.get("recent_trip_count", 0))
                score = (
                    SOFOR_WEIGHTS["route_type_perf"] * route_type_perf
                    + SOFOR_WEIGHTS["overall_hybrid"] * overall_hybrid
                    + SOFOR_WEIGHTS["availability"] * availability_score
                )
                reasons = _driver_reasons(
                    route_type, route_type_perf, deviation_pct,
                    overall_hybrid, availability_score, cold_start,
                )
                out.append(DriverCandidate(
                    sofor_id=sofor_id,
                    ad_soyad=d.get("ad_soyad") or "",
                    score=round(score, 3),
                    route_type_perf=round(route_type_perf, 3),
                    overall_hybrid=round(overall_hybrid, 3),
                    availability_score=round(availability_score, 3),
                    route_type=route_type,
                    deviation_pct=round(deviation_pct, 1),
                    cold_start=cold_start,
                    reasons=reasons,
                ))
        return out


# ── Saf yardımcılar (test edilebilir) ──────────────────────────────────
def _risk_label(impact: float) -> str:
    if impact > 1.10:
        return "high"
    if impact > 1.02:
        return "medium"
    if impact == 1.0:
        return "unknown"
    return "low"


def _availability_score(recent_trips: int) -> float:
    # 0 sefer → 1.0, 7+ sefer → 0
    return max(0.0, min(1.0, (AVAILABILITY_WINDOW_DAYS - recent_trips) / AVAILABILITY_WINDOW_DAYS))


def _vehicle_age_years(v: Dict[str, Any]) -> int:
    model_yili = v.get("model_yili") or v.get("imal_yili") or 0
    if model_yili <= 0:
        return 0
    return max(0, date.today().year - int(model_yili))


def _vehicle_reasons(...) -> List[str]:
    # PII yok — sadece sayısal/kategorik. UI Türkçe gösterimi yapar.
    ...


def _driver_reasons(...) -> List[str]:
    ...
```

> **Not:** Yukarıdaki `_vehicle_reasons`/`_driver_reasons` C.5'te
> doldurulacak — şimdilik liste boş döner.

### 4.2 Repo eklemeleri

`app/database/repositories/arac_repo.py`:

```python
async def get_eligible_for_planning(
    self, *, trip_date: date, limit: int = 10
) -> List[Dict[str, Any]]:
    """Aktif + muayene geçerli + o tarihte çakışan seferi olmayan araçlar.

    Cevap satırı: id, plaka, model_yili, has_open_maintenance_alert,
                  recent_trip_count (son 7 gün).
    """
    sql = text("""
        SELECT
            a.id, a.plaka, a.model_yili,
            EXISTS (
                SELECT 1 FROM araclar_bakim_alarm ab
                WHERE ab.arac_id = a.id AND ab.durum = 'open'
            ) AS has_open_maintenance_alert,
            (
                SELECT COUNT(*) FROM seferler s2
                WHERE s2.arac_id = a.id
                  AND s2.tarih >= :recent_cutoff
            ) AS recent_trip_count
        FROM araclar a
        WHERE a.aktif = TRUE
          AND a.deleted_at IS NULL
          AND (a.muayene_bitis IS NULL OR a.muayene_bitis >= :trip_date)
          AND NOT EXISTS (
              SELECT 1 FROM seferler s
              WHERE s.arac_id = a.id
                AND s.tarih = :trip_date
                AND s.durum IN ('planlandi', 'yolda')
                AND s.deleted_at IS NULL
          )
        ORDER BY recent_trip_count ASC, a.id DESC
        LIMIT :limit
    """)
    cutoff = trip_date - timedelta(days=7)
    rows = (await self.session.execute(sql, {
        "trip_date": trip_date,
        "recent_cutoff": cutoff,
        "limit": limit,
    })).mappings().all()
    return [dict(r) for r in rows]
```

`app/database/repositories/sofor_repo.py` benzeri: `get_eligible_for_planning`
(soforler tablosunda aktif + ehliyet geçerli + çakışma yok).

> **`araclar_bakim_alarm` tablosu varsa kullan; yoksa** `has_open_maintenance_alert=FALSE` döndür (planlı + atıl).
> Buna karar şu komutla verilecek:
> ```bash
> python -c "from app.database.models import Base; print([t for t in Base.metadata.tables if 'bakim' in t])"
> ```

### 4.3 Test stratejisi

**Pure-unit (DB yok):**
- `_risk_label` (4 senaryo)
- `_availability_score` (boundary)
- `_vehicle_age_years` (model_yili boş/null/normal)
- Skorlama formülü: sentetik `_score_vehicles` input → beklenen skor

**Integration (DB var):**
- `test_plan_wizard_endpoint.py` — gerçek araç + şoför seed + endpoint çağrısı.
- Cold-start case: yeni araç (geçmiş yok) → `cold_start=True`.

---

## 5. C.2 — Weather risk hesabı

Mevcut `WeatherService.get_trip_impact_analysis` zaten `fuel_impact_factor`
döndürüyor. C.2'de yeni endpoint yok; `TripPlannerEngine._weather_impact`
fonksiyonu wrapper. Tek değişiklik: `risk_label` mapping.

| `fuel_impact_factor` | `risk_label` | UI rengi |
|---|---|---|
| 1.0 (data yok) | unknown | gri |
| < 1.0 | low | yeşil |
| 1.02 → 1.10 | medium | sarı |
| > 1.10 | high | turuncu |

### 5.1 Test

`test_trip_planner_filters.py`'da `_risk_label` tablosu test edilir.

---

## 6. C.3 — `POST /trips/plan-wizard` endpoint

### 6.1 Path + payload

```http
POST /api/v1/trips/plan-wizard
Authorization: Bearer ...
Content-Type: application/json

{
  "tarih": "2026-06-15",
  "guzergah_id": 42,                 # opsiyonel — verilirse koord/route_analysis backend okur
  "cikis_yeri": "Ankara",            # guzergah_id yoksa zorunlu
  "varis_yeri": "İstanbul",
  "mesafe_km": 450,
  "ascent_m": 320,
  "descent_m": 310,
  "flat_distance_km": 400,
  "weight_kg": 22000,
  "top_n": 3                         # default 3, max 5
}
```

### 6.2 Response

```json
{
  "weather_impact": 1.07,
  "risk_label": "medium",
  "route_type": "highway_dominant",
  "vehicles": [
    {
      "arac_id": 12,
      "plaka": "34 ABC 123",
      "yas": 4,
      "score": 0.812,
      "predicted_liters": 142.3,
      "fuel_score": 0.95,
      "route_history_score": 0.8,
      "vehicle_health_score": 0.84,
      "availability_score": 0.71,
      "similar_trip_count": 4,
      "cold_start": false,
      "reasons": ["Bu güzergahta 4 başarılı sefer geçmişi", "Düşük yakıt sapması"]
    }
    // ... 2 more
  ],
  "drivers": [
    {
      "sofor_id": 7,
      "ad_soyad": "Ali Veli",
      "score": 0.78,
      "route_type_perf": 0.85,
      "overall_hybrid": 0.72,
      "availability_score": 0.71,
      "route_type": "highway_dominant",
      "deviation_pct": -4.5,
      "cold_start": false,
      "reasons": ["Otoyol seferlerinde %4.5 tasarruflu", "Yüksek hibrit skor"]
    }
  ],
  "generated_at": "2026-06-12T10:32:11+00:00",
  "cache_hit": false
}
```

### 6.3 Status kodları

| Kod | Durum |
|---|---|
| 200 | başarı |
| 400 | zorunlu alan eksik / negatif değer |
| 401 | auth yok |
| 403 | yetki yok (`sefer:write` gerekli) |
| 503 | `TRIP_PLANNER_ENABLED=False` |

### 6.4 Endpoint kod taslağı

```python
# app/api/v1/endpoints/trips.py — sonuna ekle

from app.core.ai.trip_planner import TripPlannerEngine, PlanInput
from app.schemas.trip_planner import (
    PlanWizardRequest, PlanWizardResponse,
)

@router.post(
    "/plan-wizard",
    response_model=PlanWizardResponse,
    dependencies=[Depends(RateLimiterDependency("plan_wizard", rate=20.0, period=60.0))],
)
async def plan_wizard(
    payload: PlanWizardRequest,
    db: SessionDep,
    pred_service: Annotated[PredictionService, Depends(get_prediction_service)],
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
) -> PlanWizardResponse:
    if not settings.TRIP_PLANNER_ENABLED:
        raise HTTPException(503, "Sefer planlama sihirbazı kapalı")

    # Güzergah varsa rota detayını oradan al
    route_analysis = None
    if payload.guzergah_id:
        guzergah = await db.get(Lokasyon, payload.guzergah_id)
        if guzergah and guzergah.rota_detay:
            route_analysis = guzergah.rota_detay.get("route_analysis") or guzergah.rota_detay

    inp = PlanInput(
        cikis_yeri=payload.cikis_yeri,
        varis_yeri=payload.varis_yeri,
        mesafe_km=payload.mesafe_km,
        tarih=payload.tarih,
        ascent_m=payload.ascent_m or 0,
        descent_m=payload.descent_m or 0,
        flat_distance_km=payload.flat_distance_km or 0,
        route_analysis=route_analysis,
        weight_kg=payload.weight_kg or 0,
        guzergah_id=payload.guzergah_id,
    )
    engine = TripPlannerEngine(pred_service)
    result = await engine.plan(inp, top_n=payload.top_n or 3)
    # Audit: kim wizard kullandı?
    await log_audit_event(
        module="trip_planner",
        action="plan_wizard_used",
        entity_id=None,
        user_id=current_admin.id,
        new_value={
            "tarih": payload.tarih.isoformat(),
            "mesafe_km": payload.mesafe_km,
            "guzergah_id": payload.guzergah_id,
        },
    )
    return PlanWizardResponse.from_engine_result(result)
```

### 6.5 Schemas (`app/schemas/trip_planner.py`)

```python
from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

RiskLabel = Literal["low", "medium", "high", "unknown"]
RouteType = Literal["highway_dominant", "mountain", "urban", "mixed"]


class PlanWizardRequest(BaseModel):
    tarih: date
    guzergah_id: Optional[int] = Field(None, gt=0)
    cikis_yeri: str = Field(..., min_length=1, max_length=120)
    varis_yeri: str = Field(..., min_length=1, max_length=120)
    mesafe_km: float = Field(..., gt=0, le=5000)
    ascent_m: Optional[float] = Field(0, ge=0, le=20000)
    descent_m: Optional[float] = Field(0, ge=0, le=20000)
    flat_distance_km: Optional[float] = Field(0, ge=0, le=5000)
    weight_kg: Optional[float] = Field(0, ge=0, le=80000)
    top_n: Optional[int] = Field(3, ge=1, le=5)


class VehicleSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    arac_id: int
    plaka: str
    yas: int
    score: float
    predicted_liters: float
    fuel_score: float
    route_history_score: float
    vehicle_health_score: float
    availability_score: float
    similar_trip_count: int
    cold_start: bool
    reasons: List[str]


class DriverSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sofor_id: int
    ad_soyad: str
    score: float
    route_type_perf: float
    overall_hybrid: float
    availability_score: float
    route_type: RouteType
    deviation_pct: float
    cold_start: bool
    reasons: List[str]


class PlanWizardResponse(BaseModel):
    weather_impact: float
    risk_label: RiskLabel
    route_type: RouteType
    vehicles: List[VehicleSuggestion]
    drivers: List[DriverSuggestion]
    generated_at: datetime
    cache_hit: bool = False

    @classmethod
    def from_engine_result(cls, r) -> "PlanWizardResponse":
        return cls(
            weather_impact=r.weather_impact,
            risk_label=r.risk_label,
            route_type=r.route_type,
            vehicles=[VehicleSuggestion(**v.__dict__) for v in r.vehicles],
            drivers=[DriverSuggestion(**d.__dict__) for d in r.drivers],
            generated_at=r.generated_at,
            cache_hit=r.cache_hit,
        )
```

### 6.6 Test (`test_plan_wizard_endpoint.py`)

- `test_plan_wizard_returns_3_vehicles_3_drivers` — happy path
- `test_plan_wizard_top_n_clamped_to_5` — query param sanity
- `test_plan_wizard_no_eligible_returns_empty_lists` — hard filter empty
- `test_plan_wizard_503_when_flag_off` — feature flag
- `test_plan_wizard_403_for_non_admin` — RBAC

---

## 7. C.4 — Frontend wizard step

### 7.1 UX akışı

```
TripFormModal açılır
  ↓
İlk sekme: "🪄 Akıllı Plan" (default)   ← C.4 yeni adım
  ├─ Tarih + Güzergah seçici  (zaten var, üst kısımdan referans alır)
  ├─ "Önerileri Getir" butonu  → POST /trips/plan-wizard
  ├─ Loading state (3 skeleton kart)
  ├─ Sonuç:
  │    [Hava risk rozeti]   [Güzergah tipi rozeti]
  │    ── Araç adayları (3 kart) ──
  │    [PlanWizardCard]  [PlanWizardCard]  [PlanWizardCard]
  │    ── Şoför adayları (3 kart) ──
  │    [PlanWizardCard]  [PlanWizardCard]  [PlanWizardCard]
  │    "Seç ve Devam" butonu (araç+şoför seçildiyse aktif)
  └─ Sonraki sekme: "📝 Detaylar" (mevcut form, prefill edilmiş)
```

### 7.2 PlanWizardCard.tsx (özet)

```tsx
interface VehicleProps { kind: 'vehicle'; data: VehicleSuggestion }
interface DriverProps { kind: 'driver'; data: DriverSuggestion }

export function PlanWizardCard(props: VehicleProps | DriverProps) {
  const selected = ...
  return (
    <button
      onClick={onSelect}
      className={cn(
        'rounded-modal border p-4 text-left transition-all',
        selected ? 'border-accent bg-accent/5 ring-2 ring-accent/30' : 'border-border hover:border-accent/30',
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-bold">{props.data.plaka /* or ad_soyad */}</span>
        <ScoreBadge value={props.data.score} />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-secondary">
        {props.kind === 'vehicle' ? (
          <>
            <span>Tahmini: {props.data.predicted_liters} L</span>
            <span>Yaş: {props.data.yas}</span>
          </>
        ) : (
          <>
            <span>{routeTypeLabel(props.data.route_type)}: {props.data.deviation_pct}%</span>
            <span>Skor: {(props.data.overall_hybrid*100).toFixed(0)}/100</span>
          </>
        )}
      </div>
      {props.data.cold_start && <ColdStartBadge />}
      <button onClick={() => onOpenXai(props.data)} className="mt-2 text-xs underline">
        Neden bu? (XAI)
      </button>
    </button>
  )
}
```

### 7.3 TripFormModal.tsx değişikliği

- `activeTab` state'i: `'wizard' | 'details' | 'timeline'`
- Yeni sefer (initialData=null) ise default `'wizard'`; edit ise `'details'`.
- Wizard'da seçilen araç/şoför → `setValue('arac_id', ...)` + `setValue('sofor_id', ...)`.

### 7.4 Test

- `PlanWizardStep.test.tsx` — endpoint mock + sonuçların render'ı
- `PlanWizardCard.test.tsx` — selected/cold_start görsel state'leri
- `TripFormModal.test.tsx` (varsa) — wizard'dan details'e geçişte prefill

---

## 8. C.5 — XAI panel "Neden bu araç önerildi?"

### 8.1 UX

Kart üzerindeki "Neden bu?" linki açar → sağdan slide-in panel.

### 8.2 İçerik (sayısal kırılım)

```
🚛 34 ABC 123 önerildi
─────────────────────
Skor: 0.812 / 1.0

Yakıt verimliliği          ██████████  0.95  (40% ağırlık)
Güzergah tarihi            ████████░░  0.80  (25% ağırlık)
Araç sağlığı               ████████░░  0.84  (20% ağırlık)
Müsaitlik                  ███████░░░  0.71  (15% ağırlık)

Sebepler:
✓ Bu güzergahta son 90 günde 4 başarılı sefer
✓ Tahmini tüketim aday seti içinde en düşük
✓ Bakım uyarısı yok
⚠ Son 7 günde 2 sefer (yorgun olabilir)
```

### 8.3 Saf-component

`PlanWizardXaiPanel.tsx` — props olarak `VehicleSuggestion | DriverSuggestion`
alır, ağırlıkları sabit map'ten okur. Backend'den ek istek yok (response'da
zaten alt skor + reasons var).

### 8.4 reasons üretimi (backend `_vehicle_reasons` / `_driver_reasons`)

```python
def _vehicle_reasons(
    fuel_score, route_history_score, vehicle_health_score,
    availability_score, sim_count, age, has_open_alert,
) -> List[str]:
    out: List[str] = []
    if fuel_score > 0.8:
        out.append("Tahmini tüketim aday seti içinde en düşük")
    if sim_count >= 3:
        out.append(f"Bu güzergahta son 90 günde {sim_count} başarılı sefer")
    if age <= 3:
        out.append("Yeni araç (≤ 3 yaş)")
    elif age >= 12:
        out.append("Eski araç — yakıt verimliliği düşebilir")
    if has_open_alert:
        out.append("⚠ Açık bakım uyarısı var")
    if availability_score < 0.3:
        out.append("⚠ Son haftada yoğun kullanım")
    return out[:5]  # üst sınır
```

### 8.5 Test

`PlanWizardXaiPanel.test.tsx` — props ile render, beklenen sebepler.
Backend: `_vehicle_reasons` 5-7 senaryo unit testi.

---

## 9. Konfig + feature flag

`app/config.py`:

```python
# Feature C — Akıllı sefer planlama sihirbazı
TRIP_PLANNER_ENABLED: bool = True
TRIP_PLANNER_CACHE_TTL_S: int = 300   # 5 dk (driver profile + arac shortlist)
```

Flag KAPALI iken endpoint `503` döner — frontend hata mesajı gösterir
("Sihirbaz devre dışı — manuel form kullanın").

---

## 10. Yol haritası (alt görevler ve gating)

| Sıra | Alt görev | Çıktı | Test | Tahmini |
|---|---|---|---|---|
| C.1 | trip_planner.py + schemas + repo eklemeleri | Engine sınıfı, hard filter sorguları | 8 pure unit + 4 integration | 3 sa |
| C.2 | Weather risk wrapper + label mapping | `_weather_impact` + `_risk_label` | 4 unit | 0.5 sa |
| C.3 | `POST /trips/plan-wizard` endpoint | Endpoint + audit | 5 integration | 2 sa |
| C.4 | Frontend wizard step + service + cards | UI + RQ hook | 4 vitest | 3 sa |
| C.5 | XAI panel + `_vehicle_reasons` / `_driver_reasons` | UI panel + backend reasons | 6 unit + 1 vitest | 1.5 sa |

**Toplam tahmin:** ~10 saat. Her alt-görev kendi commit'i.

### Gating

- C.1 → C.2 (independent)
- C.1 + C.2 → C.3 (endpoint engine'i çağırır)
- C.3 → C.4 (frontend backend'e bağımlı)
- C.3 + C.4 → C.5

---

## 11. Riskler ve azaltma

| Risk | Etki | Azaltma |
|---|---|---|
| `predict_consumption()` 10 araç paralel → DB / Groq throttle | Plan 5+ sn sürer | `asyncio.gather` zaten async; Groq çağrısı predict'ten içeride değil. SHORTLIST_SIZE=10 üst sınır |
| `find_similar_trips` aracı filtrelemiyor → araç skoru yanıltıcı olabilir | route_history_score net "aracın" değil "güzergahın" geçmişini gösterir | C.1'de docstring uyarısı, C+ sonraki iterasyonda `arac_id` filtresi eklenir (kapsam dışı) |
| WeatherService geocoding fail | risk_label='unknown', plan çalışmaya devam | Mevcut try/except, nötr fallback |
| Yeni filo (10'dan az araç) → `min` skor ile `max` skor aynı → division by zero | spread=1.0 fallback | `spread = (max - min) or 1.0` |
| Cold-start araç → ensemble physics fallback ↔ aday seti karışık | Skor karşılaştırılabilir kalır (predict_consumption tek API döndürür) | OK by design — physics zaten tutarlı sonuç verir |
| Telegram alarm gibi sessiz fail davranışı **plan endpoint'inde olmamalı** | UI hata göstermez | Engine içinde sadece sub-component fail'leri (örn weather) sessiz; ana akış hata fırlatır |

---

## 12. PII ve güvenlik

- Plan endpoint **şoför adı + plaka** döndürür (admin'in göreceği veri).
- LLM çağrısı **YOK** — bu özellikte tüm karar deterministik scoring.
- `reasons` listesi sadece sayısal/kategorik (PII yok), yani LLM'e
  beslense bile güvenli (gelecek iterasyon için).
- Audit log entry her plan çağrısında: `user_id`, `tarih`, `mesafe_km`,
  `guzergah_id` (kanıt-iz için).

---

## 13. Acceptance criteria

- [ ] `POST /trips/plan-wizard` happy path 200, 3 araç + 3 şoför döner
- [ ] Hard filter boş ise 200 + `vehicles=[]` (404 değil)
- [ ] Feature flag kapalı → 503
- [ ] RBAC: `sefer:write` yetkisiz → 403
- [ ] Audit log entry oluşur (`plan_wizard_used`)
- [ ] Frontend wizard adımı: tarih + güzergah doluyken "Önerileri Getir" aktif
- [ ] Wizard'dan seçim → details adımında `arac_id` + `sofor_id` prefilled
- [ ] XAI panel: alt skor barları + min 3 reason gösterir
- [ ] Tüm yeni unit/vitest testleri yeşil
- [ ] `ruff check`, `mypy`, `npx tsc --noEmit`, `npx vite build` temiz
- [ ] Cold-start senaryosu: yeni araç + boş filo → wizard hata yerine
      "yeni araç" rozetli kart döner

---

## 14. Açık notlar (uygulama sırasında karara bağlanacak)

1. `araclar_bakim_alarm` tablosunun kesin adı — uygulama başında repo
   sorgusunu doğrula. Yoksa `has_open_maintenance_alert=False` ile başla.
2. `Lokasyon.rota_detay` JSONB schema'sı — `route_analysis` nested mi yoksa
   root'ta mı? `_classify` her iki şekli de kabul edecek.
3. `recent_trip_count` ham SQL ile mi yoksa `sefer_repo`'da var olan
   metoda mı? — keşifte kontrol.
4. UI'da "Şoför ad-soyad" plaka kadar prominent gösterilmeli mi? Plan
   karar: evet (admin için anlam taşıyor; PII zaten admin-tarafı).

Bu 4 nokta C.1 başlangıcında doğrulanır, ardından plan kilitlenir.
