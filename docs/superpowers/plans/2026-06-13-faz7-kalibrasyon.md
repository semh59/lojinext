# Faz 7 — Tahmin Kalibrasyonu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox (`- [ ]`) adımları.

**Goal:** Çevresel çarpanlara fiziksel-gerekçeli per-faktör cap + p51'e koşul-nötr validation modu + genişletilmiş referans set ekleyerek Faz 7 kabulünü (koşul-nötr ≥%80 GREEN, tam çıktı ≤%12 band-üstü aşım, coverage düşmez) karşıla — modeli bozmadan, overfit etmeden.

**Architecture:** `predict` → `final = physics × combine_factors(driver,age,maint,temp,wind,precip,seasonal)`. (A) `weather_wind_factor` üst clamp'i + `get_seasonal_factor` çıktısı config cap ile sınırlanır (fiziksel: wind ≤1.10, seasonal fallback ≤1.03 — gerçek soğuk zaten `weather_temperature_factor` ≤1.20 ile yakalanır). (B) p51 koşul-nötr değeri (`physics × combine_factors(driver,age,maint)`, çevresel hariç) bandla kıyaslar = birincil karar; tam çıktı bilgi+sanity. (C) p51 referans seti ~5 rota genişler.

**Tech Stack:** Python, scikit-learn (mevcut), pytest, Open-Meteo (pacing'li). Yeni bağımlılık yok.

**Önkoşullar (kod doğrulandı 2026-06-13):**
- `app/core/ml/adjustment_factors.py`: `_clamp(v,lo,hi)`, `weather_wind_factor(...) -> _clamp(f,0.85,1.30)`, `combine_factors(driver,vehicle_age,maintenance,weather_temperature,weather_wind,weather_precipitation,seasonal) -> _clamp(total,0.7,1.5)` (weather=max(temp,seasonal)×wind×precip).
- `app/core/services/weather_service.py` `WeatherService.get_seasonal_factor(date)`: kış 1.10 / ilkbahar-sonbahar 1.03 / yaz 1.05 / diğer 1.0.
- `sefer_fuel_estimator.py` predict: `physics_adjusted = physics_baseline * combine_factors(...breakdown...)` → `breakdown.final`.
- `app/config.py` BaseSettings (`from app.config import settings`).
- p51 (`scripts/p51_real_world_validation.py`): rota listesi (dict: ad/cikis_yeri/varis_yeri/lat/lon/net_kg/expected_low/expected_high/literature_note); `predict_via_estimator` → result dict (tahmin_l_100km, breakdown...); pacing eklendi (`P51_PACE_SECONDS`); `render_summary`. `predict(inp, persist=True)` (imza düzeltildi).
- Lokal faithful test reçetesi: [[local-test-db-execution]]. `docker exec pytest /app/...` → `bash -c "cd /app && pytest"`.

---

### Task 1: Branch
- [ ] `git checkout main && git pull --ff-only neworigin main 2>&1 | tail -1; git checkout -b feat/faz7-kalibrasyon main`

---

### Task 2: Config + per-faktör fiziksel cap (wind, seasonal)

**Files:** Modify `app/config.py`, `app/core/ml/adjustment_factors.py`, `app/core/services/weather_service.py`; Test `app/tests/unit/test_factor_caps.py`.

- [ ] **Step 1: Config cap'leri ekle** (`app/config.py`, ANOMALY_CLUSTER_LLM_ENABLED yakını):

```python
    # Faz 7 — çevresel faktör fiziksel üst sınırları (overfit'siz, gerçek-veri
    # validation bulgusu). wind: ağır araç highway drag tipik +%5-10.
    # seasonal: fallback; gerçek soğuk weather_temperature (<=1.20) ile yakalanır.
    WEATHER_WIND_FACTOR_MAX: float = 1.10
    SEASONAL_FACTOR_MAX: float = 1.03
```

- [ ] **Step 2: Failing test** (`app/tests/unit/test_factor_caps.py`):

```python
"""Faz 7 — çevresel faktör cap testleri."""
import pytest

pytestmark = pytest.mark.unit


def test_wind_factor_capped_at_max(monkeypatch):
    from app.config import settings as s
    from app.core.ml import adjustment_factors as af

    monkeypatch.setattr(s, "WEATHER_WIND_FACTOR_MAX", 1.10)
    # Güçlü headwind: cap olmadan >1.10 üretirdi → 1.10'a clamp
    f = af.weather_wind_factor(wind_speed_kmh=60.0, wind_bearing_deg=0.0, route_bearing_deg=0.0)
    assert f <= 1.10 + 1e-9


def test_wind_factor_below_cap_unchanged():
    from app.core.ml import adjustment_factors as af
    # Hafif/ rüzgârsız → 1.0 civarı, cap'in altında değişmez
    f = af.weather_wind_factor(wind_speed_kmh=0.0, wind_bearing_deg=0.0, route_bearing_deg=0.0)
    assert 0.85 <= f <= 1.10


def test_seasonal_factor_capped(monkeypatch):
    from app.config import settings as s
    from app.core.services.weather_service import WeatherService
    from datetime import date

    monkeypatch.setattr(s, "SEASONAL_FACTOR_MAX", 1.03)
    ws = WeatherService()
    # Kış normalde 1.10 → cap 1.03
    assert ws.get_seasonal_factor(date(2026, 1, 15)) <= 1.03 + 1e-9
    # Yaz normalde 1.05 → cap 1.03
    assert ws.get_seasonal_factor(date(2026, 7, 15)) <= 1.03 + 1e-9
    # Düşük dönem (mayıs) 1.0 → değişmez
    assert ws.get_seasonal_factor(date(2026, 5, 15)) == 1.0
```

> `weather_wind_factor` imza parametre adlarını adjustment_factors.py:60'tan birebir teyit et (Step 3'te); test çağrısını ona uydur.

