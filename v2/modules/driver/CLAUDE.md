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

# Analytics / ranking (domain/driver_stats.py)
get_driver_stats(sofor_id=None, baslangic=None, bitis=None,
                  include_elite_score=True, uow=None) -> list[DriverStats]
compare_drivers(sofor_ids=None, uow=None) -> dict
get_driver_trend(sofor_id, window=10, uow=None) -> dict
get_route_performance(sofor_id, uow=None) -> list[dict]
calculate_elite_performance_score(sofor_id, baslangic=None, bitis=None, uow=None) -> float | None  # 0-100, ML-deviation
calculate_performance_score(ort_tuketim, filo_ort, sefer_sayisi) -> float  # 0-100, fleet-comparison (reports modülü kullanır)
calculate_trend(values: list[float]) -> str

# Evaluation — kapsamlı 0-100 karne (domain/evaluation.py)
evaluate_driver(sofor_id, pre_metrics=None, pre_filo_ortalama=None,
                 include_routes=True, uow=None) -> SoforDegerlendirme | None
get_all_evaluations(include_routes=False, uow=None) -> list[SoforDegerlendirme]
get_rankings(uow=None) -> dict
SoforDegerlendirme, GuzergahPerformans, DereceEnum, TrendEnum

# ML (domain/performance_ml.py — sınıf, bkz. aşağıdaki istisna notu)
DriverPerformanceML, DriverScorePrediction, get_driver_performance_ml()

# Route-type classification (domain/route_profile.py — zaten free function'dı)
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
   alt sınıfı (reports modülü, henüz taşınmadı — **geçici bağımlılık**),
   template-method builder pattern (`olustur()` → `_build_pdf()`).

## Yayınladığı / dinlediği event'ler (events.py)

`SOFOR_ADDED`, `SOFOR_UPDATED`, `SOFOR_DELETED` — `@publishes(...)`
decorator'ı `add_sofor`/`update_sofor`/`delete_sofor` üzerinde var ama
**repo-genelinde ölü kod** (fuel/fleet/notification/location'ın aynı
bulgusu): `publishes()` yalnızca fonksiyona `_publishes` attribute'u
ekliyor, hiçbir yerde okunmuyor; fonksiyon gövdeleri de
`event_bus.publish(...)` çağırmıyor (dalga 5'te yeniden doğrulandı: repo
genelinde `grep "publish(" | grep -i sofor` sıfır sonuç).

`app/core/ai/rag_sync_service.py` `SOFOR_ADDED`/`SOFOR_UPDATED`'a subscribe
olup RAG indeksini günceller (`rag.index_driver`) — bu subscriber de
publish hiç tetiklenmediği için pratikte etkisiz (fuel'in YAKIT_* bulgusuyla
aynı sınıf, taşımadan önce de böyleydi, regresyon değil).

## Şema & tablo sahipliği

`soforler`, `sofor_ad_soyad_trigram` (Tier E madde 26 — `ad_soyad`/`telefon`
PII şifreli, arama trigram tablosu üzerinden yapılır), `sofor_adaptasyon`,
`coaching_deliveries` (Feature A.5 — koçluk etki ölçümü).

