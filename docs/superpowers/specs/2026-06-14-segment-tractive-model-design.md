# Segment-Bazlı Tractive Yakıt Modeli — Tasarım (Spec)

**Tarih:** 2026-06-14
**Bağlam:** Faz 7 kalibrasyon kök-neden analizinin devamı
(`2026-06-13-faz7-kalibrasyon-sonuc.md` §7). İlgili karar: [[route-segment-simulation]].

---

## 1. Problem

Faz 7 validasyonu iki yapısal physics kusuru ortaya çıkardı (payload
kalibrasyonu 0.473 ile sefer doğruluğu 8/10'a çıktı ama iki kusur kaldı):

1. **Cross-segment enerji netleştirme (aggregate yol):** `PhysicsBasedFuelPredictor.predict_granular`
   tüm segmentleri birden alınca grade enerjisi `m·g·(1.05·ΣÇIKIŞ − recovery·ΣİNİŞ)`'e
   indirgeniyor (segment uzunluğu sadeleşir; gravitasyonel PE yola-bağımsız). Route
   düzeyinde iniş, başka segmentin yakıtını siliyor — dizel TIR'da enerji deposu
   yok, fiziksel imkânsız. **Kullanan:** `prediction_service.predict_consumption`
   (granular_nodes / RouteConditions yolu).
2. **Base/intercept çok düşük (her iki yol):** Düz-yol tüketimi gerçeğin ~%25
   altında. KON-AKS (%86 düz, 2.2 m/km) physics-nötr 27.78 vs literatür ~34.8.
   Normal-eğimli rotalarda tırmanış enerjisiyle maskeleniyor, düz rotada açığa
   çıkıyor. Sebep: `engine_efficiency=0.40` pik-BSFC iyimser; drivetrain kaybı +
   rölanti/aksesuar (zaman-bazlı) yükü hiç sayılmıyor.

**Estimator** (`sefer_fuel_estimator` → `RouteSimulator.simulate` → `segment_simulator.simulate_route`)
zaten **per-segment** çağırıp segment-düzeyinde floor'luyor → #1 onu vurmuyor; ama
#2 (base) + grade gürültüsü onu da vuruyor.

Ek veri gerçeği (kanıt: `route_segments` sorgusu):
- **Grade gürültüsü:** IST-BOL'de %11 segment |grade|>%8, 12 segment >%15 (yolda
  fiziksel imkânsız) — Open-Meteo SRTM (~90m) + 500m resample artefaktı. Ham çıkış
  5652m, %8 clamp'le 4972m → 680m sahte. Düz KON-AKS'ta 0 gürültü.
- **Hız verisi:** `maxspeed_kmh`/`traffic_speed_kmh` çoğu TR segmentinde **boş**
  (Mapbox "unknown" döner). Drag (∝v²) road-class varsayım hızına düşüyor.

## 2. Hedef

İki physics yolunu **tek, fiziksel olarak doğru, segment-bazlı tractive motorda**
birleştir; cross-segment netleştirmeyi kaldır; base-level'ı zaman-bazlı parazit
yükle literatüre kalibre et; grade gürültüsünü temizle; gerçek hız verisini varsa
kullan. Sonuç: iki koordinat → güvenilir yolculuk simülasyonu.

**Kabul:** p51 koşul-nötr **≥9/10 GREEN** (KON-AKS dahil, eğimli rotalarda GREEN
regresyonu yok); full unit suite yeşil; payload duyarlılığı 0.473 korunur; ML
ensemble regresyonsuz. Yeni motor **feature flag** ardında (default kapalı),
validasyon sonrası açılır.

## 3. Tasarım

### 3.1 Tek tractive motor — `predict_segment_tractive`

`PhysicsBasedFuelPredictor`'a yeni metot. Segment listesi alır, **her segmenti
bağımsız** hesaplar, **toplar** (netleştirme yok):

```
predict_segment_tractive(segments, total_mass_kg, arac_yasi, **kw) -> FuelPrediction:
  fuel_total = 0
  for (dist_m, v_ms, delta_h) in segments:
      grade = clamp(delta_h/dist_m, -0.09, +0.09)          # gürültü temizleme
      F_roll  = Crr_eff(total_mass) · g                     # tractor+trailer split korunur
      F_air   = ½·ρ·Cd·A·v²
      F_grade = total_mass · g · grade                       # İŞARETLİ
      F_trac  = F_roll + F_air + F_grade
      E_prop  = max(0.0, F_trac) · dist_m                    # SIFIR taban; iniş kredisi yok
      fuel_prop = E_prop / (η_bsfc · η_driveline)
      t_s     = dist_m / max(v_ms, 1.0)
      fuel_aux = P_parasitic_W · t_s / (LHV_J_per_L)         # zaman-bazlı base (kW → L)
      fuel_total += (fuel_prop + fuel_aux) / fuel_energy...  # birim dönüşüm
  consumption = fuel_total / total_km · 100
```

- **Gravity recovery KALDIRILIR.** `_get_gravity_recovery` artık kullanılmaz; iniş
  `F_trac≤0` ise propulsion 0 (fuel-cut), aksesuar tabanı kalır. Hafif iniş
  `F_trac>0` ise doğal-azaltılmış pozitif.
- **`Crr_eff`** mevcut tractor/trailer rolling split'i korur (payload 0.473
  kalibrasyonu `trailer_rolling_resistance=0.00738` buradan gelir, DEĞİŞMEZ).
- **Per-segment MAX_REALISTIC clamp** (mevcut 65 L/100km, `silent_outlier_log`)
  korunur — gürültü artığı dik segment outlier'ı için.

