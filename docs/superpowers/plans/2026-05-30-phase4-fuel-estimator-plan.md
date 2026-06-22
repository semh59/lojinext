# Phase 4 — SeferFuelEstimator: Derin Plan

> Hedef: Sefer kayıt akışında **tek doğruluk kaynağı** yakıt tahmin servisi. Tüm fiziksel + ML + hava + sürücü + bakım etkenlerini birleştirir. Per-segment detay arkada kaydedilir, UI'da tek sayı + breakdown gösterilir.

**Tarih**: 2026-05-30
**Yazan**: Claude (CTO modu)
**Durum**: planlama — kod yazılmadı
**Önceki fazlar**: Phase 0-3 RouteSimulator + lokasyon ham haritası kuruldu; sefer akışı henüz bağlanmadı.

---

## 0. Executive summary

| | |
|---|---|
| **Sorun** | İki paralel yakıt tahmini akışı var (`predict_consumption` sefer için, `RouteSimulator` segment için), birbirinden habersiz. Sefer ekranı eski sistemi kullanır, yeni segment pipeline'ı sadece UI map için. |
| **Hedef** | Tek `SeferFuelEstimator` servisi. Sefer kayıt akışı buna bağlanır. Output: tahmini_tuketim (UI) + simulation_id (kayıt) + breakdown (debug/şeffaflık). |
| **En kritik karar** | RouteSimulator (physics + segment) **baseline** + multiplicative adjustment factors (driver/weather/age/maintenance/seasonal) + ML ensemble correction (kalibrasyon olunca). Cold start: physics 1.0, ML 0.0 ağırlık. |
| **En kritik bağımlılık** | P4.0 — ML training/inference ayrımı. SeferFuelEstimator yeni "inference-only" predictor'a bağlanır; eğitim ayrı Celery task'a alınır. Aksi halde production'a training kodu inmiş olur. |
| **Scope tahmini** | ~2 hafta (6 task), kalibrasyon Phase 5'e bırakılır |

---

## 1. Mevcut sistem — kod kanıtlarıyla

### 1.1 İki paralel yakıt tahmin akışı

**Akış A (sefer aggregate, eski):**

```
POST /api/v1/trips
  → SeferWriteService.create/update_sefer()
    → app/services/prediction_service.py:predict_consumption()
      → EnsemblePredictorService (app/core/ml/ensemble_service.py)
        → train_for_vehicle / get_predictor (cache LRU 20)
        → EnsembleFuelPredictor.predict() (5 model)
        → input: arac/sofor/sefer aggregate dict
      → output: PredictionResult { tahmini_tuketim, factors_used, ... }
    → seferler.tahmini_tuketim ← yazılır
```

Detay: `app/core/services/sefer_write_service.py:308` ve `:450`, `:618`, `:1217`.

**Akış B (segment, yeni — Phase 0-3):**

```
POST /api/v1/routes/simulate (manuel tetiklemeli, sefer akışında çağrılmaz)
  → RouteSimulator.simulate()
    → MapboxClient.get_segments (Phase 2.3 cache)
    → resample_segments
    → OpenMeteoElevationClient.get_elevations
    → PhysicsBasedFuelPredictor.predict_granular() (sadece physics)
  → route_simulations + route_segments persist
  → response: per-segment + total
```

Detay: `app/core/services/route_simulator.py`, `app/api/v1/endpoints/routes.py:simulate_route`.

### 1.2 EnsemblePredictorService — SRP ihlali

`app/core/ml/ensemble_service.py:17`:

```python
class EnsemblePredictorService:
    # ...
    async def train_for_vehicle(self, arac_id: int) -> Dict:     # line 230
    async def train_general_model(self) -> Dict:                  # line 374
    async def predict_consumption(self, ...) -> Dict:             # line 474
    async def predict_batch(self, requests: List[Dict]) -> List:  # line 601
```

Hem **online inference** hem **offline training** aynı sınıfta. `EnsembleFuelPredictor` core (`ensemble_core.py:85`) de hem `fit()` hem `predict()` içerir. Bu:
- Production deploy'a training kodu indirir
- Inference path'i `xgboost`, `lightgbm` train modüllerini de yükletir
- Test izolasyonu zor
- Yeni "inference-only" SeferFuelEstimator buna bağlanırsa aynı yağ tekrarı

### 1.3 Etken envanteri — hangi sefer akışı kullanıyor

| Etken | Sefer akışı (A) | Segment akışı (B) |
|---|---|---|
| Vehicle specs (drag, motor, ağırlık) | ✅ AracRepository | ✅ PhysicsBasedFuelPredictor default |
| Vehicle age (yıpranma) | ✅ `arac_entity.yas_faktoru` | ❌ — wrapper'da yok |
| Maintenance factor | ✅ kısmen (`predict_consumption.maintenance_factor`) | ❌ |
| Yük (ton) | ✅ | ✅ |
| Driver score | ✅ `sofor_katsayi = 1 - filo_karsilastirma/100 × 0.1` | ❌ |
| Mesafe / yokuş aggregate | ✅ Lokasyon cached fields | ✅ Mapbox+Open-Meteo canlı per-segment |
| Per-segment trafik | ❌ | ✅ Mapbox driving-traffic |
| Per-segment grade | ❌ aggregate ascent_m | ✅ Open-Meteo SRTM |
| Hava (gerçek sıcaklık/rüzgar/yağış) | ❌ **YOK** | ❌ **YOK** |
| Hava mevsimsel | ✅ `WeatherService.get_seasonal_factor` (sabit faktör) | ❌ |
| ML ensemble (LightGBM/XGB/GB/RF) | ✅ aggregate input ile | ❌ segment-mode'da kalibrasyonsuz |

