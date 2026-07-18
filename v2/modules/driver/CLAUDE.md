# Modül: driver

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Şoför CRUD'u, hibrit skor (`calculate_hybrid_score`) + XAI kırılımı, güzergah
tipi bazlı performans profili, kapsamlı 0-100 değerlendirme karnesi
(`SoforDegerlendirme`), LightGBM tabanlı ML skor tahmini, Feature A koçluk
motoru (Groq LLM + anomali analizi → Türkçe öneriler), şoför-sefer PDF
raporu, 3 Celery task (weekly coaching digest, coaching effectiveness
evaluation, performance score). `soforler`, `sofor_ad_soyad_trigram`,
`sofor_adaptasyon`, `coaching_deliveries` tablolarının tek sahibi.

NE YAPMAZ: sefer/rota CRUD'u (trip, henüz taşınmadı — driver bu modüle
`uow.sefer_repo` üzerinden geçici bağımlı), asıl yakıt tahmin ML pipeline'ı
(prediction_ml), RAG indeksleme (ai_assistant — `rag_sync_service.py` driver
event'lerine subscribe olur ama ayrı modülde kalır).

## Public API (public.py imzaları)

```python
# Driver CRUD
add_sofor(ad_soyad, telefon="", ehliyet_sinifi="E", ise_baslama=None,
          manual_score=1.0, notlar="", telegram_id=None) -> int
bulk_add_sofor(data_list: list) -> int
update_sofor(sofor_id: int, **kwargs) -> bool
update_score(sofor_id: int, score: float) -> bool
delete_sofor(sofor_id: int) -> bool                 # soft delete
bulk_delete(ids: list[int]) -> dict
get_by_id(sofor_id: int, include_inactive=False) -> dict | None
get_all_paged(skip=0, limit=100, aktif_only=True, **filters) -> dict
get_driver_fleet_stats() -> dict                    # {total, active}
get_performance_details(sofor_id: int) -> dict      # safety/eco/compliance/total

# Score / route profile
calculate_hybrid_score(sofor_id, manual_score, uow=None) -> float          # 0.1-2.0 ML correction factor
get_score_breakdown_sofor(sofor_id, uow=None) -> dict                      # XAI kırılımı
get_route_profile_sofor(sofor_id, min_trips_for_best=5, uow=None) -> dict  # 4 güzergah tipi profili

# Coaching delivery / etki ölçümü (Feature A.5)
record_coaching_delivery(sofor_id, *, channel, insight_category, message, sent_by_user_id) -> int | None
get_coaching_effectiveness_stats(days: int) -> dict

# Analytics / ranking (application/driver_stats.py — 2026-07-18'de domain/'den taşındı: UoW/DB erişimi var, domain saf olmalı)
get_driver_stats(sofor_id=None, baslangic=None, bitis=None,
                  include_elite_score=True, uow=None) -> list[DriverStats]
compare_drivers(sofor_ids=None, uow=None) -> dict
get_driver_trend(sofor_id, window=10, uow=None) -> dict
get_route_performance(sofor_id, uow=None) -> list[dict]
calculate_elite_performance_score(sofor_id, baslangic=None, bitis=None, uow=None) -> float | None  # 0-100, ML-deviation
calculate_performance_score(ort_tuketim, filo_ort, sefer_sayisi) -> float  # 0-100, fleet-comparison (reports modülü kullanır)
calculate_trend(values: list[float]) -> str

# Evaluation — kapsamlı 0-100 karne (application/evaluation.py — 2026-07-18'de domain/'den taşındı, aynı gerekçe)
evaluate_driver(sofor_id, pre_metrics=None, pre_filo_ortalama=None,
                 include_routes=True, uow=None) -> SoforDegerlendirme | None
get_all_evaluations(include_routes=False, uow=None) -> list[SoforDegerlendirme]
get_rankings(uow=None) -> dict
SoforDegerlendirme, GuzergahPerformans, DereceEnum, TrendEnum

# ML (domain/performance_ml.py — sınıf, bkz. aşağıdaki istisna notu)
DriverPerformanceML, DriverScorePrediction, get_driver_performance_ml()

# Route-type classification (application/route_profile.py — 2026-07-18'de domain/'den taşındı: get_driver_route_coefficient kendi UnitOfWork'ünü açıyor)
ROUTE_TYPES, classify_route(route_analysis: dict) -> str
get_driver_route_coefficient(sofor_id, route_type, min_trips=5) -> float

# Coaching (Feature A — sınıf, bkz. aşağıdaki istisna notu)
DriverCoachingEngine, get_driver_coaching_engine()

# PDF export (infrastructure/pdf_export.py — sınıf, bkz. aşağıdaki istisna notu)
SoforSeferPDFService

# Repository
SoforRepository, get_sofor_repo(session=None)

# Schemas
SoforCreate, SoforUpdate, SoforResponse, DriverPerformanceSchema,
DriverScoreBreakdownSchema, DriverRouteProfileSchema,
CoachingCategory, CoachingPriority, CoachingSource, CoachingInsightItem,
CoachingInsightsResponse, SendCoachingRequest, SendCoachingResponse,
CoachingEffectivenessResponse
```

**Önemli**: `SoforService`/`SoforAnalizService`/`SoforDegerlendirmeService`
sınıfları YOK. Her use-case bağımsız bir fonksiyon (B.1, location/
notification/fleet/fuel ile aynı karar). Pre-migration constructor-injected
repo parametreleri (`SoforService.__init__(repo=...)`,
`SoforAnalizService.__init__(uow=...)`, `SoforDegerlendirmeService.__init__
(analiz_repo=..., sofor_repo=...)`) dead weight değildi (bazı metotlar
gerçekten okuyordu — `get_score_breakdown`/`get_route_profile` session-aware
`self.repo` gerektiriyordu) — bu davranış korundu: her free function
opsiyonel `uow: UnitOfWork | None = None` parametresi alır, verilirse
`uow.<repo>` (aynı transaction), verilmezse modül-seviyeli singleton repo
kullanır (`get_sofor_repo()` / `get_analiz_repo()` / `get_sefer_repo()`).

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar — 3 adet)

