# Modül: prediction_ml

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Yakıt tüketimi tahmin ML pipeline'ı: 5-model ensemble (fizik + LightGBM +
XGBoost + GradientBoosting + RandomForest), fizik-tabanlı fallback motoru,
Kalman online-learning tahmincisi, ARIMA zaman serisi tahmini, model
eğitim/versiyonlama, admin ML endpoint'leri, XAI açıklama (`/predictions/explain`).
`egitim_kuyrugu`, `model_versiyonlar`, `prediction_results` tablolarının tek
sahibi.

NE YAPMAZ: sefer create yolundaki asıl Phase 4-5 tahmin akışı
(`app/core/services/sefer_fuel_estimator.py::SeferFuelEstimator` — bu modülün
`adjustment_factors`/`vehicle_health_adjustment` fonksiyonlarını + `route_simulation`u
kullanır ama kendisi trip/sefer domain'inde kalır, henüz v2'ye taşınmadı),
sefer/rota CRUD'u (trip), rota geometrisi/segment simülasyonu
(route_simulation — bu modül yalnız `PhysicsBasedFuelPredictor`/`VehicleSpecs`'i
sağlar, segment üretmez).

## Dosya envanteri düzeltmesi (task dosyası eksikti)

`TASKS/modules/prediction-ml.md`'nin 35-dosyalık envanteri bir dosyayı
atlıyordu: `app/core/ml/route_similarity.py` (`encode_route`/`cosine_similarity`/
`find_similar_trips` — ai_assistant'ın `plan_trip.py`'si kullanıyor) hiç listede
değildi ama taşındı (`domain/route_similarity.py`). Gerçek envanter 36 dosya.
`app/scripts/benchmark.py` ise task dosyasında listeli olmasına rağmen
**taşınmadı** — içeriği gerçekte ML/prediction ile hiç ilgili değil (generic
DB/fleet/reports perf benchmark script'i, `v2.modules.fleet.public`/
`v2.modules.reports.public` kullanıyor); task dosyasının bu satırı bariz stale.

## FAZ0 kararı — `model_manager.py` SİLİNDİ (dead code, kullanıcı onaylı)