### 1.4 WeatherService — minimum, dış API YOK

`app/core/services/weather_service.py:232`:

```python
def get_seasonal_factor(self, target_date) -> float:
    month = target.month
    if month in (12, 1, 2):   return 1.10  # kış
    if month in (3, 4, 10, 11): return 1.03  # geçiş
    if month in (6, 7, 8):    return 1.05   # yaz
    return 1.0                              # ilkbahar
```

Sınıfın geri kalanı (`fetch_weather_at`, `get_temperature` vs.) **yok**. Hava endişesini çözmek için **gerçek API entegrasyonu gerekli**.

---

## 2. Hedef mimari

### 2.1 Servis bölünmesi (SRP'ye uygun)

```
app/core/ml/
├── predictors/                       ← Runtime, inference-only
│   ├── __init__.py
│   ├── ensemble_predictor.py         EnsemblePredictor.predict() (saf math)
│   ├── physics_predictor.py          PhysicsBasedFuelPredictor (mevcut, hareket)
│   └── model_loader.py               load_model(path) → ready
│
├── training/                          ← Offline, batch
│   ├── __init__.py
│   ├── trainer.py                    Trainer.run(arac_id) → .pkl
│   ├── feature_pipeline.py           sefer rows → feature matrix
│   ├── data_loader.py                DB → historical seferler
│   └── scheduler_task.py             Celery beat (haftalık)
│
└── models/                            ← Disk artifact (mevcut, gitignore'lu)
    └── {arac_id}_ensemble.pkl
```

Inference path **sadece** `predictors/` import eder. Training path **sadece** `training/` import eder. İki yön çift import etmez (mypy guard).

### 2.2 SeferFuelEstimator pipeline (P4.3)

```
SeferFuelEstimator.predict(input: SeferFuelInput) → SeferFuelEstimate
  │
  ├─ Step 1: Resource Loading (UoW)
  │     vehicle = arac_repo.get(arac_id)           # spec + yas
  │     driver  = sofor_repo.get(sofor_id)         # fuel_score
  │     dorse   = dorse_repo.get(dorse_id)         # opsiyonel
  │
  ├─ Step 2: Route Resolution
  │     if lokasyon_id:
  │       lok = lokasyon_repo.get(id)
  │       (cikis/varis lat-lon) ← lokasyondan
  │     else:
  │       ad-hoc koord input'tan
  │
  ├─ Step 3: PARALLEL FETCH (asyncio.gather)
  │     mapbox_task = mapbox.get_segments(...)        ← 24h cache
  │     elev_task   = open_meteo.get_elevations(...)  ← 30g cache
  │     weather_task = weather.get_forecast(...)      ← 1h cache (P4.1 YENİ)
  │
  ├─ Step 4: PHYSICS BASELINE (segment-mode)
  │     segments = process(mapbox, elev, weather)     ← grade hesabı
  │     baseline_l_100 = PhysicsBasedFuelPredictor.predict_granular(
  │       segments, vehicle_specs, load_ton, arac_yasi
  │     )
  │
  ├─ Step 5: ADJUSTMENT FACTORS (multiplicative)
  │     factors = AdjustmentFactors.compute(
  │       driver=driver, vehicle=vehicle, weather=weather, target_date=...
  │     )
  │     # factors = {driver, age, maintenance, weather_temp, weather_wind,
  │     #            weather_rain, seasonal}
  │     adjusted_l_100 = baseline_l_100 × prod(factors.values())
  │
  ├─ Step 6: ML CORRECTION (kalibrasyon sonrası)
  │     try:
  │       ml_estimate = ensemble_predictor.predict(features)
  │       physics_weight = vehicle.physics_weight or 0.8  # cold start 1.0
  │       final = physics_weight × adjusted_l_100
  │             + (1-physics_weight) × ml_estimate
  │     except ModelNotTrained:
  │       final = adjusted_l_100   # fallback
  │
  └─ Step 7: PERSIST + RETURN
        sim = RouteSimulation(
          lokasyon_id, kullanici_id, ton, arac_yasi,
          total_l, total_km, avg_l_per_100km=final,
          ...,
          meta={"breakdown": factors_dict}
        )
        per-segment route_segments insert
        db.commit()

        return SeferFuelEstimate(
          tahmini_tuketim=final,
          simulation_id=sim.id,
          breakdown={
            "physics_baseline": 24.1,
            "factors": {...},
            "ml_correction_weight": 0.0,
            "final": 28.5,
          }
        )
```

### 2.3 SeferFuelInput / SeferFuelEstimate (dataclass)