Location/route_simulation'daki `RouteSimulator`/`LokasyonHydrator` ile aynı
gerekçe: tek-cohesive-pipeline + constructor-injected client bağımlılığı
veya mutable eğitilmiş model durumu — CRUD-benzeri bir servis değiller.

1. **`DriverCoachingEngine`** (`application/generate_coaching.py`) — `__init__`
   `groq`/`anomaly_detector` client'larını enjekte eder, tek giriş noktası
   `generate_coaching()`. CRUD parçalanması anlamsız (tek pipeline: skor+profil
   çek → anomali kategorize et → LLM prompt kur → parse/fallback).
2. **`DriverPerformanceML`** (`domain/performance_ml.py`) — LightGBM
   regressor/ranker'ı `self.regressor`/`self.ranker` olarak tutan, `train()`/
   `train_ranker()` sonrası `self.is_trained`/`self.feature_importance` mutable
   state'i olan bir model wrapper'ı. Free function'a bölünseydi bu state'i
   modül-global değişkenlere taşımak gerekirdi — daha kötü bir tasarım.
3. **`SoforSeferPDFService`** (`infrastructure/pdf_export.py`) — `PDFReportGenerator`
   alt sınıfı (`v2.modules.reports.public`'ten import — reports dalga 10'da
   taşındı, 2026-07-18'de import public'e çevrildi), template-method builder
   pattern (`olustur()` → `_build_pdf()`).

## Yayınladığı / dinlediği event'ler (events.py)

✅ **GÜNCEL (2026-07-16 dedektif denetiminde düzeltildi — bu bölüm
`e55edf7`'den [2026-07-16, "gerçekten bağla"] sonra hâlâ eski hâliyle
kalmıştı):** `SOFOR_ADDED`/`SOFOR_UPDATED`/`SOFOR_DELETED` artık GERÇEKTEN
çalışıyor — `add_sofor`/`update_sofor`/`delete_sofor` her biri commit'ten
önce aynı transaction'da `save_outbox_event(...)` çağırıyor, Celery
beat'in 60s outbox-relay task'ı bunu gerçek `event_bus.publish(...)`'e
çeviriyor. `app/core/ai/rag_sync_service.py`'nin `SOFOR_ADDED`/
`SOFOR_UPDATED` subscriber'ı (`rag.index_driver`) artık gerçekten
tetikleniyor — bu bölüm eskiden "ölü kod, hiçbir yerde publish
çağrılmıyor" diyordu, bu artık YANLIŞ.

