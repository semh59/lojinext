# Modül: anomaly

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

İstatistiksel + ML hibrit anomali tespiti (Z-Score/IQR + IsolationForest +
LightGBM), anomali eylem akışı (acknowledge/resolve), DBSCAN anomali
kümeleme, yakıt hırsızlığı şüphe sınıflandırması (kural-bazlı) + soruşturma
yaşam döngüsü (open→assigned→investigating→resolved/closed) + OPS Telegram
alarmı, manuel sefer atama düzeltmesi (attribution override). `anomalies`,
`fuel_investigations` tablolarının tek sahibi.

NE YAPMAZ: fraud AYRI modül DEĞİL — fuel-theft/investigation/attribution
zaten tek iş akışı, anomaly ile birleşik (görev dosyası kapsam notu).
Sefer/rota-bazlı gerçek tahmin pipeline'ı (prediction_ml), driver koçluk
prompt kurgusu (driver — bu modülün `get_anomaly_detector()`'ını public.py
üzerinden çağırır), fuel/trip'in kendi `ANOMALY_DETECTED` event publish'i
(bkz. events.py — bu modül o event'in ne sahibi ne subscriber'ı).

## Public API (public.py imzaları)

```python
# Ana hibrit dedektör (sınıf istisnası, aşağıya bkz.)
AnomalyDetector, get_anomaly_detector() -> AnomalyDetector
  .detect_consumption_anomalies(consumptions, arac_id=None, use_ml=True) -> list[AnomalyResult]
  .detect_trip_anomaly_elite(trip_data: dict) -> AnomalyResult | None
  .detect_anomaly_hybrid(trip_data: dict, use_ml=True) -> AnomalyResult | None
  .save_anomalies(anomalies: list[AnomalyResult]) -> int
  .get_recent_anomalies(days=30, severity=None, status=None, sofor_id=None) -> list[dict]
  .acknowledge(anomaly_id, user_id) -> dict
  .resolve(anomaly_id, user_id, notes=None) -> dict
  .train_lgb_classifier() -> dict
  .predict_severity_lgb(value, expected_value, deviation_pct) -> SeverityEnum
  .save_model(filepath) / .load_model(filepath) / .get_detector_status() -> dict
AnomalyResult, AnomalyType, SeverityEnum        # dataclass/enum'lar

# Kümeleme (saf fonksiyon)
cluster_anomalies(rows: list[dict], *, eps=0.6, min_samples=2) -> list[dict]

# Yakıt hırsızlığı sınıflandırıcı (sınıf istisnası, aşağıya bkz.)
FuelTheftClassifier, get_fuel_theft_classifier() -> FuelTheftClassifier
  .classify(anomaly: dict) -> TheftClassification
  .classify_batch(anomalies: list[dict]) -> list[TheftClassification]

# Attribution override (B.1: free function — sınıf YOK)
override_attribution(sefer_id, arac_id=None, sofor_id=None, reason="", uow=None) -> bool
bulk_override_attribution(overrides: list) -> int   # dead-code (endpoint kendi loop'unu kullanıyor, bkz. aşağı)

# Şemalar
TheftClassification, InvestigationCreate, InvestigationUpdate, InvestigationResponse,
PatternMatch, SuspicionLevel, AttributionOverrideRequest, AttributionOverrideResponse

# Repository (uow.anomaly_repo / uow.investigation_repo)
AnomalyRepository        # infrastructure/anomaly_repository.py — anomalies CRUD
InvestigationRepository  # infrastructure/investigation_repository.py — fuel_investigations + FOR-UPDATE akışı

# Investigation orkestrasyonu (application/manage_investigations.py — db: AsyncSession alır, kendi UoW açmaz, bkz. FOR-UPDATE notu)
get_patterns(db, days, min_count, limit) -> list[dict]
list_investigations(db, days, limit, status=None, suspicion_level=None, assigned_to_user_id=None) -> list[dict]
get_investigation_detail(db, inv_id) -> dict | None
create_investigation(db, *, anomaly_id, initial_notes, creator_id) -> (dict, TheftClassification, Anomaly)
update_investigation(db, inv_id, payload) -> (dict, old_value_dict, new_value_dict)
soft_delete_investigation(db, inv_id) -> bool   # True = zaten kapalıydı (idempotent)
reclassify_investigation(db, inv_id) -> TheftClassification
resolve_alarm_context(db, anomaly) -> (plaka, sofor_adi)

# Filo analiz dashboard (application/get_fleet_insights.py — trip/fleet repo okur, bkz. aşağıdaki not)
get_fleet_insights(days: int) -> dict
```