```python
@dataclass
class SeferFuelInput:
    arac_id: int
    sofor_id: int
    ton: float
    target_date: date
    bos_sefer: bool = False
    # Route — biri zorunlu
    lokasyon_id: Optional[int] = None
    cikis_lat: Optional[float] = None
    cikis_lon: Optional[float] = None
    varis_lat: Optional[float] = None
    varis_lon: Optional[float] = None
    # Opsiyonel
    dorse_id: Optional[int] = None
    segment_length_m: int = 500

@dataclass
class FactorBreakdown:
    physics_baseline: float          # L/100km
    driver: float                    # multiplier
    vehicle_age: float
    maintenance: float
    weather_temperature: float
    weather_wind: float
    weather_precipitation: float
    seasonal: float
    ml_correction_weight: float      # 0.0 cold start
    final: float                     # L/100km

@dataclass
class SeferFuelEstimate:
    tahmini_tuketim: float           # final L/100km
    total_l: float                   # × mesafe/100
    distance_km: float
    duration_min: float
    simulation_id: int
    breakdown: FactorBreakdown
    elevation_coverage_pct: float
    raw_segment_count: int
    resampled_segment_count: int
```

---

## 3. Adjustment factors — matematik + literatür

### 3.1 Driver factor

**Mantık**: Sürücü skoru 0-100 (filo karşılaştırma); yüksek skor → daha az yakıt.

```
filo_karsilastirma = sofor.fuel_score  # -50..+50 (negatif = filodan kötü)
driver_factor = 1.0 - (filo_karsilastirma / 100) × DRIVER_IMPACT

DRIVER_IMPACT = 0.10  # ±10% spread
```

Mevcut `ensemble_service.py:288` formülü aynısı: `1.0 - (driver.filo_karsilastirma / 100) * 0.1`.

**Sınırlama**: `max(0.85, min(1.15, factor))` — sıra dışı sürücü kayıtlarına karşı koruma.

**Literatür**: SAE 2014-01-2347 sürücü davranışının %5-15 yakıt değişimi (TIR class 8). Bizim ±10% bandı orta.

### 3.2 Vehicle age factor

```
arac_yasi = (today - arac.uretim_tarihi).years
# Year-over-year degradation
if arac_yasi <= 3:   age_factor = 1.00
elif arac_yasi <= 6: age_factor = 1.04
elif arac_yasi <= 10: age_factor = 1.08
else:                 age_factor = 1.12   # max %12 yıpranma
```

Mevcut Arac entity `yas_faktoru` property zaten benzer formül. Yeniden kullanılacak.

**Literatür**: VECTO study HDD trucks 1-2% per year degradation, 10 yıl sonra plateau ~%15.

### 3.3 Maintenance factor

```
ay_since_service = (today - arac.last_maintenance).months
if ay_since_service <= 6:    maint_factor = 1.00
elif ay_since_service <= 12: maint_factor = 1.02   # %2 ek
elif ay_since_service <= 18: maint_factor = 1.05
else:                         maint_factor = 1.08
```

Tire pressure / air filter / oil change combined effect literatürde %5-10 spread.

### 3.4 Weather factors

Bu **en zengin yenilik**. Open-Meteo /forecast endpoint'inden:

#### 3.4.1 Sıcaklık

```
temp_c = weather.temperature_2m         # current
optimal = 20.0
delta = abs(temp_c - optimal)
# 0°C'da +5%, 40°C'da +10% (AC), -10°C'da +12% (cold start + warmup)
if temp_c < 5:    temp_factor = 1.0 + (5 - temp_c) × 0.012
elif temp_c > 28: temp_factor = 1.0 + (temp_c - 28) × 0.008
else:              temp_factor = 1.0

clamp(0.95, 1.20)
```

**Literatür**: EPA cold weather penalty %12 (motorin), AC use %5-10 (yaz şehir içi).

#### 3.4.2 Rüzgar (headwind/tailwind)

Bu en karmaşık çünkü **segment yönüne göre** hesaplanmalı:

```
# Her segment için:
segment_bearing = bearing(prev_coord, next_coord)  # 0-360°
wind_bearing = weather.wind_direction_10m          # 0-360° (geldiği yön)
relative = (wind_bearing - segment_bearing) % 360

if relative < 45 or relative > 315:    # tailwind
    wind_factor_seg = 1.0 - wind_speed × 0.002
elif 135 < relative < 225:              # headwind
    wind_factor_seg = 1.0 + wind_speed × 0.004
else:                                    # crosswind
    wind_factor_seg = 1.0 + wind_speed × 0.001

clamp(0.92, 1.15)
```

Route-level: weighted avg by segment length.

**Literatür**: 30 km/h headwind ~%8-12 ek tüketim (HDD aero). 0.004 × 30 = 12% denkleştirmesi yaklaşık doğru.

#### 3.4.3 Yağış

```
precip_mm = weather.precipitation
if precip_mm < 0.5:    rain_factor = 1.0
elif precip_mm < 5:    rain_factor = 1.03  # hafif yağmur, dikkat
elif precip_mm < 20:   rain_factor = 1.06  # orta
else:                   rain_factor = 1.10   # şiddetli

# Kar (snow_depth varsa)
if weather.snowfall > 0:
    rain_factor = max(rain_factor, 1.12)
```

