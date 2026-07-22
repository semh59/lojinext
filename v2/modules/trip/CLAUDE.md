# Modül: trip

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Sefer (trip) domain'inin CRUD'u, durum makinesi (Planned/Completed/Cancelled),
dönüş seferi (round-trip) otomasyonu, toplu (bulk) işlemler, sefer bazlı
yakıt tahmini zenginleştirmesi (`predict_outbound`/`repredikt_for_update` —
prediction_ml'e TEK köprü), SLA gecikme tespiti, maliyet mutabakatı
(`reconcile_costs`), onay iş akışı (`onay_durumu`), sefer create yolunun
Phase 4-5 estimator pipeline'ı (`SeferFuelEstimator`), ve dashboard/rapor
tüketicilerinin çağırdığı istatistik agregasyonları. `seferler`,
`route_simulations`, `route_segments` tablolarının tek sahibi.

NE YAPMAZ: araç/şoför/dorse master data (fleet/driver), rota geometrisi/
segment simülasyonu (route_simulation — bu modül yalnız sonucu tüketir),
ML model eğitimi/ensemble (prediction_ml — bu modül yalnız
`get_prediction_service()`'i çağırır), Excel import/export (import_excel —
bu modül yalnız `add_trip.py`/`bulk_add_trips.py`'yi çağırır), executive
dashboard agregasyonu (analytics_executive — bu modül yalnız
`get_trip_stats`/`get_fuel_performance_analytics` ham verisini sağlar).

## Dosya envanteri düzeltmeleri (task dosyası vs gerçek kod)

`TASKS/modules/trip.md` madde 5'in kümelemesi 2 yerde kök CLAUDE.md'nin
domain-saflığı kuralını (I/O yok + application'a bağımlı olamaz) ihlal
ediyordu — prediction_ml dalgasındaki aynı sınıf sapmayla tutarlı olarak
düzeltildi:

- **`sla.py`**: task dosyası `domain/sla.py` öneriyordu; gerçek kod
  `uow.sefer_repo`/`uow.lokasyon_repo` DB I/O'su + `get_outbox_service()`
  çağrısı yapıyor → `application/sla.py`'ye taşındı.
- **Dönüş seferi kümesi (`return_trip.py`)**: task dosyası
  `domain/return_trip.py` öneriyordu; gerçek kod aynı DB I/O + cross-module
  çağrı (`prediction_ml.public.get_prediction_service`) yapıyor →
  `application/return_trip.py`'ye taşındı.

Ayrıca task dosyasının "import_excel/analytics_executive/ai_assistant zaten
hazır" varsayımı 3 hedeften 2'sinde doğruydu (import_excel, ai_assistant —
zaten `trip.public`'e delege ediyorlardı), analytics_executive'te YANLIŞTI:
cost/stats route'ları hiç bağlı değildi — gerçek kod okunarak (varsayım
değil) `v2/modules/analytics_executive/api/trip_analytics_routes.py` yeni
yazıldı, `trip.public.get_trip_stats`/`get_fuel_performance_analytics`'e
delege eder.

`sefer_status.py`/`trip_status.py` planın önerdiği `domain/` yerine **modül
kökünde** duruyor (`schemas.py` gibi) — bkz. aşağıdaki import-linter bölümü,
gerekçe orada.

## Public API (public.py imzaları)

```python
# facade (sınıf istisnası, aşağıya bkz.)
SeferService, get_sefer_service() -> SeferService

# per-request factory (2026-07-22, Kalem 3 commit 3 — app/api/deps.py'den
# taşındı; get_sefer_service()'in YUKARIDAKİ container-tabanlı, argümansız
# hâliyle KARIŞTIRILMASIN — bu, UOWDep'ten fresh bir SeferService kurar)
get_sefer_service_for_request(uow: UOWDep) -> SeferService

# read
get_by_id(sefer_id, current_user=None, repo=None) -> Optional[Sefer]
get_sefer_by_id(sefer_id, current_user=None, repo=None) -> Optional[dict]
get_by_vehicle(arac_id, limit=50, repo=None) -> list[Sefer]
get_all_paged(current_user=None, skip=0, limit=100, aktif_only=True, repo=None, **filters) -> dict
get_all_trips(start_date=None, end_date=None, sofor_id=None, arac_id=None, status=None, limit=100) -> list
get_timeline(sefer_id) -> list[dict]

# write / CRUD
add_sefer(data: SeferCreate, user_id=None) -> int
update_sefer(sefer_id, data: SeferUpdate, user_id=None) -> bool
delete_sefer(sefer_id) -> bool
bulk_add_sefer(sefer_list: list[SeferCreate]) -> int
bulk_update_status(sefer_ids, new_status, user_id=None) -> dict
bulk_cancel(sefer_ids, iptal_nedeni, user_id=None) -> dict
bulk_delete(sefer_ids) -> dict
create_return_trip(sefer_id, user_id=None) -> int

# analytics_executive'in çağırdığı stats/reconciliation (ham veri, agregasyon hedef modülde)
get_trip_stats(durum=None, baslangic_tarih=None, bitis_tarih=None) -> dict
get_fuel_performance_analytics(durum=None, ..., arac_id=None, sofor_id=None, search=None) -> dict
reconcile_costs(sefer_id, consumption_threshold=...) -> dict

# approval workflow
set_onay_durumu(sefer_id, yeni_durum, onay_notu=None, onaylayan_id=None, repo=None) -> Optional[Any]
get_by_onay_durumu(onay_durumu, skip=0, limit=50, repo=None) -> list

# prediction enrichment (route_simulation/ai_assistant tüketir)
build_prediction_route_analysis(route_details=None, weather_factor=None) -> Optional[dict]
extract_prediction_values(prediction, quality_flags=None) -> tuple[Optional[float], Optional[dict]]

# SeferFuelEstimator (Phase 4-5, sınıf istisnası)
SeferFuelEstimator, SeferFuelInput, SeferFuelEstimate, FactorBreakdown, get_sefer_fuel_estimator()

# status
SEFER_STATUS_PLANLANDI, SEFER_STATUS_TAMAMLANDI, SEFER_STATUS_IPTAL, CANONICAL_SEFER_STATUS_SET
ensure_canonical_sefer_status(value, field_name=..., allow_none=...) -> Optional[str]
normalize_sefer_status(value) -> Optional[str]
ALLOWED_TRANSITIONS: Dict[TripStatus, list[TripStatus]]
safe_durum(value) -> str

# repository
SeferRepository, get_sefer_repo() -> SeferRepository

# schemas
SeferBase, SeferCreate, SeferUpdate, SeferResponse, SeferDurum, TripStatus,
SeferBulkStatusUpdate, SeferBulkCancel, SeferBulkDelete, SeferBulkResponse,
SeferListResponse, SeferStatsResponse
```

`SeferOnayRequest` (`schemas.py`, `trip_approval_routes.py`'nin `/onay`
gövdesi) 2026-07-22'de "V2 dışında kalan var mı" tarama turunda bulunup
`app/schemas/telegram.py`'den taşındı — Telegram-özgü değildi, dosya adı
yanıltıcıydı (trip'in kendi onay endpoint'inin gövdesiydi, aynı dosyanın
gerçek Telegram-bridge şemaları `admin_platform.schemas`'a gitti).
Public.py'ye export EDİLMEZ — tek tüketicisi kendi `api/
trip_approval_routes.py`'si.

**Önemli**: `trip_prediction_enrichment.py`'nin diğer fonksiyonları
(`build_route_details_snapshot`, `build_prediction_quality_flags`,
`check_reprediction_needed`, `repredikt_for_update`, `resolve_route`,
`predict_via_estimator`, `predict_outbound`) public.py'de export EDİLMEZ —
yalnız trip modülünün kendi `application/` dosyaları arasında (add_trip,
update_trip, return_trip, bulk_add_trips) tüketilir, dış modül tüketicisi yok.

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar)

1. **`SeferService`** (`application/trip_service.py`, ARCH-006) — thin
   facade. CQRS alt-servisleri (`SeferReadService`/`SeferWriteService`/
   `SeferAnalizService`) dissolve edildi; her use-case bağımsız bir
   fonksiyon (B.1). Facade'ın kendisi kasıtlı korundu: hiçbir endpoint
   alt-fonksiyonları doğrudan import etmiyor (doğrulandı), tümü
   `SeferService`'e bağımlı — kaldırılsaydı her endpoint 5-6 use-case
   fonksiyonu inject edip read/write/analysis ayrımını yeniden türetmek
   zorunda kalırdı.
2. **`SeferFuelEstimator`** (`application/sefer_fuel_estimator.py`) —
   constructor-injected client bağımlılıkları (Mapbox/Open-Meteo/RouteSimulator),
   tek-cohesive-pipeline (Phase 4-5, kök CLAUDE.md'nin 7 adımı). Diğer
   modüllerdeki `RouteSimulator`/`LokasyonHydrator` ile aynı gerekçe
   kategorisi.
3. **`SeferRepository`** (`infrastructure/repository.py`) — repository
   pattern istisnası (tüm modüllerde repo bir sınıf, B.1 use-case
   dissolve kuralı yalnız `application/`/`domain/` servis katmanına
   uygulanır).

## Yayınladığı / dinlediği event'ler (events.py)

Kendi `EventType`'ını tanımlamaz, paylaşılan
`app.infrastructure.events.event_bus.EventType` sabitlerini kullanır.

**Yayınlar**: `SEFER_ADDED` (`add_sefer`, outbox), `SEFER_DELETED`
(`delete_sefer`), `SEFER_UPDATED` (`reconcile_costs` — maliyet dağıtımı
sonrası), `ROUTE_COMPLETED` (`update_sefer_uow` — durum Completed'e
geçtiğinde), `SLA_DELAY` (`sla.py::check_sla_delay`, outbox), `ANOMALY_DETECTED`
(`reconcile_costs` — dağıtılan tüketim eşiği aştığında, `type="HIGH_CONSUMPTION"`).

**Dinler**: yok — event akışı tek yönlü (trip → diğer modüller).
prediction_ml'in `ModelTrainingHandler`'ı `SEFER_ADDED`'i, `PhysicsRecalculationHandler`'ı
`SEFER_UPDATED`'i dinler (o modülün kendi CLAUDE.md'sinde dokümante).

## Şema & tablo sahipliği

`seferler` (`Sefer` — `SeferRepository`, `net_kg = dolu_agirlik_kg -
bos_agirlik_kg` CHECK constraint'i, `ck_seferler_check_sefer_net_kg_calc`),
`route_simulations` (Phase 4-5 `SeferFuelEstimator` persist hedefi, kolonlar
`total_km`/`total_l`/`total_eta_sec`/`avg_l_per_100km` — kök CLAUDE.md'de
dokümante), `route_segments` (per-segment granular tahmin verisi).

## Sefer yakıt tahmini — iki paralel tahmin yolu (kafa karıştırmasın)

Trip modülünde İKİ AYRI tahmin akışı var, ikisi de prediction_ml'e bağlanır
ama farklı amaçlar için:

1. **Legacy path** (`trip_prediction_enrichment.py::predict_outbound`,
   `settings.USE_SEFER_FUEL_ESTIMATOR=False` — default): doğrudan
   `prediction_ml.public.get_prediction_service().predict_consumption()`
   çağırır, weather-service ile ayrı bir weather_factor hesaplar.
2. **Phase 4-5 estimator path** (`application/sefer_fuel_estimator.py`,
   `settings.USE_SEFER_FUEL_ESTIMATOR=True` — production): Mapbox +
   Open-Meteo + RouteSimulator + physics + adjustment factors birleşimi,
   `route_simulations`/`route_segments`'e persist eder. Kök CLAUDE.md'nin
   "Sefer yakıt tahmini (Phase 4-5 SeferFuelEstimator)" bölümünde 7 adımı
   dokümante.

`predict_outbound` iki yolu da sarar (`predict_via_estimator`'a delege eder
flag açıkken); her iki yol da **2.5s timeout** uygular — cold cache'de
sefer **tahminisiz** kaydedilir (`tahmini_tuketim=NULL`, silent fallback,
`GET /admin/fuel-accuracy`'ye yansır).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **fleet (taşındı)**: `add_trip.py`/`bulk_add_trips.py` → `uow.arac_repo`
  (aynı UoW üzerinden, fleet'in kendi repo'su).
- **driver (taşındı)**: `infrastructure/repository.py::get_all`'ın genel
  arama özelliği → `v2.modules.driver.public.search_driver_ids_by_name`.
  Ters yön: `v2/modules/driver/infrastructure/driver_trip_queries.py`
  (6 şofor-özel sorgu, bu dalgada `SeferRepository`'den oraya taşındı) →
  kendi UoW/session fallback deseniyle `Sefer` modeline sorgu atıyor.
- **prediction_ml (taşındı, TEK köprü `trip_prediction_enrichment.py`)**:
  `predict_outbound`/`repredikt_for_update`/`predict_via_estimator`/
  `bulk_add_trips.py`/`return_trip.py` → `prediction_ml.public.get_prediction_service`.
  Ters yön: `prediction_ml`'in dokümantasyonu bu bağımlılığı "trip
  (taşınmadı, dalga 14, geçici)" olarak işaretlemişti — DALGA 14 ile bu artık
  güncel değil, prediction_ml'in kendi CLAUDE.md'si bir sonraki denetimde
  güncellenmeli (bu modülün kapsamı dışında, cross-module doc senkronizasyonu
  notu).
- **route_simulation (taşındı, iki yönlü)**: `sefer_fuel_estimator.py` →
  `route_simulation`'ın `RouteSimulator`/Mapbox/Open-Meteo client'larını
  kullanır. Ters yön: route_simulation'ın `get_route_details.py` route-simulation
  path'i → `trip.public.build_prediction_route_analysis`/`extract_prediction_values`.
- **import_excel (taşındı, ters yön)**: `sefer_importer.py`/
  `sefer_upload_importer.py` → `trip.public.add_sefer`/`bulk_add_sefer`.
  `v2/modules/import_excel/api/trip_export_routes.py`/`trip_import_routes.py`
  (bu dalgada `trips.py`'den taşındı) → `trip.public`.
- **analytics_executive (taşındı, ters yön)**: `v2/modules/analytics_executive/
  api/trip_analytics_routes.py` (bu dalgada yeni yazıldı) →
  `trip.public.get_trip_stats`/`get_fuel_performance_analytics`/`reconcile_costs`.
- **ai_assistant (taşındı, ters yön)**: `v2/modules/ai_assistant/api/
  plan_wizard_routes.py` (bu dalgada `trips.py`'den taşındı) → `trip.public`
  (trip planner wizard, sefer create çağrısı).
- **auth_rbac (taşındı)**: her `api/*.py` route dosyası →
  `v2.modules.auth_rbac.public.require_permissions`.

## Router bölünmesi — eski `trips.py` (1017 satır, 22 route) → 8 dosya

`app/api/v1/endpoints/trips.py` silindi, tümü `api.py`'de aynı
`prefix="/trips"` altında (URL'ler değişmedi — router objesinin fiziksel
konumu URL'i etkilemez, `include_router(prefix=...)` belirler):

| Yeni dosya | Modül | İçerik |
|---|---|---|
| `trip/api/trip_read_routes.py` | trip | liste, detay, timeline |
| `trip/api/trip_write_routes.py` | trip | create/update/delete |
| `trip/api/trip_bulk_routes.py` | trip | bulk status/cancel/delete |
| `trip/api/trip_approval_routes.py` | trip | onay workflow |
| `import_excel/api/trip_export_routes.py` | import_excel | Excel export |
| `import_excel/api/trip_import_routes.py` | import_excel | Excel import (sync/async) |
| `analytics_executive/api/trip_analytics_routes.py` | analytics_executive | cost-analysis, stats (async job pattern) |
| `ai_assistant/api/plan_wizard_routes.py` | ai_assistant | trip planner wizard |

**2026-07-22 (Kalem 3 commit 3)**: `api.py`'nin KENDİSİ (~50
`include_router()` çağrısı, bu 8 route dosyası dahil hepsini
`prefix="/trips"` ile mount eden composition-root) `app/api/v1/api.py`'den
`v2/modules/platform_infra/api_router.py`'ye taşındı — yalnız
include_router aggregator'ının fiziksel konumu değişti, yukarıdaki 8 route
dosyasının kendisi YERİNDE kaldı, URL'ler/sıralama DEĞİŞMEDİ (`app.routes`
üzerinden + gerçek `TestClient` isteğiyle 245 route'un tamamı doğrulandı —
özellikle `trip_read_router`'ın catch-all'ının en son kaydedildiği).
`app/main.py` artık `from v2.modules.platform_infra.api_router import
api_router` import ediyor.

## İzin verilen / yasak import'lar (import-linter özeti)

`public-surface-only-trip` kontratı: `application/` diğer 13 modülün yalnız
`public`/`events`'ini import edebilir. `13 modulun domain/infrastructure
katmanlari birbirinden bagimsiz` kontratına `trip.domain`/`trip.infrastructure`
eklendi — **bu kontrat aynı modül İÇİNDE de geçerli** (yeni bulgu, önceki 13
dalgada hiç karşılaşılmamıştı): `trip.infrastructure`'ın `trip.domain.
sefer_status`/`trip_status`'ü doğrudan import etmesi bu kontratı ihlal
ediyordu. Çözüm: `sefer_status.py`/`trip_status.py` `domain/`'den **modül
köküne** taşındı (`v2/modules/trip/sefer_status.py`,
`v2/modules/trip/trip_status.py`) — `schemas.py` gibi kontratın `modules`
listesinin dışında, hem `domain/` hem `infrastructure/` bunları serbestçe
import edebilir (ikisi de saf/normalizasyon kodu, gerçek domain-I/O ayrımı
ihlali değil). `Modul-ici katman sirasi` kontratına (`api → application →
infrastructure → domain`) `v2.modules.trip` container olarak eklendi.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`sefer`=trip, `durum`=status, `çıkış/varış yeri`=origin/destination,
`mesafe`=distance, `net/dolu/boş ağırlık`=net/loaded/empty weight,
`tırmanış/iniş`=ascent/descent, `düz mesafe`=flat distance,
`dönüş seferi`=return trip, `boş sefer`=empty trip (deadhead),
`onay durumu`=approval status, `iptal nedeni`=cancellation reason,
`mutabakat`=reconciliation, `tahmini tüketim`=estimated consumption,
`gerçek tüketim`=actual consumption, `güzergah`=route.

## Test stratejisi

- `app/tests/unit/test_services/test_sefer_write_more.py`,
  `test_sefer_write_more2.py`, `test_sefer_write_service_coverage.py`,
  `test_sefer_write_service_prediction_flows.py` — eski `SeferWriteService`
  instance-method çağrıları free-function çağrılarına çevrildi
  (`add_trip.add_sefer`, `update_trip.update_sefer_uow`,
  `bulk_add_trips.bulk_add_sefer`, `return_trip.build_return_trip`/
  `create_return_trip`, `sla.check_sla_delay`,
  `trip_prediction_enrichment.*`, `domain.trip_validation.*`).
- `app/tests/unit/test_services/test_sefer_read_service.py` — free-function
  çağrıları `repo=mock_repo` parametresiyle (`list_trips.get_by_id` vb.).
- `app/tests/unit/test_sefer_status_guards.py` — `ALLOWED_TRANSITIONS`
  artık `domain/trip_validation.py`'den, dosya-yolu kontrolleri
  `v2/modules/trip/{schemas.py,trip_status.py,application/update_trip.py,
  infrastructure/repository.py}`'a güncellendi.
- Free-function `unittest.mock.patch` hedefi: modül-seviyesi import'lar için
  **tüketen modülün namespace'i** (örn. `update_trip.check_sla_delay`,
  `update_trip.repredikt_for_update`, `add_trip.predict_outbound`,
  `return_trip.build_return_trip`); fonksiyon-içi (inline) import'lar için
  **kaynak modül** (örn.
  `v2.modules.trip.application.sefer_fuel_estimator.get_sefer_fuel_estimator`,
  `v2.modules.prediction_ml.public.get_prediction_service`) — diğer 13
  modülle tutarlı aynı konvansiyon.
- `test_sefer_write_service_coverage.py` `@pytest.mark.integration`
  (gerçek `db_session` fixture, 0-mock Dilim 25 kararı) — `TEST_DATABASE_URL`
  gerektirir.