**B.1 sınıf istisnaları** (`AttributionService` KALDIRILDI, önceki 6 dalgadaki
karar aynı gerekçeyle — free function'a çevrildi; kalan 3 sınıf `RouteSimulator`/
`LokasyonHydrator`/`DriverPerformanceML` ile aynı sınıftan istisna):

- **`AnomalyDetector`** — sklearn `IsolationForest` + LightGBM `LGBMClassifier`
  + `lgb_trained` bayrağı gerçek mutable eğitilmiş-model state'i taşır,
  istatistiksel+ML tek-cohesive-pipeline'dır. **Dürüst not (2026-07-15
  dalga-8-sonrası dedektif denetimi):** bu gerekçe yalnız tespit
  metodlarını (`detect_consumption_anomalies`/`train_lgb_classifier`/
  `save_model`/`load_model` vb.) kapsar — `acknowledge`/`resolve` (satır
  ~560-610) ML/istatistik pipeline'ıyla İLGİSİZ, basit UoW CRUD-güncelleme
  metodları ve B.1'in "tek sorumluluk" ilkesini teknik olarak ihlal eder.
  Bu karışım taşımadan ÖNCE de vardı (`app/core/services/anomaly_detector.py`
  içinde aynı şekildeydi, `git show 1a8d77a:...` ile doğrulandı) — dalga 8'in
  ürettiği YENİ bir ihlal değil, taşınan mimari borç. Ayrı bir dosyaya
  (`application/acknowledge_anomaly.py` gibi) bölünmesi bu dalganın
  kapsamı dışında bırakıldı (saf mekanik taşıma kararına sadık kalmak için);
  ileride ele alınacak bir B.1 temizlik kalemi olarak burada işaretlendi.