### 3.2 Yeni kalibrasyon sabitleri (config, literatür-bağlı)

```python
# app/config.py
PHYSICS_ENGINE_BSFC: float = 0.42          # pik termal verim (Euro-6 dizel)
PHYSICS_DRIVELINE_EFF: float = 0.95        # şanzıman+aks
PHYSICS_PARASITIC_KW: float = 6.0          # soğutma+alternatör+klima+rölanti (zaman-bazlı base)
PHYSICS_GRADE_CLAMP_PCT: float = 9.0       # yol fiziksel max eğim (gürültü kesme)
USE_SEGMENT_TRACTIVE_MODEL: bool = False   # rollout flag (validasyon sonrası true)
```

Efektif verim `η = 0.42·0.95 = 0.399` (mevcut 0.40'a yakın → propulsion ~korunur)
**+ parazit yük base'i ayrı ekler** → düz rotalar gerçekçi tabana çıkar, hızlı
highway şişmez (parazit zaman-bazlı: yavaş/düz rota daha çok dk/km → daha çok base).
Sabitler `scripts/calibrate_physics.py` ile DAF/ICCT'ye fit edilir (§3.4).

### 3.3 İki yolu birleştir (flag'li)

- `physics_fuel_predictor.predict_granular`: flag açıksa segment listesini
  `predict_segment_tractive`'e delege eder (cross-segment netleştirme yok olur);
  kapalıysa eski davranış (rollback).
- `segment_simulator.simulate_segment`: flag açıksa tek-segment tractive yolu
  (zaten per-segment; recovery kalkar + parazit eklenir).
- Estimator + prediction_service kod değişmez — flag motoru değiştirir.

### 3.4 Kalibrasyon (`scripts/calibrate_physics.py`)

Saf fonksiyon hedefi: `Crr`, `BSFC`, `parasitic_kW` üçlüsünü
`C_flat(payload) = 25.1 + 0.473·(payload_t − 2.6)` eğrisine ve ICCT 33.1
baseline'a fit et (düz-yol, ~80 km/h, tipik yük). Payload slope 0.473 zaten
`trailer_rolling_resistance`'ten geliyor → onu sabit tut, BSFC+parasitic ile
**intercept**'i kaldır. Overfit guard: sabitler fiziksel bantta kalmalı
(BSFC 0.40-0.46, parasitic 3-10 kW, Crr 0.005-0.008).

### 3.5 Veri tamlığı — hız annotation akışı

`mapbox_client` zaten `annotations=...,speed,maxspeed,congestion` istiyor.
- **`route_segments`'e `maxspeed`/`traffic_speed`/`congestion` doğru yazıldığını
  doğrula/tamamla** (RouteSimulator→SegmentInput→persist zinciri); şu an persist'te
  0 görünüyor — kaynağı (resampler maxspeed taşıyor mu? "unknown"→None mı?) izle.
- **Hız öncelik zinciri** (`_effective_speed_kmh` genişletilir): `traffic_speed`
  (canlı) > `maxspeed` (kural) > road-class default. Mapbox `speed` (canlı trafik)
  TR'de maxspeed'den daha sık dolu → drag doğruluğu artar.
- Mapbox "unknown" gerçeği: kapatılamaz (dış veri); fallback zinciri + segment
  başına `speed_source` log/coverage metriği.

## 4. Hata yönetimi

- Boş/0-uzunluk segment → atla (mevcut). Tüm segmentler 0 → `MIN_REALISTIC` floor.
- Grade clamp + per-segment MAX clamp gürültüyü sınırlar; route-level clamp log'u
  korunur (`silent_outlier_log`).
- Flag kapalıyken davranış bit-aynı (rollback garantisi).
- Calibration fiziksel bant dışına çıkarsa script hata verir (overfit guard).

## 5. Test stratejisi

- **Birim (deterministik, API'siz):** `predict_segment_tractive` — (a) cross-segment
  netleştirme yok (büyük inişli sentetik rota eski aggregate'ten yüksek çıkar),
  (b) grade clamp (±15% segment → ±9% işlenir), (c) parazit base (yavaş düz rota >
  hızlı düz rota L/100km), (d) payload slope 0.473 korunur, (e) fuel-cut (dik iniş
  segmenti propulsion 0 + sadece aksesuar).
- **Kalibrasyon testi:** fit sonrası sabitler fiziksel bantta + flat-base literatür
  ±%5.
- **Regresyon:** full unit suite; ML ensemble (physics member shift kabul, contract
  bozulmaz); flag kapalı = eski snapshot.
- **e2e (quota-aware):** p51 `P51_PACE_SECONDS=90`, koşul-nötr ≥9/10 GREEN (KON-AKS
  dahil), sanity 10/10, eğimli rotalarda regresyon yok. Open-Meteo daily quota
  reset sonrası tek temiz koşu.

## 6. Rollout

1. Motor + kalibrasyon + testler merge (flag **default false** — davranış değişmez).
2. p51 quota-reset sonrası validate.
3. Validasyon GREEN ise `USE_SEGMENT_TRACTIVE_MODEL=true` (config default) flip +
   docker-compose env; ML ensemble yeniden eğitimi tetikle (physics member değişti).
4. Geçiş izleme: `GET /admin/fuel-accuracy` coverage + MAPE.

## 7. Kapsam dışı (YAGNI)

- Transient/stop-go kinetik enerji modeli (ileride; şimdilik parazit + hız profili
  yeterli yaklaşım).
- Rüzgâr-yön bazlı per-segment drag (mevcut weather_wind faktörü yeterli).
- Mapbox dışı hız kaynağı (OSM maxspeed scrape) — ayrı epik.