`app/core/ml/model_manager.py`'nin `ModelManager.save_version()`'ı `model_versions`
tablosuna (Türkçesiz, `s` ile biten) ham SQL yazıyordu — bu tablo **alembic
geçmişinde hiç var olmadı** (`alembic/legacy_versions_archive/
ef8abc3ede67_017_ml_versions_queue.py` incelendi: gerçek tablo hep
`model_versiyonlar` idi, yalnızca bir INDEX adı kısa süre `ix_model_versions_arac_id`
taşıyıp sonra `ix_model_versiyonlar_arac_id`'ye yeniden adlandırıldı). Bu
yüzden `ModelManager.save_version()` her çağrıldığında gerçek bir DB'ye karşı
`relation "model_versions" does not exist` ile patlıyordu; 3 çağıran sitesi
(`ensemble_service.py`'nin `_persist_fallback_model`/`train_for_vehicle`/
`train_general_model`'i) bunu `except Exception` ile yutuyordu — sessizce
başarısız, hiç fark edilmeyen dead write path.

Ayrıca `scripts/init_ml_db.py` (deprecated rogue script, kendi docstring'i
"model_versions is managed by Alembic migrations, bu script'i çalıştırma"
diyordu) ham SQL ile `model_versions` tablosunu manuel oluşturuyordu — şema
canlı `model_versiyonlar`'dan eksikti (`mape`/`feature_schema_hash`/
`training_data_hash`/`physics_version` yoktu). Kullanıcı onayıyla (2026-07-18):
`model_manager.py` + `scripts/init_ml_db.py` + `app/tests/unit/test_ml/
test_model_manager_coverage.py` TAMAMEN SİLİNDİ.

**Gerçek yazım yolu bağlandı**: `MLService.register_model_version()`
(`application/ml_service.py`) — `model_versiyonlar`'a doğru ORM INSERT'i
yapan metot — daha önce **hiçbir prod kod tarafından çağrılmıyordu**
(`GET /admin/ml/versions/{arac_id}` her zaman boş dönüyordu). Kullanıcı
onayıyla: `ensemble_service.py`'ye yeni bir `_register_model_version()` free
function eklendi (kendi `UnitOfWork` açıp `MLService.register_model_version()`
çağırıyor, versiyon numarasını `model_versiyon_repo.get_latest_version()`'dan
hesaplıyor) ve 3 eski `model_manager` çağıran sitesi buna yönlendirildi.
Bu fonksiyon kendi try/except'i içinde TÜM hataları yutar (asla raise etmez) —
bu, `train_general_model`'daki gerçek bir davranış hatasını da düzeltti:
eskiden `save_version()` istisnası dış `try` bloğuna düşüp fonksiyonun geri
kalanını (legacy kayıt, disk serialize, heavy/medium/light class-model döngüsü)
iptal ediyordu; artık versiyon-kayıt hatası izole, geri kalan akışı etkilemiyor.

## `app/core/ml/predictors/` paketi SİLİNDİ (dead code, ikinci bulgu)

`app/core/ml/predictors/ensemble_predictor.py`'nin `EnsemblePredictor`
(inference-only wrapper sınıfı) — grep ile doğrulandı: repo genelinde
**sıfır prod çağıran** (yalnız kendi özel test dosyası `test_phase4_ml_predictors_
training_split.py` tarafından egzersiz ediliyordu). Gerçek production tahmin
yolu her zaman `EnsemblePredictorService`/`EnsembleFuelPredictor`'ı
(`ensemble_service.py`/`ensemble_core.py`) doğrudan kullanıyor, bu "predictors"
paketinin "training kodu inference'a hiç sızmaz" mimari hedefi hiçbir çağıran
tarafından benimsenmemiş. `app/core/ml/predictors/{__init__.py,
ensemble_predictor.py}` + `app/tests/unit/test_phase4_ml_predictors_
training_split.py` SİLİNDİ (task dosyasının 35-dosya listesinde vardı ama
gerçek kanıt "taşı" değil "sil" gerektiriyordu).

## Public API (public.py imzaları)

```python
# Ana tahmin servisi (sınıf istisnası, aşağıya bkz.)
PredictionService, get_prediction_service() -> PredictionService
    .predict_consumption(arac_id, mesafe_km, ton=0.0, ..., route_analysis=None,
                          _arac_obj=None, _sofor_obj=None, _dorse_obj=None) -> dict
    .explain_consumption(arac_id, mesafe_km, ...) -> dict          # XAI
    .train_xgboost_model(arac_id, user_id=None) -> dict

# Ensemble motoru (sınıf istisnası)
EnsemblePredictorService, get_ensemble_service() -> EnsemblePredictorService
    .train_for_vehicle(arac_id) -> dict
    .train_general_model() -> dict                # + heavy/medium/light class fallback
    .predict_consumption(arac_id, mesafe_km, ton, ..., uow=None) -> dict
    .predict_batch(requests: list[dict]) -> list[dict]
    .get_predictor(arac_id) -> EnsembleFuelPredictor
EnsembleFuelPredictor, PredictionResult, SecurityError
LIGHTGBM_AVAILABLE, SKLEARN_AVAILABLE, XGBOOST_AVAILABLE

# Fizik motoru (saf, I/O yok)
PhysicsBasedFuelPredictor, VehicleSpecs, RouteConditions, FuelPrediction
HybridFuelPredictor          # fizik + öğrenen düzeltme faktörü (test-only kullanım, bkz. gotcha)

# Rota benzerliği (ai_assistant plan_trip.py kullanır)
find_similar_trips(route_analysis, mesafe_km, limit=5) -> list[dict]

# Hava/bakım çarpanları (sefer_fuel_estimator.py + analytics_executive kullanır)
weather_temperature_factor(temp_c) -> float
weather_wind_factor(wind_speed_kmh, wind_bearing_deg=None, segment_bearing_deg=None) -> float
weather_precipitation_factor(precip_mm, snowfall_cm=None) -> float
combine_factors(driver=1.0, vehicle_age=1.0, maintenance=1.0, ...) -> float
HealthInput, HealthResult
fetch_health_input(uow, arac_id) -> HealthInput
fetch_health_input_batch(uow, arac_ids) -> dict[int, HealthInput]
compute_maintenance_factor(inp, *, now=None, no_history_factor=1.05) -> HealthResult
apply_maintenance_factor(payload, factor, reason=None) -> dict

# Zaman serisi tahmini
TimeSeriesService, get_time_series_service() -> TimeSeriesService
ARIMATimeSeriesPredictor, get_arima_predictor(), get_time_series_predictor(), is_lstm_available()

# Event handler'lar (main.py lifespan'de bağlanır)
ModelTrainingHandler, get_model_training_handler()
PhysicsRecalculationHandler, get_physics_handler()

# Backfill (Phase 4.4 — timeout nedeniyle tahminisiz kalan seferleri doldurur)
PredictionBackfillService

# ML predictor warm-up (main.py lifespan'de çağrılır — dalga 17, ilk modül-startup hook'u)
schedule_predictor_warmup() -> asyncio.Task[None]

# Offline eğitim facade (Celery weekly retrain kullanır)
Trainer
```

**Önemli**: `MLService` (`application/ml_service.py`) public.py'de export
EDİLMEZ — yalnız modülün kendi `api/admin_ml.py`'si ve `ensemble_service.py`
(`_register_model_version` üzerinden) kullanır, dış modül tüketicisi yok.

**Dalga 17 (platform-infra) eklentisi**: `infrastructure/ml_probe.py`
(`MLProbe`/`get_ml_probe`) `app/infrastructure/monitoring/ml_probe.py`'den
taşındı — tek çağıranı `ensemble_service.py`/`ensemble_core.py` idi
(fallback-oranı takibi tamamen bu modüle özgü). `public.py`'de export
EDİLMEZ (yalnız modülün kendi içinde kullanılıyor). `ensemble_core.py`
(domain) bunu import ettiği için `module-cross-domain-infra-independence`/
`module-internal-layers` kontratlarına 1 satır `ignore_imports` eklendi
(telemetri side-effect'i, gerçek domain iş kuralı değil — `.importlinter`'da
gerekçeli). Kendi `v2.modules.platform_infra.monitoring.models`/`emit`
bağımlılığı sürüyor (platform_infra'nın monitoring alt sistemi — dalga
17'nin commit 5'inde `app/infrastructure/monitoring/`'den oraya taşındı).

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar)

Diğer modüllerdeki `RouteSimulator`/`LokasyonHydrator`/`DriverCoachingEngine`
ile aynı gerekçe kategorisi: gerçek mutable eğitilmiş-model state'i veya
constructor-injected client bağımlılığı, CRUD-benzeri bir servis değiller.

1. **`PredictionService`** (`application/prediction_service.py`) —
   `container.py`'de lazy singleton (`self._prediction_service`), constructor
   `WeatherService()`/`get_ensemble_service()` client'larını tutuyor —
   `AIService`/`SmartAIService` ile aynı DI-singleton gerekçesi.
2. **`EnsemblePredictorService`** (`application/ensemble_service.py`) — 20-slot
   LRU predictor cache (`OrderedDict` + `threading.Lock`) + disk-persist
   state, gerçek mutable state.
3. **`EnsembleFuelPredictor`** (`domain/ensemble_core.py`) — sklearn/xgboost/
   lightgbm model nesnelerini + `self.weights`/`self.is_trained` mutable
   eğitim state'ini tutan model wrapper'ı.
4. **`PhysicsBasedFuelPredictor`**/`HybridFuelPredictor` (`domain/physics_fuel_predictor.py`) —
   `HybridFuelPredictor` `self.historical_errors`/`self.correction_factor`
   online-öğrenen state tutuyor.
5. **`KalmanFuelEstimator`**/`KalmanEstimatorService` (`domain/kalman_estimator.py`) —
   Kalman filtresi devlet-uzayı (`state`, `P` kovaryans matrisi) gerçek mutable
   state; `KalmanEstimatorService` 200-slot LRU cache.
6. **`LightGBMFuelPredictor`**/`LightGBMAnomalyClassifier` (`domain/lightgbm_predictor.py`) —
   model wrapper, `self.model`/`self.is_trained` state.
7. **`ARIMATimeSeriesPredictor`**/legacy `TimeSeriesPredictor`+`FuelConsumptionLSTM`
   (`domain/time_series_predictor.py`) — model wrapper.
8. **`Trainer`** (`application/trainer.py`) — thin facade, `EnsemblePredictorService`'i
   lazy import eden tek-pipeline sınıf (offline eğitim, inference path'e hiç
   girmez — Phase 4.0 mimari kararı, `training`/`predictors` paket ayrımından
   kalan tek gerçek parça; `predictors` paketinin kendisi dead code olarak
   silindi ama bu ayrım kararının facade'ı hâlâ geçerli).
9. **`ModelTrainingHandler`**/`PhysicsRecalculationHandler` (`application/`) —
   event-bus subscriber'ları, `self.event_bus`/`self._cache` state.
10. **`TimeSeriesService`** (`application/time_series_service.py`) —
    `container.py`'de lazy singleton, `self.engine` (AdvancedTSEngine) state.
11. **`MLService`** (`application/ml_service.py`) — class-level `_locks:
    Dict[int, asyncio.Lock]` (araç başına eğitim kilidi), gerçek paylaşılan
    mutable state; use-case fonksiyonlarına bölünemez çünkü kilit sözlüğü
    tüm çağrılar arasında paylaşılmalı. `public.py`'de export EDİLMEZ (bkz.
    yukarı not) — yalnız `api/admin_ml.py` ve `ensemble_service.py`
    (`_register_model_version` üzerinden) kullanır.
12. **`MLBenchmark`**/**`ABTestFramework`**/**`EnsembleBenchmark`**
    (`domain/benchmark.py`) — istatistiksel karşılaştırma state'i tutan
    framework sınıfları (çalışan benchmark/A-B-test sonuçlarını internal
    listede biriktirir). Denetimde doğrulandı: repo genelinde sıfır prod
    çağıranı var (yalnız `test_ml_reliability.py`/`test_ml_audit.py`
    tarafından egzersiz ediliyor) — `lightgbm_predictor.py`/
    `kalman_estimator.py`/`HybridFuelPredictor` ile aynı "taşındı ama
    wire edilmedi" kategorisinde, aşağıdaki gotcha'ya bkz.

## Domain katmanı bölünmesi — task dosyasının §5 kümelemesi kısmen düzeltildi

`predict_consumption` (eskiden CC=50, 257 satır) ZATEN yardımcı metotlara
bölünmüştü (bu modülün taşınmasından önce, `app/services/prediction_service.py`'de).
Task dosyası §5'in önerdiği 4 küme (fizik/ensemble/response/route-ratio)
uygulandı ama task dosyasının kümelemesi kök CLAUDE.md'nin domain-saflık
kuralını (domain/ I/O-suz OLMALI + application'a bağımlı OLMAMALI) 2 yerde
ihlal ediyordu — bunlar düzeltildi, gerekçe her dosyanın kendi docstring'inde:

- **`domain/route_ratios.py`**: `sum_segment_km`/`derive_route_ratios`/
  `normalize_route_analysis` — task dosyasıyla birebir eşleşiyor, saf.
- **`domain/physics_model.py`**: `build_vehicle_specs`/`run_physics_model`/
  `build_base_factors` — task dosyasının "fizik kümesi" listesinden
  `_run_physics_fallback` HARİÇ tutuldu (o, `response_builder`'ı çağırıyor —
  domain uygulama katmanına bağımlı olamaz). `_run_physics_fallback`
  `application/prediction_service.py`'de instance metodu olarak KALDI.
- **`application/response_builder.py`**: `build_explanation_summary`/
  `normalize_confidence_band`/`extract_confidence_score`/
  `build_prediction_response` — task dosyasıyla eşleşiyor, saf fonksiyonlar
  (application'da olmaları I/O-suz olmadıkları anlamına gelmiyor, sadece
  domain/ için gereken "asla application'a bağımlı olma" kısıtı yok).
- **`application/ensemble_orchestration.py`** (task dosyası bunu
  `domain/ensemble.py` olarak öneriyordu — İSİM VE KATMAN DEĞİŞTİ):
  `run_ensemble_prediction`/`process_ensemble_result`. `run_ensemble_prediction`
  gerçek DB I/O yapıyor (`UnitOfWork` açıp `EnsemblePredictorService.
  predict_consumption`'ı çağırıyor) — domain/ I/O-suz olmalı kuralını ihlal
  ederdi. `process_ensemble_result` de `response_builder`'a bağımlı. İkisi de
  application/'da kaldı.

`_build_sefer_dict` task dosyasının listesinde yoktu, `PredictionService`
instance metodu olarak kaldı (I/O yok ama orkestrasyona sıkı bağlı,
ayrıştırma gerekçesi yoktu — "gerekçesiz split yasak").

`ensemble_core.py::fit` (CC=61, en yüksek kompleksite) task dosyasının
kararı gereği bu FAZ'da BÖLÜNMEDİ (baseline'da kaldı).

## Prefetch-N+1 koruması korundu

`predict_consumption` `_arac_obj`/`_sofor_obj`/`_dorse_obj` (N+1 optimizasyonu,
`bulk_add_sefer`'ın batch yolu için) parametrelerini KABUL EDER; `_build_sefer_dict`
bunlar yoksa DB'den yükler. Bu "varsa kullan, yoksa yükle" dalı taşıma
sırasında birebir korundu — mekanik taşıma, davranış değişikliği yok.

## Yayınladığı / dinlediği event'ler (events.py)

Kendi `EventType`'ını tanımlamaz. **Dinler**: `YAKIT_ADDED`/`SEFER_ADDED`
(`ModelTrainingHandler` — her 5 yeni kayıtta arka planda otomatik retrain
tetikler), `SEFER_UPDATED` (`PhysicsRecalculationHandler` — manuel override
sonrası fizik tabanlı tüketimi yeniden hesaplar, `trigger="physics_recalculation"`
ile sonsuz döngüyü engeller). **Yayınlar**: `CACHE_INVALIDATED` (retrain
sonrası), `SEFER_UPDATED` (fizik yeniden hesaplama sonrası). Her iki handler
da `app/main.py` lifespan startup'ında bağlanır
(`get_model_training_handler().setup()` / `get_physics_handler().register()`).

## Şema & tablo sahipliği

`egitim_kuyrugu` (`EgitimKuyrugu` — `MLTrainingRepository`), `model_versiyonlar`
(`ModelVersiyon` — `ModelVersiyonRepository`, kolonlar: `arac_id`, `versiyon`,
`veri_sayisi`, `r2_skoru`, `mae`, `mape`, `rmse`, `model_dosya_yolu`,
`kullanilan_ozellikler` JSON, `egitim_tarihi`), `prediction_results`
(`PredictionResult` — async prediction-queue task sonuçları,
`workers/tasks/prediction_tasks.py`).

Ayrıca `analytics_executive.infrastructure.executive_read_models.AnalizRepository`'nin
3 ML-parametre metodu (`save_model_params`/`get_model_params`/
`get_daily_summary_for_ml`) — bu modülün ML akışı için kullanılıyor ama
FİZİKSEL OLARAK `analytics_executive`'te KALDI (taşınmadı; analytics_executive'in
kendi task dosyası madde 4'te bu taşımayı işaretlemişti ama analytics_executive
dalgası bunu tamamlamamıştı — dedektif denetiminde bulunan tutarsızlık).
Kullanıcı kararı: bu FAZ'da yalnız **dead** `get_training_seferler` (sıfır
prod çağıran, grep ile doğrulandı) SİLİNDİ; diğer 3 metot davranış
değişikliği riski nedeniyle `analytics_executive`'te bırakıldı (taşımak ayrı
bir refactor — çapraz-modül repo-metod taşıma, bu dalganın "mekanik taşıma"
kapsamının ötesinde). `ensemble_service.py`/`kalman_estimator.py`
`v2.modules.analytics_executive.public.get_analiz_repo()` üzerinden bu 3
metodu çağırmaya devam ediyor.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **fleet (taşındı)**: `ensemble_service.py` → `v2.modules.fleet.public.
  {get_arac_repo, get_dorse_repo}` (en yoğun bağımlılık, task dosyasının
  bağlaşıklık karnesinde "prediction_ml→fleet 7" olarak işaretli).
- **driver (taşındı)**: `ensemble_service.py`/`prediction_service.py` →
  `v2.modules.driver.public.get_driver_stats`/`classify_route` (şoför
  katsayısı hesaplaması).
- **analytics_executive (taşındı)**: `ensemble_service.py`/`kalman_estimator.py` →
  `v2.modules.analytics_executive.public.get_analiz_repo` (legacy model-param
  kaydı + Kalman state persist).
- **ai_assistant (taşındı, ters yön)**: `prediction_service.py::_log_prediction_to_ai`
  → `v2.modules.ai_assistant.public.get_smart_ai().teach()` (best-effort arka
  plan görevi). `infrastructure/prediction_tasks.py` →
  `v2.modules.ai_assistant.public.{LLMMessage, get_llm_client}`.
- **auth_rbac (taşındı)**: `api/admin_ml.py` → `v2.modules.auth_rbac.public.require_yetki`.
- **trip (taşınmadı, dalga 14, geçici — TERS YÖN)**: `app/api/v1/endpoints/trips.py`
  (trip modülünün kendisi) → bu modülün `public.PredictionService` +
  `v2.modules.ai_assistant.public.TripPlannerEngine`'i kullanır.
  `app/core/services/sefer_write_service.py` (4 site) →
  `public.get_prediction_service`. Bu modülün `ensemble_service.py`'si de
  ters yönde `app.database.repositories.sefer_repo.get_sefer_repo` (trip'in
  henüz taşınmamış repo'su) kullanır — trip taşınınca `uow.sefer_repo`
  deseni gözden geçirilecek.
- **anomaly (taşındı, ters yön)**: `detect_anomaly.py` → `public.get_prediction_service`
  (istatistiksel anomali karşılaştırması gerçek ML tahminine dayanır).
- **route_simulation (taşındı, ters yön)**: `get_route_details.py` →
  `public.get_prediction_service`; `simulate_route.py`/`create_route_simulation.py`/
  `domain/segment_simulator.py` → `public.VehicleSpecs`/`PhysicsBasedFuelPredictor`/
  `FuelPrediction` (fizik motorunu tüketir, kendi segment simülasyonunu sarar).
- **location (taşındı, ters yön)**: `analyze_location_route.py` →
  `public.PhysicsBasedFuelPredictor`/`RouteConditions` (baseline yakıt tahmini,
  güzergah kartı gösterimi için).
- **ai_assistant (taşındı, ters yön #2)**: `plan_trip.py` →
  `public.find_similar_trips` (Feature C sefer planlama, benzer geçmiş
  seferleri bulma).

## Modüle özel iş kuralları & gotcha'lar

- **`register_model_version` artık gerçekten çağrılıyor** (yukarıdaki FAZ0
  bölümüne bkz.) — `GET /admin/ml/versions/{arac_id}` artık boş dönmeyecek
  (bir eğitim tamamlandıktan sonra).
- **Multi-worker LRU sorunu (kapsam dışı, MEMORY §4.1)**: `EnsemblePredictorService`
  20-slot LRU her worker process'inde AYRI (Redis/shared cache değil) — 4
  worker × 20 slot = 80 farklı predictor instance olabilir, aynı arac_id
  farklı worker'larda farklı (veya hiç) cache'lenmiş olabilir. Bu modülün
  SINIRLARI İÇİNDE ama mimari sorun değil, kaynak-yönetimi sorunu — bu FAZ'ın
  kapsamı dışında, ayrı performans işi olarak bırakıldı (task dosyası §4'te
  zaten böyle işaretlenmişti).
- **Warm-up hook dalga 17'de taşındı**: `app/main.py`'nin ML predictor
  warm-up hook'u (`_warmup_all_predictors`) `application/model_warmup.py`'ye
  taşındı — `schedule_predictor_warmup()` task'ı yaratıp döndürür,
  `main.py`'nin lifespan'ı onu kendi `_bg_tasks` GC-koruma setine ekleyip
  shutdown'da drain eder (task bookkeeping'i bilerek main.py'de bırakıldı,
  modüle sızdırılmadı). Bu, projenin İLK `<modül>.startup()`-tarzı hook'u —
  daha önce hiçbir migrated modül bu deseni uygulamıyordu.
- **`get_prediction_service()` container'a delege edecek şekilde düzeltildi
  (dalga 17)**: eskiden bağımsız kendi `_prediction_service` modül-global'ini
  tutuyordu (diğer 6 property'nin — `anomaly_detector`/`time_series_service`/
  `license_service`/`ai_service`/`smart_ai_service`/`export_service` —
  hepsinin izlediği "modülün kendi getter'ı container'a delege eder"
  deseninden sapıyordu, dosyanın kendi docstring'i "CREATED_BY: app/core/
  container.py" zaten bunu öngörüyordu). Artık `get_container().
  prediction_service`'e delege ediyor — `admin_platform/health_service.py`'nin
  okuduğu instance ile gerçek serving instance'ı artık AYNI nesne.
- **`_calculate_training_hash`** (`ensemble_service.py`) artık hiçbir çağıran
  tarafından KULLANILMIYOR (eskiden `model_manager.save_version`'ın
  `training_data_hash` kwarg'ına besleniyordu — `ModelVersiyon` ORM modelinde
  böyle bir kolon yok). Metot SİLİNMEDİ: kendi dedike test paketi var
  (`test_ensemble_service_coverage.py`'nin `_calculate_training_hash` testleri,
  hash uniqueness/stability davranışını doğruluyor) — gelecekteki data-drift
  tespiti için tutulan kasıtlı bir yardımcı olarak değerlendirildi, "ölü kod"
  silme kararının kapsamına (sıfır test yatırımı olan kod) girmiyor.
- **`lightgbm_predictor.py`/`kalman_estimator.py`/`HybridFuelPredictor`/
  legacy LSTM sınıfları/`domain/benchmark.py` (`MLBenchmark`/
  `ABTestFramework`/`EnsembleBenchmark`) — prod çağıranı yok, ama
  silinmedi**: grep ile doğrulandı, bu kalemlerin (özellikle
  `KalmanEstimatorService`/`get_kalman_service` ve `benchmark.py`'nin 3
  sınıfı) hiçbir endpoint/container/servis tarafından wire edilmediği
  görüldü. `time_series_predictor.py`'nin legacy LSTM sınıfları için
  modülün kendi docstring'i zaten "yalnızca test fixture'ları için
  tutuluyor" diyerek bunu KASITLI olarak dokümante ediyor. Diğerleri
  (`lightgbm_predictor.py`, `kalman_estimator.py`, `HybridFuelPredictor`,
  `benchmark.py`) için böyle bir doküman yok — ama bu modülün taşıma görevi
  (task dosyası) bunları "sil" değil "taşı" olarak işaretliyor ve dead-code
  temizliği bu dalgada yalnız FAZ0'ın açıkça flag'lediği kalemlerle
  (model_manager, predictors/, get_training_seferler) sınırlı tutuldu —
  genişletilmiş bir dead-code avı bu taşımanın kapsamı dışında bırakıldı.
  Not olarak düşürülüyor: gelecekte ayrı bir "kullanılmayan ML sınıfları"
  denetimi açılabilir.
- **`app/core/ml/ensemble_predictor.py` shim'i kaldırıldı**: DALGA 13'ün
  ilk commit'i (`9e47ce8`) bu dosyayı 19 tüketici (2 script + test
  dosyaları) için geçici bir backward-compat shim olarak bırakmıştı — kök
  `CLAUDE.md`'nin "migrated modüllerin eski app/ dosyaları silinir, shim
  bırakılmaz" kuralına aykırıydı. Takip denetiminde bulunup düzeltildi: tüm
  19 çağıran gerçek `v2.modules.prediction_ml.{public,domain.ensemble_core,
  application.ensemble_service}` yoluna güncellendi, shim dosyası ve artık
  boşalan `app/core/ml/` dizini silindi.
- **`Sefer yakıt tahmini (Phase 4-5 SeferFuelEstimator)`** kök CLAUDE.md'de
  dokümante — bu modülün `adjustment_factors`/`vehicle_health_adjustment`
  fonksiyonlarını kullanır ama estimator'ın kendisi (`app/core/services/
  sefer_fuel_estimator.py`) trip domain'inde kalıyor, bu modüle taşınmadı.

## İzin verilen / yasak import'lar (import-linter özeti)

`public-surface-only-prediction_ml` kontratı: `application/` diğer 12
modülün yalnız `public`/`events`'ini import edebilir. `12 modulun domain/
infrastructure katmanlari birbirinden bagimsiz` kontratına `prediction_ml.domain`/
`prediction_ml.infrastructure` eklendi. `Modul-ici katman sirasi` kontratına
(`api → application → infrastructure → domain`) `v2.modules.prediction_ml`
container olarak eklendi; `infrastructure.** -> application.**` ignore
girişi gerekti (`scheduler_task.py`/`prediction_backfill_tasks.py` `Trainer`/
`PredictionBackfillService`'i application'dan import ediyor — Celery
task'ları için standart desen, diğer modüllerde de aynı ignore var, örn.
`anomaly.infrastructure.** -> anomaly.application.**`).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`tahmin`=prediction, `tüketim`=consumption, `eğitim`=training,
`versiyon`=version, `güven aralığı`=confidence interval/band,
`güven skoru`=confidence score, `sapma`=deviation, `bakım`=maintenance,
`yaş faktörü`=age factor, `mevsim faktörü`=seasonal factor,
`rota analizi`=route analysis, `zorluk`=difficulty, `boş sefer`=empty trip,
`geri dönüş`=fallback, `topluluk (model)`=ensemble.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_ml/` (20+ dosya) — domain/application birim testleri,
  import path'leri `v2.modules.prediction_ml.{domain,application}.*`'e
  güncellendi. `test_model_manager_coverage.py`/`test_phase4_ml_predictors_
  training_split.py` silindi (test ettikleri kod silindi).
- `test_ensemble_service_coverage.py`/`test_ensemble_service_more.py` —
  eski `app.core.ml.model_manager.get_model_manager` patch hedefleri
  `v2.modules.prediction_ml.application.ensemble_service._register_model_version`'a
  çevrildi (yeni fonksiyon kendi try/except'i içinde tüm hataları yuttuğu
  için "manager exception → hâlâ devam eder" testleri artık `_register_model_version`'ı
  mock'layıp doğrudan davranışı doğruluyor).
- `test_prediction_service_coverage.py`/`test_prediction_service_more.py` —
  `PredictionService._build_explanation_summary` gibi eski staticmethod
  çağrıları `response_builder.build_explanation_summary` gibi free-function
  çağrılarına çevrildi; `patch.object(svc, "_run_physics_model", ...)` gibi
  eski instance-method patch'leri `patch("...prediction_service.run_physics_model", ...)`
  module-level patch'lerine çevrildi (fonksiyonlar artık `prediction_service.py`'ye
  import edilen serbest fonksiyonlar).
- `app/tests/unit/test_services/test_prediction_service_contracts.py` —
  `PhysicsBasedFuelPredictor` patch hedefi `v2.modules.prediction_ml.domain.
  physics_model.PhysicsBasedFuelPredictor`'a taşındı (artık `run_physics_model`
  içinde kullanılıyor, `prediction_service.py`'de değil).
- `app/tests/api/test_admin_ml.py`, `test_admin_predictions.py`,
  `test_predictions*.py` — endpoint testleri (`TEST_DATABASE_URL` zorunlu).
- Free-function `unittest.mock.patch` hedefi HER ZAMAN **tüketen modül**
  (`v2.modules.prediction_ml.application.prediction_service.run_physics_model`
  gibi) — kaynak modül değil (aynı gotcha, diğer 12 modülle tutarlı).
