# Route Segment Simulation — Derin Plan + Araştırma

> **Hedef artifact**: Kullanıcı 2026-05-28'de istedi, koordinat çiftinden 500m bazlı simülasyon — "500m gitti bu yolda tır 90 km/h gider, sonra %3 eğimde 60 km/h düşer" tipi ham segment verisi. Bu dosya plan + araştırma sonuçlarını kalıcı kayıt eder; uygulama ayrı bir epic.

**Tarih**: 2026-05-29
**Yazan**: Claude (CTO modu, oturum)
**Durum**: planlama / araştırma — kod yazılmadı
**Provider tercihi (kullanıcı)**: Mapbox (ORS değil)

---

## 0. Executive summary

| | |
|---|---|
| **Kullanıcı vizyonu** | İki koordinat → route'un her 500m'i için (eğim, yol kategorisi, hız sınırı, gerçek trafik hızı, simüle yakıt) seviyesinde **ham veri** üretip frontend'de polyline + heatmap + hız profili göstermek |
| **Mevcut sistem** | Sefer-aggregate ML (`predict_consumption()` 6 scalar bucket alıp tek L/100km döner). Per-segment veri Mapbox'tan **alınıyor ama atılıyor** |
| **En kritik bulgu** | **Tek API yetmez**. Mapbox Directions API hız + traffic veriyor, **elevation/gradient VERMİYOR**. Hybrid: Directions + Terrain-DEM (Tilequery) gerek |
| **En kritik kod bug'ı** | `mapbox_client.py:146` `annotation.get("road_class", [])` — bu annotation Mapbox response'unda YOK, response'da step-level `mapbox_streets_v8.class` var. Mevcut kod boş list alıp fallback'e düşüyor (yani road class classification şu an gerçekten çalışmıyor) |
| **Scope tahmini** | ~3-5 hafta full pipeline (backend + persist + ML + frontend + literatür kalibrasyon). Kullanıcı "düşündüğünden basit değil" uyardı — küçümsemiyoruz |
| **Önerilen ilk hamle** | Phase 0: kod bug'ı (`road_class` annotation) doğrula + Mapbox Directions response'unu gerçek 2-3 koordinat çiftine bas, raw JSON'u plan dosyasına ek olarak koy (canlı API verisi, varsayım değil) |

---

## 1. Mevcut durum — kod kanıtlarıyla

### 1.1 ML predict_consumption() — sefer aggregate scalar input

`app/services/prediction_service.py:556-573`:

```python
predict_consumption(
    arac_id, mesafe_km, ton,
    ascent_m,           # toplam tırmanış metre (sefer toplamı)
    descent_m,          # toplam iniş metre
    flat_distance_km,   # düz km toplam
    sofor_id, dorse_id, sofor_score,
    ramp_pct,           # rampa yüzdesi
    target_date, zorluk, use_ensemble,
    bos_sefer, route_analysis,
)
```

Output (line 698-756 civarı): **tek `tahmini_tuketim` sayısı** + bantlar. Per-segment yok.

Pipeline:
1. Vehicle specs + age degradation
2. Route ratios scalar (otoyol/devlet_yolu/sehir_ici 0.6/0.3/0.1 default)
3. Weather seasonal factor scalar
4. Physics model → tek L/100km
5. Driver score + ramp adjustment scalar
6. Ensemble ML (LightGBM/XGBoost/GB/RF) — input sefer-level dict
7. Maintenance factor scalar
8. Final L/100km

**Her adım sefer-aggregate**. Segment-mode hiçbir yerde yok.

### 1.2 Mapbox client — per-segment data alıyor ama atıyor

`app/infrastructure/routing/mapbox_client.py:56`:

```python
"annotations": "distance,duration,maxspeed,road_class"
```

`_classify_road_segments()` (113-198):

```python
for leg in legs:
    annotation = leg.get("annotation", {})
    distances: List[float] = annotation.get("distance", [])
    maxspeeds: List[Dict] = annotation.get("maxspeed", [])
    road_classes: List[str] = annotation.get("road_class", [])  # ← BUG
    # ...
    for i, seg_dist in enumerate(distances):
        r_class = road_classes[i] if i < len(road_classes) else "street"
        # her segment için motorway_m / trunk_m / primary_m / secondary_m / city_m
        # SONRA bunlar km'ye çevrilip 5 buckete aggregate → sefer-level scalar
```

**Bug**: Mapbox Directions API response'da `road_class` annotation YOK (Mapbox docs onaylı, aşağıda §2.1). Mevcut kod `annotation.get("road_class", [])` ile boş list alıyor → `r_class = "street"` fallback → çoğu segment city_m bucket'ına yazılıyor (yani classification şu an gerçekten yanlış). `maxspeed` ile fallback ediyor ama sadece `r_class` tanımsızsa.