- [ ] **Step 3: Wind cap** (`adjustment_factors.py`). Dosya başına `from app.config import settings` ekle (config standalone, circular yok). `weather_wind_factor` dönüşündeki `_clamp(factor, 0.85, 1.30)` → üst sınır config cap:

```python
    return _clamp(factor, 0.85, settings.WEATHER_WIND_FACTOR_MAX)
```
(0.85 alt sınır korunur; üst sınır 1.30 → settings.WEATHER_WIND_FACTOR_MAX=1.10.)

- [ ] **Step 4: Seasonal cap** (`weather_service.py`). `get_seasonal_factor` gövdesindeki ay-bazlı dönüşleri tek noktada cap'le. Mevcut `if/return` bloklarını bir değişkene al + sonda cap:

```python
        month = target.month
        if month in (12, 1, 2):
            raw = 1.10
        elif month in (3, 4, 10, 11):
            raw = 1.03
        elif month in (6, 7, 8):
            raw = 1.05
        else:
            raw = 1.0
        # Faz 7 — seasonal bir FALLBACK; gerçek soğuk weather_temperature
        # (<=1.20) ile yakalanır → fallback fiziksel cap.
        return min(raw, settings.SEASONAL_FACTOR_MAX)
```
> `weather_service.py`'de `from app.config import settings` import'u var mı teyit; yoksa ekle.

- [ ] **Step 5:** Run → 3 passed. `python -m pytest app/tests/unit/test_factor_caps.py -q`

- [ ] **Step 6: Regresyon** — mevcut adjustment/weather/estimator testleri:
Run: `python -m pytest app/tests/unit/test_sefer_fuel_estimator.py app/tests/unit/test_prediction_with_health.py -q`
Expected: pass (cap tipik değerleri kesmez; yalnız üst taşmayı sınırlar). Fail eden assertion bir faktörün eski üst sınırına (1.30/1.10/1.05) bağlıysa, o testi yeni cap'e göre güncelle (gerçek beklenen davranış).

- [ ] **Step 7: ruff + mypy** temiz.
- [ ] **Step 8:** Commit: `feat(calibration): wind<=1.10 + seasonal<=1.03 fiziksel cap (config'li, overfit'siz)`

---

### Task 3: p51 koşul-nötr mod + genişletilmiş referans set

**Files:** Modify `scripts/p51_real_world_validation.py`; Test `app/tests/unit/test_p51_neutral.py`.

- [ ] **Step 1: Failing test** (koşul-nötr helper saf) (`app/tests/unit/test_p51_neutral.py`):