### 3.5 Seasonal factor (deterministik, mevcut)

`WeatherService.get_seasonal_factor()` aynen kullanılır — gerçek hava ile çakışırsa **min** alınır (çift sayma önler).

```
final_weather = max(temp_factor, seasonal_factor) × wind_factor × rain_factor
```

### 3.6 Tüm faktörlerin birleşimi

```
adjustment_total = (
    driver_factor
    × age_factor
    × maintenance_factor
    × temp_factor
    × wind_factor
    × rain_factor
)
# seasonal artık temp_factor içinde sayılıyor (çift sayma önleme)
# Toplam clamp:
adjustment_total = clamp(0.7, 1.5)  # üst-alt sınır
```

Cold start: tüm faktörler 1.0 ise `adjustment_total = 1.0` → `final = baseline`.

---

## 4. P4.0 — ML training/inference ayrımı (detaylı)

### 4.1 Hedef yapı

```
app/core/ml/predictors/
├── ensemble_predictor.py
│     class EnsemblePredictor:
│         __init__(model_path: str)
│             self.physics = PhysicsBasedFuelPredictor()
│             self._lgb = joblib.load(...) if exists
│             self._xgb = ...
│             self._gb = ...
│             self._rf = ...
│             self._weights = self._load_weights(...)
│         def predict(features: dict) -> PredictionResult:
│             # Sadece predict logic, fit/save/load YOK
│             physics_pred = self.physics.predict(features)
│             ml_preds = {m: m.predict(...) for m in [lgb, xgb, gb, rf] if m}
│             return weighted_blend(physics_pred, ml_preds, self._weights)
│
└── physics_predictor.py  ← mevcut PhysicsBasedFuelPredictor (taşınır)


app/core/ml/training/
├── trainer.py
│     class Trainer:
│         def run(arac_id: int) -> dict:
│             data = DataLoader.fetch_for_vehicle(arac_id)
│             X, y = FeaturePipeline.transform(data)
│             models = train_all_models(X, y)
│             weights = compute_r2_weights(models, X, y)
│             save_model_bundle(arac_id, models, weights)
│
├── feature_pipeline.py   ← input prep (sefer dict → np array)
├── data_loader.py        ← DB → DataFrame
└── scheduler_task.py     ← Celery beat: haftalık retrain all vehicles
```

### 4.2 Geçiş stratejisi

