# Segment-Bazlı Tractive Yakıt Modeli Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans veya subagent-driven-development. Checkbox (`- [ ]`) adımları.

**Goal:** İki physics yolunu (aggregate `predict_granular` + per-segment `segment_simulator`) tek fiziksel-doğru segment-bazlı tractive motorda birleştir; cross-segment enerji netleştirmeyi kaldır, base-level'ı zaman-bazlı parazit yükle literatüre kalibre et, grade gürültüsünü temizle, gerçek hız verisini kullan. Feature flag ardında, validasyon sonrası açılır.

**Architecture:** `PhysicsBasedFuelPredictor.predict_segment_tractive` yeni motor; her segment bağımsız hesaplanır + toplanır (netleştirme yok). `predict_granular` + `segment_simulator` flag açıkken buna delege eder. Sabitler config'te, DAF/ICCT'ye kalibre. Spec: `docs/superpowers/specs/2026-06-14-segment-tractive-model-design.md`.

**Tech Stack:** Python, mevcut physics modülü, pytest, Open-Meteo (pacing'li, daily-quota-aware). Yeni bağımlılık yok.

**Önkoşullar (kod doğrulandı 2026-06-13/14):**
- `physics_fuel_predictor.py`: `VehicleSpecs` (empty_weight_kg=8000, trailer_empty_weight_kg=6500, rolling_resistance=0.007, **trailer_rolling_resistance=0.00738** [Faz 7], drag_coefficient=0.52, trailer_drag_contribution=0.13, frontal_area_m2=8.2, engine_efficiency=0.40, fuel_density_kg_l=0.835, fuel_energy_mj_kg=45.8). Sabitler GRAVITY=9.81, AIR_DENSITY=1.225, MAX_REALISTIC_L_100KM=65, MIN_REALISTIC_L_100KM=15. `predict_granular(segments, load_ton, is_empty_trip, historical_stats, **kw)` — kw: arac_yasi, silent_outlier_log.
- `segment_simulator.py`: `SegmentInput(dist_m,v_*,grade_pct,maxspeed_kmh,...)`, `simulate_segment(seg, predictor, ton, arac_yasi, ...)` → `predict_granular` tek segment; `_effective_speed_kmh(seg)` (traffic? maxspeed? road-class). `simulate_route` → her segment ayrı.
- `sefer_fuel_estimator.py` → `RouteSimulator.simulate` → `simulate_route`; `physics_baseline = sim_result.summary.avg_l_per_100km`.
- `prediction_service.py:~407` → `predict_granular(granular_nodes, ...)` (aggregate) veya `physics.predict(RouteConditions)` (→ `_build_segments` → aggregate).
- `mapbox_client.py`: `annotations=distance,duration,speed,maxspeed,congestion,congestion_numeric`.
- `config.py` `from app.config import settings`; `app/tests/conftest.py` faithful Py3.12 reçetesi [[local-test-db-execution]]; `docker exec` yerine `bash -c "cd /app && pytest"`.
- LHV türevi: `LHV_J_per_L = fuel_energy_mj_kg × fuel_density_kg_l × 1e6 = 45.8×0.835×1e6 = 3.8243e7 J/L`.

---

### Task 1: Branch + feature flag config

**Files:** Modify `app/config.py`.

- [ ] **Step 1:** `git checkout main && git checkout -b feat/segment-tractive-model main`

- [ ] **Step 2: Config sabitleri** (`app/config.py`, `WEATHER_WIND_FACTOR_MAX` yakını):

```python
    # Segment-tractive model (2026-06-14) — fiziksel-doğru per-segment yakıt.
    PHYSICS_ENGINE_BSFC: float = 0.42          # Euro-6 dizel pik termal verim
    PHYSICS_DRIVELINE_EFF: float = 0.95        # şanzıman + aks verimi
    PHYSICS_PARASITIC_KW: float = 6.0          # soğutma+alternatör+klima+rölanti (zaman-bazlı base)
    PHYSICS_GRADE_CLAMP_PCT: float = 9.0       # yol fiziksel max eğim (SRTM gürültü kesme)
    USE_SEGMENT_TRACTIVE_MODEL: bool = False   # rollout flag — validasyon sonrası true
```

- [ ] **Step 3:** `bash -c "cd /app && python -c 'from app.config import settings; print(settings.PHYSICS_ENGINE_BSFC, settings.USE_SEGMENT_TRACTIVE_MODEL)'"` → `0.42 False`
- [ ] **Step 4:** Commit: `feat(physics): segment-tractive model config flag + sabitleri`

---

### Task 2: `predict_segment_tractive` motoru (TDD)

**Files:** Modify `app/core/ml/physics_fuel_predictor.py`; Test `app/tests/unit/test_ml/test_segment_tractive.py`.

- [ ] **Step 1: Failing testler** (`app/tests/unit/test_ml/test_segment_tractive.py`):

```python
"""Segment-bazlı tractive yakıt motoru testleri (fiziksel doğruluk)."""
import pytest

from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

pytestmark = pytest.mark.unit


def _p():
    return PhysicsBasedFuelPredictor()


def test_no_cross_segment_netting_vs_aggregate():
    # Büyük inişli rota: aggregate (predict_granular) inişi route geneline kredi
    # eder → düşük; tractive segment-floor'lu → daha YÜKSEK (netleştirme yok).
    p = _p()
    # 10km düz + 5km %6 iniş (delta_h negatif): (dist_m, v_ms, delta_h)
    segs = [(10000.0, 22.0, 0.0), (5000.0, 22.0, -300.0)]
    aggr = p.predict_granular(list(segs), load_ton=20.0)
    trac = p.predict_segment_tractive(list(segs), total_mass_kg=8000 + 6500 + 20000, arac_yasi=5)
    assert trac.consumption_l_100km > aggr.consumption_l_100km


def test_grade_clamped_to_max():
    # %20 eğimli segment → %9'a clamp (SRTM gürültüsü). Clamp'siz çok yüksek olurdu.
    p = _p()
    m = 8000 + 6500 + 20000
    steep = p.predict_segment_tractive([(1000.0, 15.0, 200.0)], total_mass_kg=m, arac_yasi=5)  # %20
    capped = p.predict_segment_tractive([(1000.0, 15.0, 90.0)], total_mass_kg=m, arac_yasi=5)   # %9
    assert steep.consumption_l_100km == pytest.approx(capped.consumption_l_100km, rel=1e-3)


def test_parasitic_base_slow_vs_fast_flat():
    # Aynı düz mesafe; yavaş rota daha çok dk → daha çok parazit yakıt/km.
    p = _p()
    m = 8000 + 6500 + 20000
    slow = p.predict_segment_tractive([(10000.0, 8.0, 0.0)], total_mass_kg=m, arac_yasi=5)   # 28.8 km/h
    fast = p.predict_segment_tractive([(10000.0, 25.0, 0.0)], total_mass_kg=m, arac_yasi=5)  # 90 km/h
    assert slow.consumption_l_100km > fast.consumption_l_100km


def test_steep_descent_propulsion_zero_floor():
    # Dik iniş: F_trac<0 → propulsion 0, yalnız aksesuar tabanı → düşük ama pozitif.
    p = _p()
    m = 8000 + 6500 + 20000
    out = p.predict_segment_tractive([(2000.0, 20.0, -160.0)], total_mass_kg=m, arac_yasi=5)  # %8 iniş
    assert 0.0 < out.consumption_l_100km < 12.0


def test_payload_slope_preserved():
    # Düz yol; 12t → 24t yük artışı L/100km'yi yaklaşık 0.473×12≈5.7 artırmalı.
    p = _p()
    flat = [(50000.0, 22.0, 0.0)]
    c12 = p.predict_segment_tractive(flat, total_mass_kg=8000 + 6500 + 12000, arac_yasi=5).consumption_l_100km
    c24 = p.predict_segment_tractive(flat, total_mass_kg=8000 + 6500 + 24000, arac_yasi=5).consumption_l_100km
    slope = (c24 - c12) / 12.0
    assert 0.40 <= slope <= 0.55
```

- [ ] **Step 2:** Run → FAIL (`predict_segment_tractive` yok).
Run: `bash -c "cd /app && python -m pytest app/tests/unit/test_ml/test_segment_tractive.py -q"`

- [ ] **Step 3: Motoru ekle** (`physics_fuel_predictor.py`, `predict_granular`'dan sonra):

```python
    def predict_segment_tractive(
        self,
        segments: List[Tuple[float, float, float]],
        total_mass_kg: float,
        arac_yasi: int = 5,
        **kwargs,
    ) -> FuelPrediction:
        """Fiziksel-doğru per-segment tractive yakıt.

        Her segment bağımsız: tractive enerji (rolling+air+İŞARETLİ grade),
        sıfır-taban (iniş kredisi route'a yayılmaz), zaman-bazlı parazit base.
        Gravity recovery YOK — dizel TIR'da enerji deposu yok.
        """
        from app.config import settings

        lhv_j_per_l = (
            self.vehicle.fuel_energy_mj_kg * self.vehicle.fuel_density_kg_l * 1e6
        )
        eta_prop = settings.PHYSICS_ENGINE_BSFC * settings.PHYSICS_DRIVELINE_EFF
        eta_aux = settings.PHYSICS_ENGINE_BSFC
        p_par_w = settings.PHYSICS_PARASITIC_KW * 1000.0
        grade_cap = settings.PHYSICS_GRADE_CLAMP_PCT / 100.0
        combined_cd = (
            self.vehicle.drag_coefficient + self.vehicle.trailer_drag_contribution
        )
        # rolling split: tractor sabit + (trailer_empty+load) trailer rr (payload slope)
        trailer_and_load = total_mass_kg - self.vehicle.empty_weight_kg
        f_roll = (
            self.vehicle.empty_weight_kg * self.GRAVITY * self.vehicle.rolling_resistance
            + trailer_and_load * self.GRAVITY * self.vehicle.trailer_rolling_resistance
        )

        fuel_l = 0.0
        total_km = 0.0
        for dist_m, v_ms, delta_h in segments:
            if dist_m <= 0:
                continue
            total_km += dist_m / 1000.0
            grade = max(-grade_cap, min(grade_cap, delta_h / dist_m))
            f_air = (
                0.5 * self.AIR_DENSITY * combined_cd * self.vehicle.frontal_area_m2
                * (v_ms ** 2)
            )
            f_grade = total_mass_kg * self.GRAVITY * grade
            f_trac = f_roll + f_air + f_grade
            e_prop = max(0.0, f_trac) * dist_m
            fuel_l += e_prop / (eta_prop * lhv_j_per_l)
            t_s = dist_m / max(v_ms, 1.0)
            fuel_l += (p_par_w * t_s) / (eta_aux * lhv_j_per_l)

        if not np.isfinite(fuel_l):
            fuel_l = 0.0
        cons = (fuel_l / total_km * 100.0) if total_km > 0 else 0.0
        if cons > self.MAX_REALISTIC_L_100KM:
            if not kwargs.get("silent_outlier_log", False):
                logger.warning(
                    "tractive_outlier: %.1f l/100km > MAX_REALISTIC (dist=%.0f km)",
                    cons, total_km,
                )
                _physics_outlier_counter.inc()
            cons = self.MAX_REALISTIC_L_100KM
            fuel_l = cons * total_km / 100.0

        return FuelPrediction(
            total_liters=round(fuel_l, 2),
            consumption_l_100km=round(cons, 2),
            energy_breakdown={},
            confidence_range=(round(fuel_l * 0.92, 1), round(fuel_l * 1.08, 1)),
            factors_used={"total_mass_kg": total_mass_kg, "distance_km": round(total_km, 2), "model": "tractive"},
        )
```

- [ ] **Step 4:** Run → 5 passed. (Slope testi kalibrasyon öncesi geçer çünkü trailer_rr 0.00738 zaten 0.473 verir; geçmezse Task 5 kalibrasyonu ayarlar — o zaman bu adımı Task 5 sonrası tekrar çalıştır.)
- [ ] **Step 5: ruff + mypy** temiz.
- [ ] **Step 6:** Commit: `feat(physics): predict_segment_tractive — netleştirmesiz, sıfır-floor, parazit base`

---

### Task 3: `predict_granular` flag delegasyonu

**Files:** Modify `app/core/ml/physics_fuel_predictor.py`; Test ekle `test_segment_tractive.py`.

- [ ] **Step 1: Failing test** (delegasyon):

```python
def test_predict_granular_delegates_when_flag_on(monkeypatch):
    from app.config import settings as s
    monkeypatch.setattr(s, "USE_SEGMENT_TRACTIVE_MODEL", True)
    p = _p()
    segs = [(10000.0, 22.0, 0.0), (5000.0, 22.0, -300.0)]
    out = p.predict_granular(list(segs), load_ton=20.0, arac_yasi=5)
    assert out.factors_used.get("model") == "tractive"


def test_predict_granular_legacy_when_flag_off(monkeypatch):
    from app.config import settings as s
    monkeypatch.setattr(s, "USE_SEGMENT_TRACTIVE_MODEL", False)
    p = _p()
    out = p.predict_granular([(10000.0, 22.0, 0.0)], load_ton=20.0, arac_yasi=5)
    assert out.factors_used.get("model") != "tractive"
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Delegasyon** (`predict_granular` başına, `effective_load` hesabından sonra):

```python
        from app.config import settings
        if settings.USE_SEGMENT_TRACTIVE_MODEL:
            total_mass = (
                self.vehicle.empty_weight_kg
                + self.vehicle.trailer_empty_weight_kg
                + (effective_load * 1000)
            )
            return self.predict_segment_tractive(
                segments, total_mass_kg=total_mass,
                arac_yasi=kwargs.get("arac_yasi", 5),
                silent_outlier_log=kwargs.get("silent_outlier_log", False),
            )
```

- [ ] **Step 4:** Run → 2 passed. Mevcut `test_physics_fuel_predictor.py` flag-off olduğu için yeşil kalmalı.
- [ ] **Step 5:** Commit: `feat(physics): predict_granular flag açıkken tractive'e delege eder`

---

### Task 4: segment_simulator flag yolu

**Files:** Modify `app/core/ml/segment_simulator.py`; Test `app/tests/unit/test_ml/test_segment_simulator*.py` (varsa) + yeni.

- [ ] **Step 1:** `simulate_segment` flag açıkken `predict_segment_tractive` çağırsın (tek segment, total_mass hesapla). Mevcut `predict_granular` çağrısı zaten flag ile delege olduğundan (Task 3) **ek değişiklik gerekmeyebilir** — doğrula: `simulate_segment` `predict_granular` kullanıyorsa otomatik delege olur. Kullanmıyorsa flag dalını ekle.
Run: `bash -c "cd /app && python -m pytest app/tests/unit/test_ml/ -q"` (regresyon).
- [ ] **Step 2:** Flag açık snapshot testi: sentetik 3-segment rota, `simulate_route` çıktısı `model=tractive` izini taşır (predict_granular delege).
- [ ] **Step 3:** Commit: `feat(physics): segment_simulator tractive delegasyonu doğrulandı`

---

### Task 5: Kalibrasyon scripti + sabit fit

**Files:** Create `scripts/calibrate_physics.py`; Modify `app/config.py` (fitted defaults); Test `app/tests/unit/test_ml/test_physics_calibration.py`.

- [ ] **Step 1: Kalibrasyon scripti** — `predict_segment_tractive`'i düz-yol sentetik rotada (≈80 km/h, çeşitli yük) koşup `C_flat(payload)=25.1+0.473·(payload−2.6)` ile ICCT 33.1'e fit et. `BSFC` + `PHYSICS_PARASITIC_KW`'i intercept için ayarla (trailer_rr=0.00738 → slope sabit). Çıktı: önerilen sabitler + fiziksel bant kontrolü.

```python
# scripts/calibrate_physics.py — düz-yol intercept fit
from app.core.ml.physics_fuel_predictor import PhysicsBasedFuelPredictor

def flat_consumption(bsfc, parasitic_kw, payload_t, v_kmh=80.0, km=100.0):
    import app.config as cfg
    cfg.settings.PHYSICS_ENGINE_BSFC = bsfc
    cfg.settings.PHYSICS_PARASITIC_KW = parasitic_kw
    p = PhysicsBasedFuelPredictor()
    m = 8000 + 6500 + payload_t * 1000
    out = p.predict_segment_tractive([(km * 1000, v_kmh / 3.6, 0.0)], total_mass_kg=m)
    return out.consumption_l_100km

def target(payload_t):  # DAF/ICCT
    return 25.1 + 0.473 * (payload_t - 2.6)

# grid/bisection: bsfc∈[0.40,0.46], parasitic∈[3,10] → min Σ(model−target)² over payload 5..25t
# en iyi (bsfc, parasitic) yazdır + slope kontrol (0.45-0.50) + bant guard
```

- [ ] **Step 2:** Scripti koş, en iyi `(BSFC, PARASITIC_KW)` al. Fiziksel bant: BSFC 0.40-0.46, parasitic 3-10 kW. **Overfit guard:** bant dışıysa DURDUR (model yanlış).
Run: `bash -c "cd /app && python -m scripts.calibrate_physics"`
- [ ] **Step 3:** Fitted değerleri `config.py` default'larına yaz (Task 1'deki placeholder'ları güncelle).
- [ ] **Step 4: Kalibrasyon testi** (`test_physics_calibration.py`): flag açık, 12t/18t/25t düz → `C_flat` literatür ±%5; slope 0.45-0.50.
- [ ] **Step 5:** Run → pass. Task 2 Step 4 slope testini tekrar koş (hâlâ yeşil).
- [ ] **Step 6:** Commit: `feat(physics): tractive sabitleri DAF/ICCT'ye kalibre (BSFC+parazit intercept)`

---

### Task 6: Hız annotation veri akışı

**Files:** Inspect/Modify `app/core/services/route_simulator.py`, `app/core/services/segment_resampler.py`, `app/core/services/sefer_fuel_estimator.py` (persist), `app/core/ml/segment_simulator.py` (`_effective_speed_kmh`).

- [ ] **Step 1:** İzle — `route_segments.maxspeed_kmh`/`traffic_speed_kmh` neden 0? `bash -c "cd /app && python -c '...resampler maxspeed taşıyor mu...'"` ile Mapbox→resample→SegmentInput→persist zincirini kontrol et. ("unknown"→None mı, persist 0 default mı?)
- [ ] **Step 2:** `_effective_speed_kmh` öncelik zinciri: `traffic_speed_kmh` (canlı) > `maxspeed_kmh` (kural, TIR cap'li) > road-class default. Test: traffic verilince onu kullanır.
- [ ] **Step 3:** Persist'te `traffic_speed_kmh`/`congestion` gerçekten yazıldığını sağla (estimator `_persist`). Coverage log: segment başına `speed_source`.
- [ ] **Step 4:** Test (deterministik, mock segment): traffic dolu → drag traffic hızıyla; boş → maxspeed; o da boş → road-class.
- [ ] **Step 5:** ruff+mypy; Commit: `feat(routing): segment hız önceliği traffic>maxspeed>road-class + persist`

---

### Task 7: Regresyon + gate'ler

- [ ] **Step 1:** Full unit suite (flag **kapalı** = davranış değişmemeli):
Run: `bash -c "cd /app && python -m pytest -m 'unit or not integration' --ignore=tests/integration --ignore=app/tests/integration -q -p no:cacheprovider"`
Expected: pre-değişiklik sayısı (6406 passed civarı), 0 fail.
- [ ] **Step 2:** ruff `app` temiz; mypy `app` temiz.
- [ ] **Step 3:** Commit (varsa stale-test fix): `test(physics): tractive regresyon yeşil`

---

### Task 8: p51 e2e validasyon (quota-aware)

- [ ] **Step 1:** Backend'e değişen dosyaları `docker cp` (config, physics, segment_simulator, route_simulator) + restart (CLAUDE.md docker pattern) VEYA `up -d --build backend`.
- [ ] **Step 2:** `USE_SEGMENT_TRACTIVE_MODEL=true` env ile p51 koş (Open-Meteo daily quota reset sonrası):
Run: `docker compose exec -e PYTHONIOENCODING=utf-8 -e P51_PACE_SECONDS=90 -e USE_SEGMENT_TRACTIVE_MODEL=true backend python -m scripts.p51_real_world_validation`
Expected: koşul-nötr **≥9/10 GREEN** (KON-AKS dahil — base-level düzeldi), sanity 10/10, eğimli rotalarda (IST-BOL/IST-ANK/IST-IZM) GREEN regresyonu YOK. elevation_coverage=100% (quota varsa).
- [ ] **Step 3:** Sonuç raporu: `docs/superpowers/specs/2026-06-14-segment-tractive-sonuc.md` (gerçek tablo + önce/sonra).
- [ ] **Step 4:** KON-AKS hâlâ RED ise: base kalibrasyonu yetersiz → `calibrate_physics` parasitic/BSFC yeniden fit (bant içinde); overfit YAPMA — fiziksel bant dışına çıkıyorsa modeli sorgula, raporla.

---

### Task 9: Rollout + merge

- [ ] **Step 1:** Validasyon GREEN ise `USE_SEGMENT_TRACTIVE_MODEL` default `True` (config) + docker-compose backend+worker env.
- [ ] **Step 2:** ML ensemble physics-member değişti → yeniden eğitim tetikle / not düş (`prediction.backfill` + ensemble retrain).
- [ ] **Step 3:** main'e ff-merge. `GET /admin/fuel-accuracy` ile geçiş izleme (coverage + MAPE).
- [ ] **Step 4:** Memory güncelle: [[sefer-fuel-estimator]] + [[prod-readiness-audit-series]] + [[route-segment-simulation]].

---

## Self-Review

- **Spec kapsaması:** §3.1 tractive motor → Task 2; §3.3 birleştirme → Task 3-4; §3.2/§3.4 kalibrasyon → Task 1+5; §3.5 hız akışı → Task 6; §5 test → Task 2-7; §6 rollout → Task 8-9. ✅
- **Placeholder:** Task 1 config default'ları Task 5'te fitted değerle güncellenir (script çıktısı — plan fit prosedürünü + guard'ı veriyor, sahte sayı değil). Task 6 Step 1 bir izleme adımı (kaynak koda bağlı, komutla).
- **İsim/tip tutarlılığı:** `predict_segment_tractive(segments, total_mass_kg, arac_yasi)` Task 2'de tanımlı, Task 3'te çağrılır; `USE_SEGMENT_TRACTIVE_MODEL`/`PHYSICS_*` Task 1'de tanımlı, Task 2/3/5'te kullanılır; `FuelPrediction` mevcut dataclass (energy_breakdown={} boş geçilebilir — tüketici kontrol et: `prediction_service`/`segment_simulator` energy_breakdown kullanıyorsa Task 2'de doldur).
- **Overfit guard:** sabitler fiziksel bantta (BSFC 0.40-0.46, parasitic 3-10kW); KON-AKS RED kalırsa band düşürme YOK, model sorgulanır.
- **Rollback:** flag default false → tüm değişiklik davranış-nötr merge edilir; flip ayrı + izlenir.
- **Risk:** physics tüm tahminleri + ML ensemble'ı etkiler → flag + ayrı validasyon + retrain notu. energy_breakdown={} tüketici kırabilir → Task 2'de tüketici kontrolü şart.