**Bilinen istisna (pre-existing, dalga 5'ten ÖNCE de vardı, taşımayla
değişmedi):** `app/core/services/import_service.py` (import-excel modülü,
henüz taşınmadı) `soforler`/`sofor_ad_soyad_trigram`'a `infrastructure/
repository.py`'yi bypass eden HAM SQL `INSERT`/`DELETE` yazıyor (bulk Excel
import performansı için — satır ~401-408/424-427/582, `git show
f2321a1^:app/core/services/import_service.py`'de de aynı desen doğrulandı).
Dedektif denetiminde (2026-07-14) bulundu, gerçek bir tablo-sahipliği
istisnası ama davranış değişikliği gerektirmediği için bu dalgada
dokunulmadı — import-excel dalga 9'da ele alınacak (driver repository'sinin
bulk-insert path'ini kullanacak şekilde refactor edilebilir).

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
- **prediction_ml (senkron, henüz taşınmadı)**: `domain/driver_stats.py`
  `_calc_elite_from_trips`/`calculate_elite_performance_score`
  `app.services.prediction_service.get_prediction_service()` çağırır
  (ML tahmin ile gerçek tüketim farkına dayalı elite skor).
- **analytics_executive (senkron, henüz taşınmadı)**: `domain/driver_stats.py`
  ve `domain/evaluation.py` `app.database.repositories.analiz_repo.get_analiz_repo()`
  çağırır (bulk driver metrics, filo ortalaması — analytics_executive henüz
  `public.py` yayınlamadığı için doğrudan repo importu).
- **ai_assistant (senkron, henüz taşınmadı)**: `DriverCoachingEngine`
  `app.core.ai.groq_service.get_groq_service()` çağırır (LLM inference).
- **anomaly (taşındı, dalga 8)**: `DriverCoachingEngine`
  `v2.modules.anomaly.public.get_anomaly_detector()` kullanır (public.py
  üzerinden — driver→anomaly bağımlılığı artık modül sınırını doğru geçiyor).
- **reports (taşındı, dalga 10)**: `SoforSeferPDFService`
  `v2.modules.reports.infrastructure.pdf_export.PDFReportGenerator`'dan
  miras alır (public.py üzerinden değil — reports'un kendi `pdf_export.py`
  dosyasından doğrudan, `RouteSimulator`/`LokasyonHydrator` sınıf-istisnası
  desenindeki gibi). `reports/application/generate_vehicle_report.py`
  `calculate_performance_score`'u (bu modülün `domain/report_metrics.py`'si)
  driver raporlarında kullanır.
- **fuel (senkron, tersine — zaten taşınmış)**: `v2/modules/fuel/domain/consumption_prediction.py`
  `get_driver_stats`'i (eski `SoforAnalizService.get_driver_stats`) çağırıp
  şoför-bazlı tüketim düzeltme faktörü hesaplar.

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

## 🔴 Bulgu: `driver.calculate_performance_score` Celery task'ı hiç kayıtlı değildi

`infrastructure/driver_tasks.py` (eski `app/workers/tasks/driver_tasks.py`)
taşımadan ÖNCE de `app/infrastructure/background/celery_app.py`'nin
`import app.workers.tasks.*` listesinde YOKTU — Celery, task'ları modül
import edilince decorator'la kaydeder; hiç import edilmeyen bir modülün
`@celery_app.task(name="driver.calculate_performance_score")`'u worker'a
asla kaydolmaz. Sonuç: bu task prod'da **hiç çalıştırılamaz** durumdaydı
(prod kodda hiçbir `.delay()`/`.apply_async()` çağrısı da yok — tamamen
orphan). Regresyon değil, dalga 5 taşımasıyla keşfedildi; davranış
değişikliği gerektirdiği için kapsam dışı bırakıldı (import eklemek =
önceden hiç çalışmayan bir cron'u aktifleştirmek, ayrı bir karar).

## 🔴 Bulgu (dedektif denetim, 2026-07-14): `evaluation.py::_add_guzergah_performansi` — 9206e3f'in aynı sınıf ikizi bug'ı, PRE-EXISTING

`domain/evaluation.py`'deki `_add_guzergah_performansi` (satır ~279-314)
`get_sofor_repo()`'yu (modül-seviyeli, session'sız singleton) DOĞRUDAN
çağırıyor — `evaluate_driver`'ın aldığı `uow` parametresini bu alt-fonksiyona
geçirmiyor. `get_guzergah_performansi` raw-SQL bir metot, session gerektirir
→ prod'da `Database session not initialized in SoforRepository` ile patlar,
geniş bir `except Exception: logger.warning(...)` bunu yutar. Sonuç:
`guzergah_performansi`/`en_iyi_guzergah`/`en_kotu_guzergah` şoför
değerlendirme karnesinde **hiçbir zaman doldurulmuyor** (sessiz özellik
kaybı, hata değil).

`9206e3f`'in düzelttiği score-breakdown/route-profile 500 bug'ıyla TAM
AYNI kök sebep sınıfı — ama bu FARKLI: eski `app/core/entities/
sofor_degerlendirme.py` (satır 364-371, `git show f2321a1^:...`) içinde
BİREBİR AYNI kod zaten vardı (`SoforDegerlendirmeService.__init__`'in
constructor-injected `self.sofor_repo`'sunu KULLANMIYOR, doğrudan
`get_sofor_repo()` singleton'ı çağırıyordu). Yani bu **taşımadan önce de
bozuktu** — dalga 5 regresyonu değil, olduğu gibi taşındı. Aynı nedenle
`domain/driver_stats.py::get_route_performance` de etkilenmiş olabilir
(hiçbir endpoint çağırmıyor, yalnız `uow` verilerek unit test'te
kullanılıyor — prod etkisi doğrulanmadı).

Kapsam dışı bırakıldı (davranış değişikliği + ayrı bug-fix kapsamı
gerektiriyor, dalga sırasını bozmasın); ilerleyen bir oturumda
`TASKS/bug-connection-pool-leak-under-load.md` örneğindeki gibi bağımsız
bir bug görevi açılabilir.

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