`ascent_m: 0.0` ve `descent_m: 0.0` hard-coded (line 92): Mapbox Directions elevation vermiyor.

### 1.3 Route analyzer — ORS için segment intersect (sefer aggregate'e dökülüyor)

`app/domain/services/route_analyzer.py:45-200`:

- ORS extras'tan `steepness`, `waycategory`, `waytype` per-segment alıyor
- Geometry koordinatları kümülatif distance ile birleştirip her metreyi (steepness × waycategory × waytype) 3-boyutlu kategorize ediyor
- **Sonra**: `highway × {flat,up,down}` ve `other × {flat,up,down}` — 6 bucket'a aggregate

GradeClass enum var (downhill_steep/-moderate/flat/uphill_moderate/-steep) ama **kullanılmıyor** — sadece aggregate sırasında up/flat/down 3 sınıfına düşürülüyor.

### 1.4 Sefer schema — per-segment yer ayrılmamış

`app/database/models.py` SeferModel: `ascent_m`, `descent_m`, `flat_distance_km`, `route_analysis` (jsonb). `route_analysis` aggregate snapshot tutuyor, segment listesi tutmuyor.

`route_paths` tablosu var (mapbox/ors cache) — `geometry` (polyline jsonb), distance/duration/ascent_m/descent_m **sefer-level cache**. Per-segment kolonu yok.

---

## 2. Mapbox API capability matrix (doğrulanmış, 2026-05-29)

### 2.1 Directions API annotations (`driving-traffic` profile)