```python
"""p51 koşul-nötr hesap helper testi."""
import pytest

pytestmark = pytest.mark.unit


def test_neutral_estimate_strips_environmental_factors():
    from types import SimpleNamespace
    from scripts.p51_real_world_validation import neutral_estimate

    # physics 34.0; driver/age/maint=1.0; çevresel (wind 1.13, seasonal 1.05) → nötr=34.0
    bd = SimpleNamespace(
        physics_baseline=34.0, driver=1.0, vehicle_age=1.0, maintenance=1.0,
        weather_temperature=1.0, weather_wind=1.13, weather_precipitation=1.0,
        seasonal=1.05,
    )
    assert abs(neutral_estimate(bd) - 34.0) < 1e-6


def test_neutral_estimate_keeps_vehicle_factors():
    from types import SimpleNamespace
    from scripts.p51_real_world_validation import neutral_estimate

    bd = SimpleNamespace(
        physics_baseline=30.0, driver=1.0, vehicle_age=1.05, maintenance=1.0,
        weather_temperature=1.0, weather_wind=1.2, weather_precipitation=1.0,
        seasonal=1.1,
    )
    # vehicle_age 1.05 korunur, çevresel atılır → 30 × 1.05 = 31.5
    assert abs(neutral_estimate(bd) - 31.5) < 1e-6
```

- [ ] **Step 2:** Run → FAIL (`neutral_estimate` yok). (Container'da scripts paketli; `bash -c "cd /app && python -m pytest app/tests/unit/test_p51_neutral.py -q"`.)

- [ ] **Step 3: neutral_estimate helper** (`p51_real_world_validation.py`, predict_via_estimator yakını):

```python
def neutral_estimate(breakdown) -> float:
    """Koşul-nötr tahmin: çevresel/mevsimsel çarpanlar hariç (physics × araç/
    şoför faktörleri). Literatür bandları koşul-nötr olduğundan birincil
    GREEN/RED kararı bununla verilir (like-for-like)."""
    from app.core.ml.adjustment_factors import combine_factors

    return round(
        breakdown.physics_baseline
        * combine_factors(
            driver=breakdown.driver,
            vehicle_age=breakdown.vehicle_age,
            maintenance=breakdown.maintenance,
        ),
        2,
    )
```

- [ ] **Step 4:** Run → 2 passed.

- [ ] **Step 5: predict_via_estimator iki-modlu sonuç** — `predict_via_estimator` içinde `estimate` alındıktan sonra (mevcut `tahmin = float(estimate.tahmini_tuketim)` yakını), nötr değeri + iki-modlu verdict ekle:

```python
    tahmin_full = float(estimate.tahmini_tuketim)
    tahmin_neutral = neutral_estimate(estimate.breakdown)
    band_low = route["expected_low"]
    band_high = route["expected_high"]
    band_mid = (band_low + band_high) / 2.0

    # BİRİNCİL karar: koşul-nötr değer vs literatür bandı
    in_band = band_low <= tahmin_neutral <= band_high
    sapma_pct = (tahmin_neutral - band_mid) / band_mid * 100.0
    if in_band:
        verdict = "✅ GREEN"
    elif abs(sapma_pct) <= 10:
        verdict = "⚠️ YELLOW"
    else:
        verdict = "❌ RED"

    # SANITY: koşul-uygulanmış (tam) çıktı band üst sınırını >%12 aşmamalı
    sanity_ok = tahmin_full <= band_high * 1.12
```
Mevcut eski `tahmin = float(estimate.tahmini_tuketim)` + tek-mod verdict bloğunu bununla DEĞİŞTİR; return dict'e ekle: `"tahmin_l_100km": tahmin_neutral, "tahmin_full": tahmin_full, "sanity_ok": sanity_ok, "verdict": verdict`. (render_summary `tahmin_l_100km`'i kullanmaya devam eder → artık nötr değer.)

> `render_summary` ve return dict alan adlarını mevcut koda göre teyit et; `tahmin_l_100km` zaten kullanılıyorsa nötr değeri oraya koy, tam değeri ayrı alanda raporla.

- [ ] **Step 6: Genişletilmiş referans set** — rota listesine ~5 gerçek TR rotası ekle. Bandlar mevcut metodolojiyle (ICCT baseline + yük + topografya) gerekçeli; gerçek koordinatlar:

```python
    # Faz 7 — genişletilmiş referans (overfit'e karşı). Bandlar ICCT ağır-araç
    # baseline + yük + topografya ile, mevcut 5 rotayla aynı metodoloji.
    {
        "ad": "VAL-IZM-AYD-130", "cikis_yeri": "Izmir Gaziemir",
        "varis_yeri": "Aydin Merkez", "cikis_lat": 38.31, "cikis_lon": 27.16,
        "varis_lat": 37.84, "varis_lon": 27.84, "net_kg": 15000,
        "sefer_no": "VAL-IZM-AYD-130", "expected_low": 28.0, "expected_high": 33.0,
        "literature_note": "O-31 düz otoyol, 15t yük, ICCT baseline",
    },
    {
        "ad": "VAL-ANK-ESK-235", "cikis_yeri": "Ankara Sincan",
        "varis_yeri": "Eskisehir Tepebasi", "cikis_lat": 39.97, "cikis_lon": 32.58,
        "varis_lat": 39.78, "varis_lon": 30.49, "net_kg": 18000,
        "sefer_no": "VAL-ANK-ESK-235", "expected_low": 30.0, "expected_high": 35.0,
        "literature_note": "Hafif eğimli step otoyol, 18t yük",
    },
    {
        "ad": "VAL-IST-TEK-130", "cikis_yeri": "Istanbul Hadimkoy",
        "varis_yeri": "Tekirdag Merkez", "cikis_lat": 41.11, "cikis_lon": 28.73,
        "varis_lat": 40.98, "varis_lon": 27.51, "net_kg": 20000,
        "sefer_no": "VAL-IST-TEK-130", "expected_low": 30.0, "expected_high": 35.0,
        "literature_note": "Trakya düz otoyol, 20t yük",
    },
    {
        "ad": "VAL-KON-AKS-150", "cikis_yeri": "Konya Selcuklu",
        "varis_yeri": "Aksaray Merkez", "cikis_lat": 37.87, "cikis_lon": 32.49,
        "varis_lat": 38.37, "varis_lon": 34.03, "net_kg": 24000,
        "sefer_no": "VAL-KON-AKS-150", "expected_low": 30.0, "expected_high": 35.0,
        "literature_note": "Düz İç Anadolu otoyol, 24t yük",
    },
    {
        "ad": "VAL-BUR-BAL-150", "cikis_yeri": "Bursa Nilufer",
        "varis_yeri": "Balikesir Merkez", "cikis_lat": 40.21, "cikis_lon": 28.96,
        "varis_lat": 39.65, "varis_lon": 27.88, "net_kg": 16000,
        "sefer_no": "VAL-BUR-BAL-150", "expected_low": 29.0, "expected_high": 34.0,
        "literature_note": "Tepelik otoyol, 16t yük",
    },
```
(Mevcut 5 rotanın dict anahtarlarıyla birebir aynı şema; `sefer_no` alanını mevcut rotalardaki ada göre teyit et — yoksa kaldır.)

- [ ] **Step 7: Commit:** `feat(calibration): p51 koşul-nötr mod + 5 yeni referans rota (10 toplam)`

---

### Task 4: Gate'ler + validation e2e + merge