1. `ensemble_core.EnsembleFuelPredictor.predict()` → `predictors/ensemble_predictor.py` (saf inference, sadece predict)
2. `ensemble_core.EnsembleFuelPredictor.fit()` + `save_model()` → `training/trainer.py`
3. `ensemble_service.EnsemblePredictorService.train_for_vehicle()` → `training/scheduler_task.py`
4. `ensemble_service.EnsemblePredictorService.predict_consumption()` → SeferFuelEstimator.predict()
5. Backward compat: `get_ensemble_service()` → bir adapter (eski API çağırılırsa yeni service'e yönlendirir, deprecation warning)

### 4.3 Test düzeni

- `tests/unit/test_predictors_inference_only.py` — predictors/ test edilir, training modülleri import EDİLMEZ (smoke check)
- `tests/unit/test_training_pipeline.py` — Trainer test, küçük synthetic dataset
- `tests/integration/test_train_save_load_predict_cycle.py` — full E2E (train → diskten yükle → predict)

---

## 5. P4.1 — Open-Meteo Weather Forecast Client

### 5.1 API

```
GET https://api.open-meteo.com/v1/forecast
   ?latitude=...&longitude=...
   &current=temperature_2m,wind_speed_10m,wind_direction_10m,precipitation
   &hourly=temperature_2m,wind_speed_10m,wind_direction_10m,precipitation,snowfall
   &forecast_days=2
```

### 5.2 Client implementasyonu

```python
# app/infrastructure/weather/open_meteo_forecast_client.py

@dataclass
class WeatherSample:
    temperature_2m: float | None
    wind_speed_10m: float | None       # km/h
    wind_direction_10m: float | None   # 0-360 (geldiği yön)
    precipitation: float | None        # mm/h
    snowfall: float | None             # cm/h

class OpenMeteoForecastClient:
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_forecast_at(
        self, coord: Tuple[float, float], when: datetime
    ) -> Optional[WeatherSample]:
        # 1-hour cache key
        key = f"weather:{lon:.2f}:{lat:.2f}:{when.strftime('%Y%m%d%H')}"
        # ...

    async def get_route_weather_samples(
        self, midpoints: List[Tuple[float, float]], when: datetime
    ) -> List[Optional[WeatherSample]]:
        # batch (Open-Meteo supports multiple lat/lon)
        # tek API çağrısı, N nokta
```

### 5.3 Cache stratejisi

| Parametre | Değer | Sebep |
|---|---|---|
| Coord precision | 2 decimal (~1.1 km) | Hava 1km'de çok değişmez |
| Time precision | Saat (`%Y%m%d%H`) | Saatlik veri Open-Meteo'da var |
| TTL | 1 saat | Hava saatlik güncelleniyor |
| Batch | Tek istek N koord | API destekliyor (virgülle ayrı) |

### 5.4 Test stratejisi

- Empty input → empty
- Cache hit → HTTP yok
- Cache miss → HTTP + write
- Partial cache
- 500 error → cached only, miss → None
- Real smoke (env-gated): canlı API ±2°C tolerans

---

## 6. P4.4 — Sefer akışı entegrasyonu

### 6.1 Mevcut çağrı yerleri

`sefer_write_service.py`:
- Line 308: `create_sefer` ana akış
- Line 450: `update_sefer` re-predict
- Line 618: `return_trip` (dönüş seferi)
- Line 1217: `bulk_import` (Excel)

### 6.2 Geçiş planı

```python
# Eski:
prediction = await pred_service.predict_consumption(
    arac_id=..., mesafe_km=..., ton=..., ascent_m=..., descent_m=...,
    flat_distance_km=..., sofor_id=..., target_date=..., bos_sefer=...,
    dorse_id=..., route_analysis=...
)
tahmini_tuketim = prediction.get("tahmini_tuketim")

# Yeni:
estimator = get_sefer_fuel_estimator()
estimate = await estimator.predict(SeferFuelInput(
    arac_id=arac_id, sofor_id=sofor_id, ton=ton,
    target_date=tarih, bos_sefer=bos_sefer,
    dorse_id=dorse_id, lokasyon_id=lokasyon_id,
    cikis_lat=..., cikis_lon=..., varis_lat=..., varis_lon=...,
))
tahmini_tuketim = estimate.tahmini_tuketim
route_simulation_id = estimate.simulation_id
```

### 6.3 Migration 0020

```python
op.add_column(
    "seferler",
    sa.Column(
        "route_simulation_id",
        sa.BigInteger,
        sa.ForeignKey("route_simulations.id", ondelete="SET NULL"),
        nullable=True,
    ),
)
op.create_index(
    "ix_seferler_route_simulation_id", "seferler", ["route_simulation_id"]
)
```

### 6.4 Bulk import optimizasyonu

Excel ile 100 sefer geliyorsa:
- 100 SeferFuelEstimator çağrısı = 100 Mapbox+Open-Meteo (cache hit oranı %95+)
- Aynı lokasyon birden fazla seferde varsa: lokasyon_id ile group by, tek Mapbox response paylaşılır
- Bulk path için: `estimator.predict_batch(inputs: List[SeferFuelInput])` — daha verimli

---

## 7. Faz task'ları (sıra ve süre)

```
P4.0  ML training/inference ayrımı           4-5 gün
  ├─ predictors/ + training/ ayrımı
  ├─ Adapter (backward compat)
  ├─ Celery task: weekly retrain
  └─ Tests: inference-only smoke + train-cycle

P4.1  Open-Meteo Weather Forecast client     2 gün
  ├─ OpenMeteoForecastClient + cache
  ├─ batch route weather
  └─ 8+ unit + 1 live smoke

P4.2  AdjustmentFactors hesap modülü         2 gün
  ├─ DriverFactor / AgeFactor / MaintenanceFactor / WeatherFactor*3
  ├─ Clamp + sanity guards
  └─ 12+ unit (her faktör + uç senaryo)

P4.3  SeferFuelEstimator orkestrasyon       3-4 gün
  ├─ SeferFuelInput / SeferFuelEstimate dataclass
  ├─ Resource Loading + Parallel Fetch + Physics + Factors + Persist
  ├─ predict() + predict_batch()
  └─ 10+ unit (mock'lu pipeline)

P4.4  seferler.route_simulation_id FK + entegrasyon  2-3 gün
  ├─ Alembic 0020
  ├─ SeferWriteService 4 çağrı yerini yeni servise yönlendir
  ├─ Eski predict_consumption deprecate (log warning)
  └─ Mevcut integration testler yeşil kalmalı

P4.5  Endpoint + frontend breakdown UI       2 gün
  ├─ POST /api/v1/sefer-tahmin (yeni endpoint, sefer kayıt formundan ayrı çağrılabilir)
  ├─ Response'ta breakdown göster
  └─ Frontend: sefer ekranında "Tahmin nasıl hesaplandı?" tooltip

TOPLAM: 15-18 iş günü (~3 hafta)
```

---

## 8. Riskler ve hafifletme

| Risk | Etki | Hafifletme |
|---|---|---|
| **Ensemble modeli segment-mode'da kalibrasyonsuz** | Yanlış correction | Cold start: physics_weight=1.0, ML=0.0. Pilot veri sonrası yeniden kalibre (Phase 5). |
| **Open-Meteo Forecast API rate limit** | 10k req/gün free | 1h cache → günde max 24 farklı saat × N rota = makul. Pilot ölçüm sonrası karar. |
| **Hava verisi yokken degrade** | Tahmin yanlış | Weather None → tüm hava faktörleri 1.0 (no-op). Seasonal factor (deterministic) yine çalışır. |
| **Migration 0020 sonrası eski sefer kayıtlarında route_simulation_id NULL** | Tamamen normal | Bekleniyor — kullanıcı yeni sefer açtığında dolar. UI NULL'a tolerans gösterir ("simülasyon yok"). |
| **Excel bulk import maliyeti** | 100 sefer = 100 API çağrısı | Group by lokasyon_id, cache %95+ hit. Worst case 10s/sefer. |
| **SeferFuelEstimator complexity (7 step)** | Test zor, debug zor | Her step ayrı method, ayrı test. Breakdown dict response'ta — UI debug kolay. |
| **Backward compat predict_consumption** | Mevcut endpoint'ler kırılırsa | Adapter pattern: eski sınıf get_ensemble_service() yeni servise yönlendirir; deprecation warning. |
| **ML predictor diskten yükleme süresi (50-100MB)** | Cold start yavaş | LRU cache 20 predictor (mevcut). İlk yükleme arka plan warmup task'ı (uvicorn startup). |
| **Hava API'sinin yanlış lokasyona vermesi (deniz/dağ)** | Yanlış katsayı | Coord rounding 2 decimal makul. Edge case: clamp uygulanır. |

---

## 9. Açık sorular — kullanıcıya / dış kararlar

1. **Driver impact %10 doğru mu?** Pilot veri olmadığı için kabaca. Phase 5 kalibrasyonda yenilenir.
2. **Bulk import (Excel) için segment simülasyonu maliyetli mi?** 100 sefer × ortalama 5 sn → 8 dk. Bu kullanıcı için OK mi?
3. **Hava forecast geçmiş tarihler için işe yarar mı?** Open-Meteo /forecast 2 günlük; geçmiş için /archive endpoint var ama farklı API. Geçmiş seferlere için yeniden çağırılırsa archive client gerek.
4. **Weather precision 2 decimal (~1.1 km) yeterli mi yoksa 3 (110m)?** 2 yeterli görünüyor; 3 cache miss oranını 100x artırır.
5. **Yağış mm/h cinsinden mi yoksa toplam mı?** Open-Meteo dakika başına raporluyor; saatlik toplama göre faktör hesaplanmalı.
6. **ML eğitim Celery beat saatleri?** Önerim: Pazar 03:00 (düşük trafik); araç başına ~2-5 sn × 100 araç = 5-10 dk total.

---

## 10. Phase 4 sonrası — Phase 5+ önizleme

- **Phase 5: Pilot kalibrasyon** — 4 hafta gerçek sefer + yakıt fişi → physics_baseline ve ML correction katsayıları yeniden fit. Tüm faktör parametreleri (DRIVER_IMPACT 0.10, age year %4, etc.) gerçekleştir.
- **Phase 6: Frontend mapbox-gl-js sayfa** — `/routes/simulator` interaktif harita, segment heatmap, breakdown panel.
- **Phase 7: AVL/Telemetri entegrasyonu** — gerçek GPS trace + Mapbox Map Matching + LSTM-Conv DL modeli (AVL provider seçimi yapıldıktan sonra).

---

## 11. Sources

- Plan: docs/superpowers/plans/2026-05-29-route-segment-simulation-plan.md (Phase 0-3)
- Mevcut kod: app/core/ml/ensemble_service.py, app/core/services/sefer_write_service.py, app/services/prediction_service.py
- Open-Meteo Forecast API: https://open-meteo.com/en/docs
- VECTO (HDD truck efficiency): https://transport.ec.europa.eu/transport-modes/road/vehicles-categorisation-and-co2-emissions/vecto_en
- EPA cold weather impact: https://www.fueleconomy.gov/feg/coldweather.shtml

---

**Bu plan canlı belge değil — kalıcı artifact**. Implementation başlarken bu dosya referans alınır. Phase 4 fazları (P4.0-P4.5) ayrı PR'larda. Plan değişirse `-v2.md` ile yeni dosya açılır.

---

## 12. D1-D6 Derin Kontrol Sonuçları (2026-05-30)

İlk plan §1-§11'deki **6 kritik varsayım** kod tabanı + canlı API + literatür ile test edildi. Sonuç: **3 büyük plan revizyonu**, scope %30-40 düşüşü.

### 12.1 P4.D1 — ML training/inference coupling gerçek hâli

**Bulgu**: `EnsembleFuelPredictor` (ensemble_core.py:85, 1290 satır) `fit()` ve `predict()` aynı sınıfta. Ortak state: `gb_model, rf_model, xgb_model, lgb_model, scaler, weights, is_trained, physics_weight`. `predict()` sadece **okur**; mutation yok. Modül-seviyesi imports (xgboost, lightgbm, sklearn) **ZORUNLU** — `from ensemble_core import EnsembleFuelPredictor` derken tümü yüklenir (~200MB).

**Revize**: Plan §4.1'de "sınıfı 2'ye böl" stratejisi yanlış kapsam. 1300 satır class'ı bölmek = pickle backward-compat felaketi + mevcut test'ler kırılır. **Doğru yaklaşım**: wrapper + lazy import + klasör semantiği:

```
app/core/ml/predictors/ensemble_predictor.py    # YENİ ~80 satır
    class EnsemblePredictor:
        def __init__(self, model_path):
            from app.core.ml.ensemble_core import EnsembleFuelPredictor  # lazy
            self._inner = EnsembleFuelPredictor()
            self._inner.load_model(model_path)
        async def predict(features) -> PredictionResult:
            return self._inner.predict(features)
        # fit/save/train metodları YOK (type-level enforcement)

app/core/ml/training/trainer.py                  # YENİ ~150 satır
    class Trainer:
        async def train(arac_id) -> dict:
            # mevcut train_for_vehicle taşınır
            ...
            predictor.save_model(...)
```

EnsembleFuelPredictor **aynen kalır**. Yeni katmanlar ona delegate eder. Mevcut testler etkilenmez.

### 12.2 P4.D2 — predict_consumption faktör envanteri

**Bulgu**: `predict_consumption` (prediction_service.py:556-750) zaten **5 ana faktörü** içeriyor:

| Faktör | Mevcut formül / kaynak |
|---|---|
| Driver | `1.0 + (1.0 - s_score) × 0.2` clamp(0.8, 1.2). `sofor.score` bandı **0.1-2.0** (models.py:214 yorum) |
| Vehicle age | `Arac.yas_faktoru` property |
| Maintenance | `compute_maintenance_factor(HealthInput)` — PERIYODIK age + ARIZA + ACIL → 0.95-1.25 clamp. Feature flag `MAINTENANCE_FACTOR_ENABLED` |
| Weather seasonal | `WeatherService.get_seasonal_factor(target_date)` — month → 1.0/1.03/1.05/1.10 |
| Ramp | `1.0 + (ramp_pct/100) × 0.2` (ascent==0 ise) |

**Revize**: Plan §3'te "5 yeni faktör formülü yaz" hatalı. Bunların 4'ü zaten var. P4.2'de **sadece 3 yeni hava faktörü** (temp/wind/rain) + **birleştirme helper'ı** kalır:

```python
# adjustment_factors.py - yeni içerik:
def weather_temperature_factor(temp_c: float) -> float: ...     # YENİ
def weather_wind_factor(wind_kmh, segment_bearing, wind_bearing): ...  # YENİ
def weather_precipitation_factor(precip_mm, snowfall_cm=0): ...  # YENİ
def combine_factors(driver, age, maintenance, weather_*, seasonal): ...  # birleştirme

# Driver/age/maintenance: predict_consumption mevcut formüllerini reuse
```

**Plan §3.1 sofor_score bandı düzeltme**: 0-100 değil **0.1-2.0**. Formül `1.0 + (1.0 - s_score) × 0.2`.

### 12.3 P4.D3 — Sefer akışı çağrı yerleri

**4 çağrı yeri**:

| Yer | Akış | Özel |
|---|---|---|
| `_predict_outbound:402` | Create gidiş | Weather impact + **2.5s timeout fallback** |
| `_repredikt_for_update:226` | Update field değişimi | Sadece "değişti mi" sonrası |
| `_create_return_trip:618` | Dönüş seferi | bos_sefer=True olabilir |
| `bulk_add_sefer:1217` | Excel import | **`skip_prediction = len > 20`** |

**Korunması gereken side effects**:
- `_extract_prediction_values` / `_build_prediction_quality_flags` / `_build_prediction_route_analysis`
- Audit log (sefer commit sonrası)
- Event bus `SeferCreated` (commit sonrası)
- 2.5s timeout fallback (sefer tahmin OLMADAN kaydedilebilir)

### 12.4 P4.D3 EK BULGU — WeatherService zaten gelişmiş!

**En kritik bulgu**: Plan §5'te "Open-Meteo Weather Forecast client yaz" iddiası **yanlış**. Mevcut yapı:

```
app/services/external_service.py:23
    OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"  ← ZATEN VAR
    async def get_weather_forecast(lat, lon) → daily forecast

app/core/services/weather_service.py
    async def get_trip_impact_analysis(cikis/varis):
        # 2 nokta weather + impact_factor hesabı
    def calculate_weather_fuel_impact(temp, precip, wind):
        # temp <0 +8%, <10 +4%, >30 +3%
        # precip >20mm +8%, >10mm +5%, >2mm +2%
        # wind >threshold +15%, >40 ...
```

**Mevcut eksiklikler** (P4.1'in YENİ yapacağı):

| Eksik | Düzeltme |
|---|---|
| **Daily aggregate** (max temp/günlük) | `hourly=temperature_2m,...&forecast_hours=N` query ekle |
| **In-memory cache** (process restart'ta kayıp) | Redis CacheManager (Phase 1.1 pattern) |
| **Sadece 2 nokta** | `get_route_weather_samples(midpoints)` batch method |
| **Wind direction yok** | `wind_direction_10m` field ekle |
| **Archive endpoint kullanılmıyor** | Geçmiş sefer için archive-api.open-meteo.com |

**Revize**: P4.1 = yeni client değil, **mevcut WeatherService genişletme** (~80 satır + cache geçişi).

### 12.5 P4.D4 — Open-Meteo canlı API teyit

3 koordinat (İstanbul, Ankara, Uludağ) ile canlı probe:

- ✅ Batch endpoint (virgülle ayrı lat/lon) → list response
- ✅ `current` (anlık) fields: temperature_2m, wind_speed_10m, **wind_direction_10m**, precipitation, snowfall
- ✅ `hourly` 12 saat tek istekte
- ✅ Türkiye coverage: İST 21.2°C, ANK 16.6°C, Uludağ 7.7°C (dağ doğru)
- ✅ `archive-api.open-meteo.com` geçmiş hava (saatlik, 2 günlük yetiyor)
- ✅ Rate limit 10k/gün free → Türkiye yeterli

API'nin **yeterliliği teyit** edildi.

### 12.6 P4.D5 — Literatür ile formül kalibrasyonu

| Formül | Plan | Literatür | Karar |
|---|---|---|---|
| Driver bandı ± | %10 | HDV %15-29 | ✅ mevcut clamp(0.8, 1.2) = %20 yeterli |
| Headwind 10 km/h | **+%4** (×0.004) | **+%10** (drag ²×) | ⚠️ **Coefficient 0.004 → 0.010 REVİZE** |
| Cold -10°C | +%18 (×0.012) | %15-24 | ✅ uyumlu |
| Hot 40°C | +%9.6 (×0.008) | %5-10 (AC) | ✅ uyumlu |
| Wind clamp | (0.92, 1.15) | %30+ fırtına olabilir | ⚠️ **(0.85, 1.30) genişlet** |
| Yağış >20mm | +%10 | EPA %7-35 winter poor | ✅ alt sınırda |

**Net düzeltme**: P4.2 `wind_factor` katsayısı 0.010 (10 km/h'de +%10), clamp (0.85, 1.30).

### 12.7 P4.D6 — Bulk import maliyet analizi

| Strateji | 100 sefer (warm) | Veri değeri |
|---|---|---|
| **A) Skip (>20)** | 0 | Geçmiş veri import — gerçek tüketim zaten kayıtlı, tahmin gereksiz |
| **B) Group by lokasyon** | ~5 sn | Aynı güzergah için paylaşılır |
| **C) Full** | ~40 sn (cache hit) | Detaylı tahmin |

**Karar**: `BULK_FUEL_ESTIMATE: skip\|share\|full` feature flag, default `skip` (mevcut davranışı koru). Memory profili: 100 × 135 KB = 13.5 MB → streaming gereksiz.

### 12.8 Net scope karşılaştırması

| Task | İlk plan | Revize | Sebep |
|---|---|---|---|
| **P4.0** ML ayrım | 4-5 gün (sınıf bölme) | **2-3 gün** (wrapper) | D1 — kapsam yanlış |
| **P4.1** Weather client | 2 gün (yeni) | **1 gün** (genişletme) | D3 — WeatherService zaten var |
| **P4.2** Adj factors | 2 gün (5 faktör) | **1 gün** (3 faktör + helper) | D2 — 4 faktör zaten var |
| **P4.3** Estimator | 3-4 gün | **2-3 gün** | reuse ile basit |
| **P4.4** Sefer akışı + bulk flag | 2-3 gün | 2 gün | aynı |
| **P4.5** Endpoint + UI | 2 gün | 2 gün | aynı |
| **TOPLAM** | ~3 hafta | **~2 hafta** | %35 azalma |

### 12.9 Revize task öncelikleri

```
P4.0  EnsemblePredictor wrapper + Trainer ayrımı       (2-3 gün)
  ├─ predictors/ensemble_predictor.py (lazy import)
  ├─ training/trainer.py (mevcut train_for_vehicle taşınır)
  ├─ training/scheduler_task.py (Celery beat haftalık)
  └─ Backward-compat: get_ensemble_service adapter → deprecation warning

P4.1  WeatherService genişletme                         (1 gün)
  ├─ ExternalService.get_weather_forecast: hourly query param ekle
  ├─ ExternalService.get_weather_archive: yeni (archive-api endpoint)
  ├─ WeatherService.get_route_weather_samples(midpoints): batch method
  ├─ wind_direction_10m field ekle
  └─ In-memory cache → CacheManager (Redis, 1h TTL)

P4.2  Adjustment factors                                (1 gün)
  ├─ weather_temperature_factor (literatür uyumlu — mevcut formül kalır)
  ├─ weather_wind_factor (coefficient 0.010, headwind/tailwind ayrımı,
  │    clamp(0.85, 1.30))
  ├─ weather_precipitation_factor (snow dahil)
  └─ combine_factors helper (çift sayma kontrolü: max(temp, seasonal))

P4.3  SeferFuelEstimator                                (2-3 gün)
  ├─ SeferFuelInput / SeferFuelEstimate dataclass
  ├─ predict(input): pipeline orchestration (UoW + parallel fetch + factors)
  ├─ predict_batch(inputs, strategy="skip"|"share"|"full")
  └─ Reuse: predict_consumption faktör formülleri, RouteSimulator pipeline

P4.4  seferler.route_simulation_id + sefer akışı entegrasyon  (2 gün)
  ├─ Alembic 0020
  ├─ 4 çağrı yerini SeferFuelEstimator'a yönlendir
  ├─ Side effect koruma (event bus, audit, 2.5s timeout)
  ├─ Eski predict_consumption deprecate (warning, mevcut testler yeşil)
  └─ Bulk: BULK_FUEL_ESTIMATE flag

P4.5  Endpoint + UI breakdown                            (2 gün)
  ├─ POST /api/v1/sefer-tahmin
  ├─ Frontend: breakdown tooltip (physics + factors + final)
  └─ Integration test
```

**Plan v1.1** kabul edilebilir, kod yazılabilir.