## Şema & tablo sahipliği

`soforler`, `sofor_ad_soyad_trigram` (Tier E madde 26 — `ad_soyad`/`telefon`
PII şifreli, arama trigram tablosu üzerinden yapılır), `sofor_adaptasyon`,
`coaching_deliveries` (Feature A.5 — koçluk etki ölçümü).

**Bilinen istisna (pre-existing, dalga 5'ten ÖNCE de vardı, taşımayla
değişmedi):** eski `app/core/services/import_service.py` dalga 9'da
`v2/modules/import_excel/`'e taşınırken silindi (artık hiç yok) — aynı
bypass deseni artık `v2/modules/import_excel/application/execute_import.py`'de
yaşıyor: `surucu` dalı `soforler`/`sofor_ad_soyad_trigram`'a `infrastructure/
repository.py`'yi bypass eden HAM SQL `INSERT`/`DELETE` yazıyor (bulk Excel
import performansı için, PII şifreleme + trigram). Dedektif denetiminde
(2026-07-14) bulundu, gerçek bir tablo-sahipliği istisnası ama davranış
değişikliği gerektirmediği için dalga 5'te dokunulmadı; dalga 9'un
(import_excel taşıması) kabul kriterlerinde de yoktu, o da kapsam dışı
bıraktı (bkz. `v2/modules/import_excel/CLAUDE.md`'nin kendi notu) — ayrı
bir bug-fix görevi olarak açılabilir (driver repository'sinin bulk-insert
path'ini kullanacak şekilde refactor).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **trip (senkron, henüz taşınmadı)**: `get_route_profile_sofor`
  `uow.sefer_repo.get_driver_trips_with_route_analysis(...)` çağırır;
  `get_driver_stats`/`calculate_elite_performance_score`
  `sefer_repo.get_recent_trips_batch(...)`/`sefer_repo.get_all(...)` çağırır.
  `sefer_repo.py`'deki 6 driver-özel sorgu (`get_by_sofor_id`,
  `get_with_route_analysis`, `get_driver_trips_with_route_analysis`,
  `get_driver_trips_by_route_type`, `get_recent_trips_batch`,
  `_search_driver_ids_by_name`) **BU DALGADA TAŞINMADI** — trip dalga 14'te
  taşınacak (`infrastructure/driver_trip_queries.py` olarak driver
  modülüne gelecek, `TASKS/modules/driver.md` §4'te zaten not düşülmüştü).
  Ayrıca `sefer_write_service.py` (trip) `uow.sofor_repo.get_by_id`/
  `get_by_ids`/`get_all` çağırır (aktif şoför kontrolü, N+1 önleme).
- **prediction_ml (taşındı, dalga 13)**: `application/driver_stats.py`
  `_calc_elite_from_trips`/`calculate_elite_performance_score`
  `v2.modules.prediction_ml.public.get_prediction_service()` çağırır
  (ML tahmin ile gerçek tüketim farkına dayalı elite skor).
- **analytics_executive (taşındı, dalga 11)**: `application/driver_stats.py`
  ve `application/evaluation.py` `v2.modules.analytics_executive.public.
  get_analiz_repo()` çağırır (2026-07-18: public'e çevrildi, dosyalar da
  domain/'den application/'a taşındı). Bulk driver metrikleri (`get_bulk_driver_metrics`) dalga 11'de bu
  modülün kendi `infrastructure/driver_metrics_queries.py`'sine taşındı;
  yanındaki ölü `get_driver_comparison` 2026-07-18 temizliğinde silindi.
- **ai_assistant (taşındı, dalga 12)**: `DriverCoachingEngine`
  `v2.modules.ai_assistant.public.get_groq_service()` çağırır (LLM
  inference; 2026-07-18: lazy import — public üst-düzeyde import edilirse
  ai_assistant→driver.public→bu dosya döngüsü oluşur).
- **anomaly (taşındı, dalga 8)**: `DriverCoachingEngine`
  `v2.modules.anomaly.public.get_anomaly_detector()` kullanır (public.py
  üzerinden — driver→anomaly bağımlılığı artık modül sınırını doğru geçiyor).
- **reports (taşındı, dalga 10)**: `SoforSeferPDFService`
  `v2.modules.reports.public.PDFReportGenerator`'dan miras alır
  (2026-07-18: public'e çevrildi). `reports/application/generate_vehicle_report.py`
  `calculate_performance_score`'u (bu modülün `domain/report_metrics.py`'si)
  driver raporlarında kullanır.
- ~~fuel (tersine)~~: `fuel/domain/consumption_prediction.py` 2026-07-18
  ölü-kod temizliğinde silindi — bu ters-yön bağımlılık artık yok.

## Modüle özel iş kuralları & gotcha'lar

- ✅ **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu, `TASKS/bug-route-layer-bypasses-application.md` sınıfı, aynı
  gün ikinci tur)** — `api/driver_routes.py`'nin `get_driver_fleet_stats`
  (ham SQL COUNT), `read_sofor`/`get_driver_performance`/
  `get_driver_score_breakdown`/`get_driver_route_profile`/`delete_sofor`
  (`db.get(Sofor,...)` doğrudan ORM) handler'ları ve
  `api/coaching_routes.py`'nin `get_coaching_insights`/`send_coaching`
  (`db.get(Sofor,...)`) + `send_coaching`'in **route içinde inline
  `UnitOfWork()` açıp `CoachingDelivery` INSERT'i yapması** (gerçek bir
  yazma işlemi route'ta yaşıyordu) + `get_coaching_effectiveness`'in ham
  SQL agregasyonu — hepsi `application/`'ı atlıyordu. Düzeltme:
  `list_sofor.py::get_driver_fleet_stats`/`get_by_id(include_inactive=...)`,
  yeni `record_coaching_delivery.py`, yeni `get_coaching_effectiveness.py`.
  `get_by_id`'ye `include_inactive` parametresi eklendi (varsayılan
  `False` mevcut çağıranları etkilemez); tekil-GET/PUT/DELETE handler'ları
  `include_inactive=True` ile çağırıyor (eski `db.get()` ham PK lookup
  davranışını koruyarak — fleet dalgasındaki `AracEntity` regresyonundan
  ders alınarak, `SoforResponse`'a dict doğrudan geçiriliyor, ekstra
  entity-dönüşüm katmanı YOK). Mekanik taşıma, davranış değişikliği yok.
- **PII şifreleme + trigram arama** (`infrastructure/repository.py`):
  `ad_soyad`/`telefon` DB'de şifreli (`EncryptedPII`); `get_all`/`count_all`
  bu yüzden DB-seviyeli `ILIKE`/`ORDER BY` YAPAMAZ — filtrelenmiş küçük
  seti (driver-roster boyutu, sefer/yakıt hacmi değil) Python'da
  arar/sıralar. `_sync_trigrams` her `add`/`update`'te
  `sofor_ad_soyad_trigram` çocuk tablosunu senkron tutar (substring arama).
- **İsim-benzersizliği kilidi modül-seviyeli** (`application/_locks.py::SOFOR_WRITE_LOCK`,
  `add_sofor`/`update_sofor`/`update_score` paylaşır): pre-migration
  `SoforService.__init__`'in `self._lock`'ı her per-request servis
  instantiation'ında (`get_sofor_service()` dependency) yeniden
  yaratılıyordu — concurrent request'ler arasında fiilen etkisizdi. Fleet
  dalga 3'teki TOCTOU plaka-kilidi bulgusuyla aynı sınıf; free function'a
  geçişte modül-seviyeli tek `asyncio.Lock()`'a taşındı — **davranışsal
  iyileştirme**, regresyon değil. Gerçek guard hâlâ DB
  `UNIQUE(ad_soyad_bidx)` constraint'i (kaybeden concurrent insert
  `IntegrityError` alır, API 400'e map'ler).
- **Hibrit skor ≠ elite skor ≠ fleet-comparison skoru** (3 farklı ölçek,
  karıştırılmamalı — her fonksiyonun docstring'inde açık):
  `calculate_hybrid_score` (0.1-2.0, ML tahmin düzeltme faktörü, `soforler.score`
  kolonunda saklanır), `_calc_elite_from_trips`/`calculate_elite_performance_score`
  (0-100, baseline 75 = ML tahminiyle tam eşleşme, analytics dashboard'da
  `performans_puani`), `calculate_performance_score` (0-100, baseline 50 =
  filo ortalaması, reports modülü kullanır — analytics dashboard'da
  KULLANILMAZ).
- **Coaching PII politikası** (`application/generate_coaching.py::_build_prompt`):
  Groq LLM'e giden prompt'ta isim/plaka/telegram_id/sofor_id KESİNLİKLE
  yok — sadece anonim sayısal/kategorik özet. `get_anomaly_detector().get_recent_anomalies(...,
  sofor_id=sofor_id)` filtresi başka şoförün anomali örüntülerinin prompt'a
  sızmasını önler (geçmişte bulunan HATA 5 — LOJINEXT_v7 raporu).
- **Weekly digest — özel Celery limitleri** (`infrastructure/coaching_tasks.py`):
  global `task_time_limit=90s` 500 şoför × ~2s Groq LLM için yetersiz;
  `coaching.weekly_digest` kendi `soft_time_limit=3600`/`time_limit=3900`
  taşır. `SoftTimeLimitExceeded` yakalanıp partial sonuç (`timeout_partial=True`)
  döner.

## ✅ ÇÖZÜLDÜ (2026-07-18) — orphan `driver.calculate_performance_score` Celery task'ı SİLİNDİ

`infrastructure/driver_tasks.py` hiçbir zaman Celery worker'a kayıtlı
olmamış, hiçbir `.delay()`/`.apply_async()` çağıranı olmayan orphan bir
task taşıyordu (dalga 5 bulgusu). Kullanıcının "ölü kod yasak" kararıyla
dosya + testi (`test_workers/test_driver_tasks.py`) silindi
(celery_app.py'deki not güncellendi).

## ✅ ÇÖZÜLDÜ (2026-07-18) — `evaluation.py::_add_guzergah_performansi` session'sız singleton bug'ı

2026-07-14 denetim bulgusuydu: fonksiyon session'sız modül-singleton
`get_sofor_repo()`'yu çağırıyordu — `get_guzergah_performansi` raw-SQL
olduğu için her çağrı "Database session not initialized" ile patlayıp
geniş `except` tarafından yutuluyordu; karnenin `guzergah_performansi`/
`en_iyi_guzergah`/`en_kotu_guzergah` alanları hiç dolmuyordu (sessiz
özellik kaybı, taşımadan önce de bozuktu). Düzeltme (9206e3f'teki
score-breakdown fix'iyle aynı desen): `evaluate_driver` artık `uow`'u
alt-fonksiyona geçiriyor; `uow.sofor_repo` varsa onu, yoksa kendi
`UnitOfWork`'ünü kullanıyor. Testler sahte-`uow` desenine güncellendi
(`test_sofor_degerlendirme_more.py`). Dosya aynı düzeltme turunda
`application/evaluation.py`'ye taşındı.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_sofor_service*.py`,
  `test_sofor_analiz_service*.py` — use-case fonksiyon testleri (0-mock:
  gerçek repo + `db_session`), sınıf-mock'tan free-function-mock desenine
  çevrildi (`v2.modules.driver.api.driver_routes.<fn>` gibi TÜKETEN modül
  patch edilir — kaynak modül değil, location/fleet/fuel'deki aynı gotcha).
- `app/tests/api/test_drivers*.py`, `test_coaching*.py` — endpoint testleri
  (`TEST_DATABASE_URL` zorunlu).
- `app/tests/unit/test_driver_coaching_engine.py` — LLM mock'lu +
  fallback-path testleri.
- Kök `tests/` klasörü de tarandı (dalga 1/4 gotcha'sı tekrarı) — driver'a
  değinen dosyalar bulunup dönüştürüldü.

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-driver` kontratı: `application/`
diğer modüllerin yalnız `public`/`events`'ini import edebilir
(2026-07-18'den beri KEPT — `generate_coaching.py`'nin groq_client
doğrudan importu `ai_assistant.public`'e çevrildi). Diğer modüller bu
modüle yalnız `v2.modules.driver.public` üzerinden erişir (container.py/
repositories/__init__.py composition-root istisnası hariç). Trip'in
`sefer_repo`'suna geçici doğrudan bağımlılık kontrat ignore'unda
dokümante (dalga 14'te çözülecek).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`şoför`=driver, `değerlendirme/karne`=evaluation/report card,
`derece`=grade, `verimlilik`=efficiency, `tutarlılık`=consistency,
`deneyim`=experience, `eğilim`=trend, `koçluk`=coaching,
`güzergah tipi`=route type, `hibrit skor`=hybrid score.