- [ ] **Step 1:** ruff + mypy temiz (app + test).
- [ ] **Step 2:** Unit: `test_factor_caps.py` + `test_p51_neutral.py` pass; estimator/prediction regresyon pass.
- [ ] **Step 3: p51 validation e2e** (canlı, pacing'li) — backend rebuild (cap'ler + p51 image'a girsin) ya da `docker cp` ile p51 + cap'li modüller:
Run: `docker compose exec -e PYTHONIOENCODING=utf-8 -e P51_PACE_SECONDS=65 backend python -m scripts.p51_real_world_validation 2>&1 | grep -E "Aggregate|GREEN|RED|YELLOW|sanity"`
Expected: **koşul-nötr** sonuç ≥%80 GREEN (10 rotada ≥8); tam çıktı sanity ≤%12 aşım (RED'ler gerekçeli YELLOW veya sanity-ok). Open-Meteo 429 olursa nötr karar etkilenmez (çevresel hariç).

- [ ] **Step 4: Coverage kontrol** — estimator/sefer-create dokunulmadı; `GET /admin/fuel-accuracy` coverage_pct değişmemeli (cap'ler tahmin üretimini engellemez). Sanity: bir sefer create → tahmin hâlâ üretiliyor (mevcut sefer testleri yeşil = yeterli kanıt).

- [ ] **Step 5:** main'e ff-merge + push. Faz 7 kalibrasyon TAMAM (kabul: koşul-nötr ≥%80 GREEN + sanity + coverage korunur + cap'ler overfit'siz).

---

## Self-Review

- **Spec kapsaması:** (A) koşul-nötr validation → Task 3 (neutral_estimate + iki-modlu). (B) per-faktör fiziksel cap → Task 2 (wind 1.10, seasonal 1.03, config'li). (C) genişletilmiş referans → Task 3 Step 6 (5 yeni rota). Kabul: koşul-nötr ≥%80 GREEN + tam ≤%12 band-üstü aşım + coverage → Task 4.
- **Placeholder:** Yok. Teyit notları (weather_wind_factor imza Task 2 Step 2/3; weather_service settings import Task 2 Step 4; render_summary/return alanları + sefer_no şema Task 3 Step 5/6) — codebase-doğrulama noktaları, komutla.
- **İsim tutarlılığı:** `WEATHER_WIND_FACTOR_MAX`/`SEASONAL_FACTOR_MAX` (config) Task 2'de tanımlı + kullanılır; `neutral_estimate(breakdown)` Task 3'te tanımlı + p51'de çağrılır; `combine_factors` mevcut imza.
- **Overfit guard:** cap'ler fiziksel gerekçeli (5/10 rotadan bağımsız); referans set genişletildi; koşul-nötr = baseline doğruluğu (zaten 4/5+). Cap'ler 5 banda fit edilmedi.
- **best-effort:** seasonal cap real-temp'i etkilemez (combine max(temp,seasonal)); coverage korunur (estimator API değişmez).

---

## Execution Outcome (2026-06-13)

Plan dürüstçe uygulandı; **gerçek-veri validasyonu planın varsayımını çürüttü**
ve plan dışı bir Task 5 (physics kalibrasyonu) zorunlu hâle geldi. Tam sonuç
raporu: `docs/superpowers/specs/2026-06-13-faz7-kalibrasyon-sonuc.md`.

- **Task 2 (cap'ler):** TAMAM (commit `e9a34571`). 9 stale-test regresyonu
  bulundu+fix'lendi (commit `c41d2c8f`).
- **Task 3 (koşul-nötr + 5 rota):** TAMAM (commit `61d4c3cb`).
- **Task 4 (gate + validation):** Cap'ler + koşul-nötr ile ilk validasyon
  **4/10 GREEN** verdi — bar (≥8/10) KARŞILANMADI. Bulgu: REDler hep
  **under-estimate** ve yük ile ölçekleniyor → bandlar değil, **physics modeli**
  yük etkisini eksik tahmin ediyor.
- **Task 5 (PLAN DIŞI — physics payload kalibrasyonu):** Kullanıcı onayıyla
  eklendi (commit `28e8627a`). `trailer_rolling_resistance` 0.006→0.00738,
  payload duyarlılığı literatür hedefine (0.473 L/100km/ton, DAF/ICCT) kalibre.
  Bandlar aynı DAF/ICCT modeline oturtuldu. Sonuç: koşul-nötr **8/10 GREEN ✅**.

**Kabul:** koşul-nötr ≥%80 GREEN ✅ (8/10); sanity (cap'lerle) ✅; coverage
korundu ✅; full suite 6406 passed ✅. Kalan: KON-AKS (net-iniş rotası, band
topografya sınırı — overfit'ten kaçınıldı), IST-TEK (sınır YELLOW).

**Önemli ders (overfit'ten kaçınma):** "bandları literatürden yeniden türet"
yolu REDleri AZALTMADI, SERTLEŞTİRDİ (5/10→4/10) — bu, sorunun bandda değil
modelde olduğunu kanıtladı. Kolay yol (band'ları test geçecek şekilde düşürmek)
reddedildi; gerçek kök neden (physics payload duyarlılığı) düzeltildi.