- **`AnomalyDetectionService`** — constructor-injected cache handle
  (`get_cache_manager()`) + iki alt-metodun (detect/analyze) birlikte
  tutarlı bir hesap hattı oluşturması. `AnomalyDetector`'dan FARKLI, bilinçli
  ikinci bir alt-sistem (docstring'de "two anomaly subsystems exist
  intentionally" notu) — Z-Score/IQR yolu, DB yazmaz. Tek tüketicisi
  (`app/core/services/analiz_service.py`) dalga 11'de dead-code olarak
  silindi; bu sınıf artık hiçbir prod koddan çağrılmıyor (kendi testleri
  hariç) — sınıf hâlâ burada duruyor çünkü silinmesi bu modülün kapsamı
  dışında bir karar (anomaly dalgasının kendi görev dosyası bunu kapsamıyor).
- **`FuelTheftClassifier`** — stateless, tek-pipeline (skor bileşenlerini
  birlikte hesaplayan tek akış), `get_fuel_theft_classifier()` singleton.

## KRİTİK İNVARYANT — FOR-UPDATE satır kilidi (görev dosyası madde 6)

`infrastructure/investigation_repository.py` içinde
`lock_investigation_for_update` + `update_investigation_fields` +
`close_investigation` AYNI dosyada, taşımadan önceki sırayla duruyor.
Bu üçü BÖLÜNMEMELİ: `SELECT ... FOR UPDATE` bir transaction sınırı — 2026-07-01
prod-grade denetimi P1'in (dalga 4 madde 18) düzelttiği TOCTOU koruması
(`PATCH /admin/investigations/{id}`, eşzamanlı iki istek) bu üç metodun
aynı repository sınıfında, aynı sırada kalmasına bağımlı. Regresyon testi:
`app/tests/integration/test_investigations_patch_race.py` — gerçek eşzamanlı
2-task senaryosu, taşıma sonrası da yeşil (351 anomaly-özgü test dahil,
bkz. dalga 8 doğrulama notu STATUS.md'de).

## Çapraz-modül bağımlılıklar (geçici, dokümante)

- **driver (taşındı, dalga 5)**: `DriverCoachingEngine`
  (`v2/modules/driver/application/generate_coaching.py`) `v2.modules.anomaly.public.get_anomaly_detector()`
  kullanır — public.py üzerinden doğru sınır geçişi (dalga 8'de düzeltildi,
  önceden `app.core.services.anomaly_detector`'a bağımlıydı).
- ✅ **ÇÖZÜLDÜ (dalga 11, 2026-07-16 + temizlik 2026-07-17)** — eski
  `app/core/services/analiz_service.py` `v2.modules.anomaly.public.
  get_anomaly_detection_service()`'in tek prod tüketicisiydi; dedektif
  denetiminde hiçbir yerden çağrılmadığı bulundu (dead code) ve silindi
  (dalga 11). `AnomalyDetectionService`/`get_anomaly_detection_service()`
  kendisi de (`application/detect_statistical_anomaly.py`) o zaman kendi
  test dosyaları dışında çağıranı kalmamıştı — kullanıcı onayıyla tamamen
  silindi (2026-07-17, bkz. `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md`
  madde 4). Bu, `app.core.entities`'in Pydantic `AnomalyResult`/
  `AnomalyType`/`SeverityEnum`'ı ile `detect_anomaly.py`'nin kendi
  (canlı, ML-augmented) dataclass eşadlılarının çakışma riskini de ortadan
  kaldırdı — artık modülde tek bir `AnomalyResult`/`AnomalyType`/
  `SeverityEnum` seti yaşıyor (`detect_anomaly.py`'deki dataclass'lar).
- **trip/fuel → notification (anomaly DEĞİL)**: `EventType.ANOMALY_DETECTED`
  fuel modülü (`add_yakit.py`) ve henüz taşınmamış trip modülü
  (`sefer_analiz_service.py`) tarafından publish edilir, notification
  tarafından consume edilir — bu modülün SAHİBİ OLMADIĞI bir event (bkz.
  `events.py`).
- **theft_tasks 5-modül raw-SQL erişimi** (`infrastructure/theft_tasks.py`,
  Celery beat `theft.daily_pattern_scan` 03:00 UTC): `fuel_investigations`+
  `anomalies` (bu modül) + `seferler`+`soforler`+`araclar` (trip/driver/fleet)
  tablolarına doğrudan raw-SQL erişiyor — FAZ2'de trip/driver/fleet
  şemalarına SELECT-only grant gerektirecek (STATUS.md'de not düşüldü,
  taşımadan önce de böyleydi, regresyon değil).
- **`bulk_create_alerts`/`get_recent_unread_alerts` `analiz_repo.py`'de
  KALDI** — bunlar `anomalies` tablosuna insight-alert yazan/okuyan AYRI bir
  yol (task dosyasının 15 metodluk taşıma listesinde yok), analytics_executive'in
  kendi sorumluluğu.
- 🔴 **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu — dalga 8 taşımasının kendisinde, `TASKS/bug-route-layer-bypasses-application.md`
  sınıfının belgelenmeden yaşayan bir tekrarı)**: `api/investigation_routes.py`'nin
  TÜM 7 endpoint'i (`get_patterns`/`list_investigations`/`get_investigation`/
  `create_investigation`/`update_investigation`/`soft_delete_investigation`/
  `reclassify_investigation`) `application/`'ı hiç kullanmıyor, doğrudan
  `get_investigation_repo(db)`/`get_anomaly_repo(session=db)` çağırıyordu —
  yeni `application/manage_investigations.py`'ye taşındı. FOR-UPDATE
  invaryantı korunuyor: bu dosyadaki fonksiyonlar kendi `UnitOfWork`'ünü
  AÇMAZ, çağıranın (route'un) `SessionDep` session'ını parametre alır —
  `lock_investigation_for_update` + `update_investigation_fields` +
  `db.commit()` aynı transaction'da kalır (aksi halde kilit anlamsızlaşır).
  Ayrıca `api/anomaly_routes.py::get_fleet_insights` de aynı ihlali
  taşıyordu (`UnitOfWork()` doğrudan route'ta) — `application/get_fleet_insights.py`'ye
  taşındı; bu endpoint `sefer_repo`/`arac_repo` (trip/fleet) okuyor,
  `anomalies`/`fuel_investigations` ile ilgisi yok — muhtemelen tarihsel
  yanlış-yerleştirme, taşıma kapsamına alınmadı (ayrı bir modül-sahipliği
  kararı gerektirir), sadece B.1 katman ihlali düzeltildi. `attribution_routes.py`'nin
  `UnitOfWork(db)` inşası İSTİSNA — connection-pool-leak fix'inin
  (`TASKS/bug-connection-pool-leak-under-load.md`) gerektirdiği bilinçli
  desen, `override_attribution` zaten application katmanı fonksiyonu,
  dokunulmadı. Mekanik taşıma, davranış değişikliği yok.

## Bilinen açık notlar

- Bu modülün kendi CRUD event'i YOK — diğer modüllerdeki ANOMALY_ADDED/
  UPDATED/DELETED tipi decorator-only ölü-kod deseninden FARKLI olarak burada
  o desen bile yok (`AnomalyDetector.save_anomalies`/`acknowledge`/`resolve`
  hiçbir `@publishes`/`event_bus.publish` çağrısı içermiyor).
- `bulk_override_attribution` free function public.py'de export ediliyor ama
  hiçbir prod route çağırmıyor — `attribution_routes.py`'nin bulk endpoint'i
  kendi loop'unu tek-tek `override_attribution(...)` ile çağırıyor (eski
  `AttributionService.bulk_override`'ın da aynı şekilde endpoint tarafından
  kullanılmadığı, sadece testlerde egzersiz edildiği doğrulandı — taşımadan
  önce de böyleydi, regresyon değil).
- `public.py`/`events.py`/`schemas.py` var (diğer dalgalardan farklı olarak
  bu modülde şema dosyası tek dosyada — investigation+attribution şemaları
  küçük ve iç içe geçmiş, ayrı dosyalara bölünmedi).

## Yayınladığı / dinlediği event'ler (events.py)

Bu modül ne publisher ne subscriber'dır (bkz. `events.py` docstring'i):
`ANOMALY_DETECTED` event'ini fuel modülünün rolling-outlier check'i
yayınlar, notification modülü tüketir — anomaly yalnız adı geçen domain
sahibidir. `acknowledge`/`resolve` akışları event yayınlamaz (senkron
DB-güncellemesi).

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-anomaly` kontratı: `application/`
diğer modüllerin yalnız `public`/`events`'ini import edebilir
(2026-07-18'den beri KEPT — `generate_cluster_insight.py`'nin
`ai_assistant.infrastructure.llm.groq_client` doğrudan importu aynı gün
`ai_assistant.public.GroqService`'e çevrildi). Diğer modüller bu modüle
yalnız `v2.modules.anomaly.public` üzerinden erişir (driver'ın
`get_anomaly_detector` kullanımı zaten böyle).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`anomali`=anomaly, `sapma`=deviation, `şiddet`=severity,
`soruşturma`=investigation, `hırsızlık`=theft, `kümeleme`=clustering,
`eşik`=threshold, `onayla (ack)`=acknowledge, `çöz`=resolve,
`kayıp ilişkilendirme`=loss attribution.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_anomaly_detector_coverage.py` /
  `test_anomaly_detector_more.py` — dedektör birimi (gerçek DB'li
  `db_session` + dar mock).
- `app/tests/unit/test_fuel_theft_classifier.py`,
  `test_anomaly_clustering.py`, `test_anomaly_cluster_task.py`,
  `test_theft_alarm_text.py`, `test_theft_pattern_pii.py`,
  `app/tests/unit/test_workers/test_theft_tasks.py` — sınıflandırıcı/
  kümeleme/Celery task testleri.
- `app/tests/api/test_investigations_coverage.py` / `_more.py` +
  `app/tests/integration/test_investigations_crud.py` /
  `test_investigations_patch_race.py` (FOR-UPDATE concurrency invariantı,
  0-mock) — endpoint + yarış senaryoları (`TEST_DATABASE_URL` zorunlu).