Resmi dokümantasyondan ([Mapbox Directions API](https://docs.mapbox.com/api/navigation/directions/)) doğrulanmış per-segment annotation'lar:

| Annotation | Var mı | Granularite | Not |
|---|---|---|---|
| `distance` | ✅ | per coordinate pair (segment) | metre |
| `duration` | ✅ | per segment | saniye |
| `speed` | ✅ | per segment | m/s, **gerçek tahmini hız** (traffic dahil), maxspeed değil |
| `congestion` | ✅ | per segment | string (low/moderate/heavy/severe), only `driving-traffic` |
| `congestion_numeric` | ✅ | per segment | 0-100, only `driving-traffic` |
| `maxspeed` | ✅ (BETA) | per segment | obje (km/h veya mph, ya da "unknown"/"none") |
| `closure` | ✅ | per segment | live closure object |
| **`road_class`** | ❌ | — | **Annotation listesinde yok**. Step-level `intersections.mapbox_streets_v8.class` var (motorway/motorway_link/primary/street vs.) ama per-coordinate segment'a doğrudan map edilmiyor |
| **elevation / gradient** | ❌ | — | Annotation olarak yok. EV routing internal kullanıyor (`ev_ascent`/`ev_descent` request param, response'da değil) |

**Sonuç**: Mevcut `annotations="distance,duration,maxspeed,road_class"` — `road_class` boş döner. Doğru olan: `annotations="distance,duration,speed,maxspeed,congestion,congestion_numeric"`.

Road class için iki seçenek:
- **A.** Her step'in `intersections` listesinden `mapbox_streets_v8.class` çek, polyline distance ile reconcile et
- **B.** maxspeed → speed bucket (mevcut fallback): `≥110 motorway, ≥80 trunk, ≥50 primary, <50 city`

A daha doğru, ama step boundary ↔ segment boundary reconciliation gerektirir.

### 2.2 Mapbox Tilequery API (elevation per coordinate)

[Mapbox Terrain-RGB docs](https://docs.mapbox.com/data/tilesets/reference/mapbox-terrain-rgb-v1/) onaylı:

```
GET https://api.mapbox.com/v4/mapbox.terrain-rgb/tilequery/{lon},{lat}.json
    ?access_token=...
```

- REST endpoint, **tek koordinat → elevation** döner (PNG tile decode etmeden)
- ⚠️ Terrain-RGB tileset **Aralık 2021'den beri güncellenmiyor**; resmi öneri: **`mapbox.terrain-dem-v1`**
- Manuel decode formülü (eğer batch tile-level yapacaksak): `height = -10000 + (R*65536 + G*256 + B) * 0.1`

**Gradient (eğim %)** hesabı:
```
grade_pct = (elev[i+1] - elev[i]) / distance_m * 100
```

API çağrı maliyeti: route N segment için N+1 tilequery çağrısı. Hız (lat,lon başına 1 HTTP request). Workaround:
- Mapbox Static API tile indirip lokal decode (1 tile ~100km², toplu segment cache'lenir)
- Veya OpenElevation / Open-Meteo elevation API (ücretsiz alternatif)

### 2.3 Mapbox Map Matching API (gerçek telematik varsa)

İleri faz: AVL'den gelen GPS trace'i Mapbox Map Matching'e gönderip **gerçekleşen** route + speed profile çıkarmak (bizim AVL provider abstraction'ı zaten var, henüz canlı veri yok). Plan'ın Phase 4'üne aday.

---

## 3. Hedef mimari — hybrid pipeline

```
┌──────────────────────────────────────────────────────────────────────┐
│  Input: arac_id, sofor_id, dorse_id, cikis_lat/lon, varis_lat/lon,  │
│          ton, target_date                                            │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  1) Route fetch — Mapbox Directions /driving-traffic                 │
│     annotations: distance,duration,speed,maxspeed,congestion         │
│     → polyline geometry + N segment (coord pair) array               │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  2) Elevation enrichment — Mapbox Terrain-DEM Tilequery batch        │
│     her segment için (lat,lon) → elevation_m                         │
│     → segment[i].grade_pct = Δelev / distance * 100                  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  3) Road class enrichment — step.intersections.mapbox_streets_v8.    │
│     class → segment'lere kuş bakışı haritala (boundary reconcile)    │
│     → segment[i].road_class ∈ {motorway, trunk, primary, secondary,  │
│                                  tertiary, residential, service}     │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  4) Resampling — N raw segment'i sabit ~500m parçalara yeniden       │
│     böl. Her 500m: (avg_grade, road_class mode, maxspeed mode,       │
│     traffic_speed avg, congestion mode)                              │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  5) Per-segment simulation                                           │
│     ┌── 5a) Speed model: simulated_speed = f(maxspeed,               │
│     │       traffic_speed, grade_pct, road_class, vehicle_specs,     │
│     │       driver_profile)                                          │
│     └── 5b) Fuel model: L_per_100km = VT-CPFM(speed, grade, mass,    │
│             vehicle_aero, drivetrain) × maintenance × weather        │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  6) Aggregate roll-up → mevcut SeferCreate format                    │
│     (mesafe, ascent_m, descent_m, otoban_km, ...) — backward compat  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  7) Persist                                                          │
│     - route_paths.segments (yeni JSONB kolon) — segment array        │
│     - veya route_segments tablo (FK route_path_id)                   │
│     - sefer.simulation_id → bu kaydı bağlar (opsiyonel)              │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  8) Endpoint                                                         │
│     POST /api/v1/routes/simulate                                     │
│     GET  /api/v1/routes/simulate/{simulation_id}                     │
│     Response: {                                                      │
│       summary: { total_km, total_l, ... },                          │
│       segments: [ { from_km, to_km, lat, lon, grade_pct,             │
│                     road_class, maxspeed, sim_speed, L_per_100km,    │
│                     eta_sec, congestion } ]                          │
│     }                                                                │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  9) Frontend (mapbox-gl-js)                                          │
│     - Polyline color = simulated_speed (heatmap)                     │
│     - Side panel: hız profili line chart + L/100km bar chart         │
│     - Click segment → detay popup                                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. Fuel simulation modeli — literatür + öneri

Mevcut `physics_fuel_predictor.py` zaten fizik tabanlı bir model içeriyor (aero drag + rolling resistance + grade resistance + acceleration). Bu **sefer-mode**'da L/100km döndürüyor. Segment-mode'a dönüştürmek için:

### 4.1 Aday modeller

| Model | Avantaj | Dezavantaj | LojiNext için |
|---|---|---|---|
| **VT-Micro** | Power-based, drive cycle uyumlu | Çok parametre, kalibrasyon zor (lab/saha verisi gerekir) | ⚠️ Calibration cost yüksek |
| **VT-CPFM** | Comprehensive, alan testlerinde MOVES'tan iyi | Hala 8+ kalibrasyon parametresi | ✅ İyi başlangıç |
| **MOVES (EPA)** | Endüstri referansı | Heavy/complex; bin/operating mode tabanlı | Referans karşılaştırma |
| **VSP (Vehicle Specific Power)** | Basit: `VSP = v(1.1a + 9.81 grade + 0.132) + 0.000302v³` | Kalibrasyonsuz başlat, gerçek L'ye dönüşüm tablo gerektirir | ✅ MVP için iyi |
| **EOP (Engine Output Power)** | Direkt engine output kullanır | Truck telematik verisi (CAN bus) gerekir, bizde yok | ❌ AVL geldiğinde |
| **LSTM-Conv (2024)** | MAPE %9.81 (en iyi), DL | Eğitim verisi: saniye-saniye fuel rate gerekir, bizde yok | ❌ Telemetri sonrası |

[Heavy-duty trucks fuel consumption model (ScienceDirect 2017)](https://www.sciencedirect.com/science/article/abs/pii/S1361920916309865): Sadeghian-Rahmani Iran HDD route'larında VT-Micro/VT-CPFM benchmark — VT-CPFM çelişen kondisyonlar dışında daha tutarlı.

[LSTM-Conv 2024 paper (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1361920924001147): MAPE %1.49 trip-level economy. Vehicle weight'i DL frame'ine entegre. **Eğitim için telematik şart**.

### 4.2 Öneri (LojiNext için)

**Phase 1 MVP**: VSP-based simple model:
```
VSP_kW = v(1.1 a + 9.81 grade_pct/100 + 0.132) + 0.000302 v³  [m/s, %]
fuel_L_per_h = a₀ + a₁·VSP + a₂·VSP²   (sabit araç sınıfı için kalibre)
```
Mevcut `physics_fuel_predictor` zaten benzer denklemleri içeriyor (force balance). Sadece **segment-mode interface**: tek sefer yerine her segment için çağrılabilir hale getir.

**Phase 2 Kalibrasyon**: Pilot uçuş sonrası gerçek yakıt fişi (`yakit_alimlari`) + sefer KM ile retro-fit. Driver × route-tipi katsayıları zaten var (`driver_route_profile.py`), segment-level uygulanabilir.

**Phase 3 (sonra)**: AVL telematik (CAN bus, instantaneous speed/RPM) gelince LSTM-Conv veya benzeri DL modeli eğit.

---

## 5. Veri modeli değişiklikleri

### 5.1 Yeni `route_segments` tablo (önerilen)

```sql
CREATE TABLE route_segments (
  id              BIGSERIAL PRIMARY KEY,
  route_path_id   BIGINT NOT NULL REFERENCES route_paths(id) ON DELETE CASCADE,
  seq             INTEGER NOT NULL,         -- 0, 1, 2, ...
  from_km         NUMERIC(8,3) NOT NULL,    -- segment start km from route origin
  to_km           NUMERIC(8,3) NOT NULL,
  mid_lat         DOUBLE PRECISION NOT NULL,
  mid_lon         DOUBLE PRECISION NOT NULL,
  grade_pct       REAL,                     -- -25..+25 typical
  road_class      VARCHAR(20),              -- enum-like
  maxspeed_kmh    SMALLINT,
  congestion      VARCHAR(10),              -- low/moderate/heavy/severe/unknown
  sim_speed_kmh   REAL,                     -- simulated effective speed
  sim_fuel_l100   REAL,                     -- simulated L/100km
  eta_sec         INTEGER,
  meta            JSONB,                    -- extras: weather, driver factor, etc.
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (route_path_id, seq)
);
CREATE INDEX ix_route_segments_route ON route_segments(route_path_id);
```

**Alternatif**: `route_paths.segments JSONB` kolonu. Daha az JOIN ama query-only erişim zayıf (ör. "tüm yokuş segmentlerini şehir bazında listele" için JSONB scan).

### 5.2 Sefer ilişkisi

`seferler` tablosuna `route_simulation_id BIGINT NULL REFERENCES route_paths(id)` (cached simülasyon link'i). Mevcut `guzergah_id` lokasyon kaydı; bu farklı (simülasyon snapshot).

### 5.3 Alembic migration plan

1. `route_segments` create
2. `seferler.route_simulation_id` add nullable
3. Backward compat: mevcut `predict_consumption` aggregate'e dokunma, yeni endpoint paralel

---

## 6. Backend endpoint'ler

### 6.1 `POST /api/v1/routes/simulate`

Request:
```json
{
  "arac_id": 12,
  "sofor_id": 7,
  "dorse_id": 4,
  "cikis_lat": 41.0082, "cikis_lon": 28.9784,
  "varis_lat": 39.9334, "varis_lon": 32.8597,
  "ton": 15000,
  "target_date": "2026-06-15",
  "segment_length_m": 500
}
```

Response (gerçek/canlı veri shape):
```json
{
  "simulation_id": 9421,
  "summary": {
    "distance_km": 451.2,
    "duration_min": 312,
    "total_l": 142.3,
    "avg_l_per_100km": 31.5,
    "total_ascent_m": 1850,
    "total_descent_m": 1612
  },
  "segments": [
    {
      "seq": 0, "from_km": 0.0, "to_km": 0.5,
      "mid_lat": 41.0080, "mid_lon": 28.9786,
      "grade_pct": -0.8, "road_class": "primary",
      "maxspeed_kmh": 50, "congestion": "moderate",
      "sim_speed_kmh": 42, "sim_fuel_l100": 38.2,
      "eta_sec": 43
    },
    /* ... ~900 segment ... */
  ]
}
```

### 6.2 `GET /api/v1/routes/simulate/{simulation_id}`

Cached simülasyonu hızlı döndür. TTL: 7 gün (traffic değişebilir, ama yapısal veri stabil).

### 6.3 `GET /api/v1/routes/simulate/preview?cikis=...&varis=...`

Master sefer yapısı yokken hızlı 1-shot — sadece geometry + road class + maxspeed, simülasyon yok. Lokasyon yönetimi sayfasında "nasıl gözükür" preview için.

---

## 7. Frontend — mapbox-gl-js entegrasyonu

### 7.1 Yeni component: `RouteSimulationMap.tsx`

- `mapbox-gl-js` veya `react-map-gl` wrapper
- Polyline rendering: segment-by-segment, `paint: line-color: <interpolated from sim_speed_kmh>`
- Heatmap legend (yeşil = 90+ km/h, kırmızı = <30)
- Click segment → popup: grade, road_class, maxspeed, sim_speed, L/100km

### 7.2 Side panel

- Hız profili line chart (X=km, Y=km/h): maxspeed + traffic_speed + sim_speed (3 çizgi)
- L/100km bar chart per segment
- Summary card: total L, avg, ascent/descent, traffic delay

### 7.3 Yeni sayfa: `/routes/simulator` veya `/locations/:id/simulate`

Lokasyon kayıt sayfasına "Simüle Et" butonu → sayfa açılır. Form: araç + şoför + dorse + ton + tarih → simulate.

### 7.4 Frontend bağımlılık

- `mapbox-gl` ~250KB gzip, ekstra ücret yok (kullanıcı zaten Mapbox token sahibi)
- `react-map-gl` opsiyonel wrapper (DX)
- Recharts/Tremor zaten var (Reports v2'den)

---

## 8. ML / `physics_fuel_predictor` segment-mode dönüşümü

Mevcut `physics_fuel_predictor.py`:
- Input: `mesafe_km, ton, ascent_m, descent_m, flat_distance_km, ...` (sefer aggregate)
- Internal: force balance (drag, rolling, grade, acceleration) — fizik denklemleri
- Output: L/100km scalar

Segment-mode için **yeniden yazmadan**, **wrapper**:

```python
def simulate_segment(seg: SegmentInput, vehicle: VehicleSpec, ...) -> SegmentOutput:
    # 1) sim_speed = effective_speed(maxspeed, traffic, grade, road_class)
    # 2) physics_predictor.predict_l_per_100km(
    #        mesafe_km=seg.length_km, ton=ton,
    #        ascent_m=max(0, seg.grade*seg.length),
    #        descent_m=max(0, -seg.grade*seg.length),
    #        flat_distance_km=seg.length_km if abs(grade)<3 else 0,
    #        ...
    #    )
    # 3) apply driver × road_class katsayı (driver_route_profile.py)
    # 4) maintenance + weather faktör (mevcut)
    return SegmentOutput(sim_speed, sim_l_100, eta_sec)
```

Aggregate predict_consumption'a **dokunma** (CI risk). Segment simulasyonu paralel pipeline'da.

---

## 9. Aşamalı sevkıyat — Phase plan

### Phase 0 — Tetkik + doğrulama (1-2 gün)

- ✅ Bu plan dosyası
- [ ] `mapbox_client.py:146` `road_class` annotation YOK bug'ını canlı API'ye sorgu atarak teyit et (real response JSON → plan ek dosyası)
- [ ] Mapbox Tilequery API'sini 5-10 koordinat için sorgula, elevation kalitesini ölç (Türkiye'de yoğunluk tatmin edici mi)
- [ ] Performans benchmark: 450 km route ≈ ~900 segment, Mapbox Directions + Tilequery × 900 = makul mi (rate limit + maliyet)

### Phase 1 — Backend prototype (1 hafta)

- [ ] `app/core/services/route_simulator.py` (yeni)
- [ ] `app/core/ml/segment_simulator.py` (physics wrapper)
- [ ] `route_segments` migration
- [ ] `POST /api/v1/routes/simulate` endpoint (no persist henüz, in-memory)
- [ ] Unit testler (physics_fuel_predictor segment-mode invariants)

### Phase 2 — Persist + cache (3-4 gün)

- [ ] `route_segments` insert + retrieval
- [ ] Tilequery batch + cache (Redis 7-gün TTL)
- [ ] Directions response cache (1-gün TTL — traffic değişir)
- [ ] Rate limit + retry (Mapbox SLA)

### Phase 3 — Frontend simulator UI (1 hafta)

- [ ] `RouteSimulationMap.tsx` + `react-map-gl` install
- [ ] Hız profili chart
- [ ] `/routes/simulator` sayfa
- [ ] E2E test (Playwright, **task #145 düzeltildikten sonra**)

### Phase 4 — Kalibrasyon (sürekli, pilot verisi geldiğinde)

- [ ] Pilot 1000 sefer × yakıt fişi → retro-fit
- [ ] VSP coefficient'leri (a₀, a₁, a₂) araç sınıfı bazında fine-tune
- [ ] Driver × road_class faktörü segment uygulaması
- [ ] MAPE ölç, %15 altına düşür

### Phase 5 — AVL entegrasyonu (provider seçildikten sonra)

- [ ] Gerçek GPS trace → Mapbox Map Matching
- [ ] Telemetri (instant speed, RPM eğer CAN bus var) → segment-level fuel rate
- [ ] LSTM-Conv veya benzeri DL modeli (yeterli veri olunca)

---

## 10. Risk + scope tahmini (dürüst)

| Risk | Etki | Hafifletme |
|---|---|---|
| Mapbox quota/cost — 900 segment × N araç × günlük çağrı | $$ | Tilequery batch (1 tile çoklu segment), Directions cache 24h, kullanıcı sefer ekledikçe değil sayfa açıldıkça çağrı |
| Terrain-DEM eski (2021) | gradient hatası | OpenElevation fallback; pilot karşılaştırma |
| `road_class` reconciliation (step.intersections → segment) | karmaşık iş | Maxspeed-bucket fallback (mevcut kod logic'ine yakın) |
| VT-CPFM kalibrasyonu eksik | %20+ hata | MVP'de VSP-basit, pilot sonrası fit |
| Frontend mapbox-gl kütüphane boyutu | bundle +250KB gz | Lazy load `/routes/simulator` sayfasında |
| AVL provider TBD → telematik yok → DL imkansız | Phase 5 ertelendi | Phase 1-4 fiziksel model yeterli |
| Mevcut `predict_consumption` aggregate kullanıcılarını kırma | regresyon | Paralel pipeline, yeni endpoint, eski hat dokunulmaz |
| **Kullanıcı: "düşündüğünden basit değil"** | scope shock | Phase 0 doğrulamayı atlama, gerçek Mapbox response al |

**Scope tahmini**:
- Phase 0: 1-2 gün
- Phase 1: 5-7 iş günü
- Phase 2: 3-4 iş günü
- Phase 3: 5-7 iş günü
- Phase 4: sürekli (pilot sonrası)
- Phase 5: AVL geldiğinde (ay-yıl)

**Toplam Phase 0-3**: ~3-4 hafta (1 geliştirici), kapsamlı testle.

**Karşılaştırma**: ilk tahminim "~1 hafta" idi, gerçek scope 3-4 hafta + (kalibrasyon + AVL) belirsiz. Kullanıcı uyarısı haklıydı.

---

## 11. Açık sorular — kullanıcıya / dış kararlar

1. **Maliyet sınırı**: Mapbox Directions (`driving-traffic`) ~ $5 / 1000 request, Tilequery ücretsiz quota dahilinde. Aylık tahmin: 100 sefer/gün × 30 = 3000 simülasyon ≈ $15/ay. Üzerinde mi tahmin?
2. **Segment length**: 500m sabit mi yoksa road_class değişiminde yeni segment (dinamik)? Dinamik daha az ama daha düzensiz UI.
3. **Frontend lib**: `mapbox-gl-js` direkt mi yoksa `react-map-gl` wrapper? Wrapper DX iyi ama +ek dependency.
4. **Kalibrasyon zamanı**: VSP coefficient'lerini kim/ne zaman tune'lar? Veri bilimci yok şu an.
5. **AVL provider**: Mobiliz mi Arvento mu? Phase 5'in start date'i buna bağlı.
6. **Existing sefer ↔ yeni simülasyon**: Excel ile bulk sefer import'unda simülasyon **otomatik** mi çağrılsın (yüksek API maliyeti) yoksa sadece tek tek kullanıcı açtığında mı?
7. **Drive cycle vs static**: Statik (sefer önce tahmin) yapacağız; **gerçekleşen** (sefer sonrası geri besleme) ayrı feature?

---

## 12. Önerilen ilk hamle

**Phase 0 sadece**, kod yazılmadan:

1. Mapbox token ile **gerçek Directions API çağrısı** — 3 sefer örnek koordinat çifti:
   - İstanbul-Ankara (uzun, otoyol-ağırlıklı)
   - İstanbul içi Maslak-Kadıköy (kısa, şehir-içi)
   - Bursa-Antalya (orta, dağlık)
   - Response JSON'ları `docs/superpowers/plans/2026-05-29-route-segment-simulation-plan-mapbox-samples/` altına commit edilir
   - Doğrulamak: `road_class` annotation YOK (bug teyidi), `speed` ne kadar gerçeğe yakın (traffic accuracy), `maxspeed` Türkiye yolları için doluluk (rural mı motorway mı dahil)
2. Mapbox **Tilequery** ile 10 koordinat → elevation; Türkiye'de coverage ve hassasiyet (Google Earth ile karşılaştır)
3. `physics_fuel_predictor` segment-mode wrapper için **prototype** (1 dosya, no DB, no endpoint) — sadece `simulate_segment(seg, vehicle) → output` mock test'le

Bu 1-2 gün, sonuçları bu plan dosyasına **append** edilir, sonra Phase 1 başlatma kararı.

---

## 13. Sources

Resmi dokümantasyon:
- [Mapbox Directions API — annotations](https://docs.mapbox.com/api/navigation/directions/)
- [Mapbox Terrain-RGB tileset](https://docs.mapbox.com/data/tilesets/reference/mapbox-terrain-rgb-v1/)

Heavy-duty truck fuel consumption literatürü:
- [Fuel consumption model for heavy duty diesel trucks: Model development and testing (ScienceDirect 2017)](https://www.sciencedirect.com/science/article/abs/pii/S1361920916309865)
- [Fuel consumption estimation in heavy-duty trucks: Integrating vehicle weight into deep-learning frameworks (ScienceDirect 2024)](https://www.sciencedirect.com/science/article/abs/pii/S1361920924001147)
- [Heavy Duty Truck Fuel Consumption Prediction Based on Driving Cycle Properties (ResearchGate)](https://www.researchgate.net/publication/232896984_Heavy_Duty_Truck_Fuel_Consumption_Prediction_Based_on_Driving_Cycle_Properties)
- [Real drive cycles analysis by ordered power methodology (Springer Nature 2020)](https://link.springer.com/article/10.1007/s11783-020-1296-z)
- [TRID — Fuel consumption model for HDD trucks](https://trid.trb.org/View/1480179)

Kod referansları (LojiNext repo, 2026-05-29 itibarıyla):
- `app/services/prediction_service.py:556-756` — predict_consumption
- `app/services/route_service.py:38-200` — ORS path
- `app/infrastructure/routing/mapbox_client.py:113-198` — road class classification (bug'lı)
- `app/domain/services/route_analyzer.py:45-200` — segment intersect + aggregate
- `app/core/ml/physics_fuel_predictor.py` — fiziksel motor (sefer-mode)
- `app/core/ml/driver_route_profile.py` — şoför × güzergah tipi
- `app/core/ml/route_similarity.py` — cosine route benzerliği

---

**Bu plan canlı belge değil — kalıcı artifact**. Uygulama başlarken bu dosya referans, kod ve test'ler PR'larda. Phase 0 sonuçları append edilebilir, ama core mimari ve scope değişirse yeni dosya (`-v2.md`).

---

## 14. Phase 0 sonuçları (2026-05-29 canlı API)

Raw JSON: `mapbox-samples/{istanbul-ankara,maslak-kadikoy,bursa-antalya}-raw.json`
Probe script: `scripts/mapbox_phase0_probe.py`
Özet rapor: `mapbox-samples/_summary.md`

### 14.1 `road_class` annotation — DOĞRULANDI: yok

`annotations=...,road_class` Mapbox 422 InvalidInput. Resmi geçerli liste:
`duration, distance, speed, congestion, congestion_numeric, closure,
state_of_charge, energy_levels, maxspeed`.

**Production etkisi**: `mapbox_client.py:56` mevcut string her çağrıda 422
alıyordu. `route_service.py:200` Mapbox'u sadece ORS fallback olarak
çağırıyor; 422 silent yutuluyor (`mb_result = None`), ORS sonucuyla devam.
Yani Mapbox enrichment fiilen hiç çalışmıyordu — kırılmadı, hiç başlamadı.

### 14.2 `step.intersections[*].mapbox_streets_v8.class` — kullanılabilir

3 rota canlı ölçüm:

| Rota | Segment | mapbox_streets_v8 doluluk |
|---|---|---|
| İstanbul-Ankara (443km otoyol) | 5400 | %99.9 |
| Maslak-Kadıköy (19km şehir) | 571 | %99.3 |
| Bursa-Antalya (548km dağlık) | 5177 | %99.9 |

Değerler endüstri std: motorway/trunk/primary/secondary/tertiary/street/
residential/service + `_link` variantları.

Reconcile mantığı `mapbox_client.py` `_reconcile_segment_road_classes()`
helper'ında: `geometry_index`'lere göre sıralı intersection listesini gez,
her annotation segment kendinden önceki son class'ı miras alır.

### 14.3 Yeni mapbox sınıflandırma çıktısı (reconcile sonrası)

| Rota | otoyol | devlet | sehir | otoban_km | sehir_km |
|---|---|---|---|---|---|
| İstanbul-Ankara | 0.89 | 0.11 | 0.00 | 443.2 | 0.3 |
| Maslak-Kadıköy | 0.57 | 0.40 | 0.03 | 18.3 | 0.6 |
| Bursa-Antalya | 0.00 | 1.00 | 0.00 | 547.9 | 0.0 |

Bursa-Antalya'da otoyol 0 — bu rota gerçekten D-yolu (trunk) tabanlı,
mevcut tek otoyol parçası FSM köprüsünden başlıyor değil. Doğru tespit.

### 14.4 maxspeed Türkiye coverage

| Rota | maxspeed seg | unknown/none | top values |
|---|---|---|---|
| İST-ANK | 5400 | 572 (%10.6) | 130/120/140 km/h |
| MAS-KAD | 571 | 119 (%20.8) | 70/90/50 km/h |
| BRS-ANT | 5177 | 1201 (%23.2) | 110/70/50/90 km/h |

Dağlık/rural rotalarda %23 unknown — bu kısımlar için `speed`
annotation (gerçek traffic-aware hız, %100 dolu) fallback olarak
kullanılabilir.

### 14.5 `speed` (traffic-aware) annotation

3 rotada da %100 doluluk. Birim: m/s. Bu, Phase 1'de simulated_speed
hesabı için **maxspeed'den daha güvenilir input** (live traffic dahil).

### 14.6 `congestion_numeric` 0-91 dağılımı

| Rota | low% | moderate% | heavy% | unknown% |
|---|---|---|---|---|
| İST-ANK | 85 | 1.7 | 0.5 | 12.5 |
| MAS-KAD | 73 | 18 | 4 | 4.7 |
| BRS-ANT | 45 | 0.4 | 0 | 54 |

Şehir içi congestion enformasyonu zengin; intercity/rural'da büyük
oranda unknown (Mapbox traffic flotası rural'da daha az).

### 14.7 Phase 0 sonucu kabul edilen kararlar

- ✅ road_class annotation request'ten KALDIRILDI
- ✅ steps=true + intersections.mapbox_streets_v8.class kullanılıyor
- ✅ Reconcile helper test'lendi (synthetic 6 + real-data 3 → 9 unit test)
- ✅ Backward compat: `_classify_road_segments` aynı ratio shape döndürüyor
- ⏳ Segment-mode simulator wrapper — P0.4'te prototip

---

## 15. Phase 0.2 — Elevation accuracy (2026-05-30)

Probe: `scripts/mapbox_tilequery_phase0.py`
Rapor: `mapbox-samples/_tilequery_elevation.md`

### 15.1 Mapbox Terrain options — ne çalışıyor?

| Kaynak | Durum | Notes |
|---|---|---|
| `mapbox.terrain-dem-v1` | ❌ 404 | Raster tileset, Tilequery (vector) desteklemez |
| `mapbox.terrain-rgb-v1` | ⚠️ Deprecated 2021 | Manuel tile download + PNG decode gerek |
| `mapbox.mapbox-terrain-v2` | ✅ HTTP 200 | Vector contour (200m interval), `properties.ele` döner |
| Open-Meteo `/v1/elevation` | ✅ HTTP 200 | SRTM 30m DEM, batch endpoint, ücretsiz |

### 15.2 10 nokta Türkiye accuracy (referans: OSM/Wiki şehir yüksekliği)

| Tip | Mapbox terrain-v2 |err| | Open-Meteo |err| |
|---|---|---|
| Şehir merkezleri (Ankara/Konya/Diyarbakır) | 20-90m | 5-33m |
| Sahil (İstanbul/Antalya/İzmir/Trabzon) | 15-45m (genelde -10m!) | 5-15m |
| Dağ zirveleri (Erzurum/Kayseri Erciyes) | 0-250m | 38-90m |

**Mapbox failure modu**: vector contour 0m altında özel değer dönüyor (-10), zirvelerde 200m interval'inin alt katı.
**Open-Meteo**: 9/10 noktada ±100m altında (Uludağ referans hatasını saymazsak ±33m altında).

### 15.3 Karar — Phase 1 elevation kaynağı

**Open-Meteo `/v1/elevation`** (SRTM 30m DEM):
- ✅ Batch endpoint (tek istekte N koordinat) — 900 segmentlik route için 1-2 çağrı
- ✅ Ücretsiz, ~50ms latency
- ✅ Türkiye'de tolerans içinde
- ⚠️ 3rd-party (Mapbox dışı) — uptime/SLA Phase 2'de Redis cache ile riski azalt

Mapbox terrain-v2 fallback: kontur layer yine `road_class` reconcile yardımı için faydalı olabilir (örn. tunnel/bridge layer'ı), ama elevation için DEĞİL.

### 15.4 Phase 1 elevation entegrasyon iskeleti

```python
# app/infrastructure/elevation/open_meteo_client.py (yeni)
async def get_elevations(coords: list[tuple[float, float]]) -> list[float]:
    # 1 batch, SRTM 30m
    ...

# Cache: redis "elev:{lon}:{lat}" → m, 30 günlük TTL (relief sabit)
```

Segment yoğunluğu: 500m bandında 900 nokta için ~1 sn cold, cache hit ile ~5ms.

**Phase 1 hazır.**
