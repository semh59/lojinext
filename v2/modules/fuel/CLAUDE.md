# Modül: fuel

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Yakıt alımı (fuel transaction) CRUD'u, yakıt periyodu türetme (iki dolu-depo
alımı arası km/litre'den tüketim hesabı) + seferlerle Ton-Km oranlı dağıtım,
OCR fiş önizleme, Excel import/export, akaryakıt kart entegrasyonu (Opet),
tahmin-coverage ops alarmı. `yakit_alimlari`, `yakit_periyotlari`,
`yakit_formul` tablolarının tek sahibi.

NE YAPMAZ: asıl ML yakıt tahmin pipeline'ı (`EnsembleFuelPredictor`,
`PhysicsBasedFuelPredictor` — prediction_ml modülünde), araç/dorse/bakım
CRUD (fleet), Excel parse orkestrasyonu (import_excel — bu modül yalnız
`bulk_add_yakit` tek-satır use-case'ini sunar).

## Public API (public.py imzaları)

```python
# Fuel transactions
add_yakit(data: YakitAlimiCreate) -> int
update_yakit(yakit_id: int, data: YakitUpdate) -> bool
delete_yakit(yakit_id: int, deleted_by_id: int | None = None) -> bool   # hard delete
bulk_add_yakit(yakit_list: list[YakitAlimiCreate]) -> int
get_yakit_by_id(yakit_id: int) -> YakitAlimi | None
get_by_vehicle(arac_id: int, limit=50) -> list[YakitAlimi]
get_all(limit=100, vehicle_id=None) -> list[YakitAlimi]
get_all_paged(skip=0, limit=100, aktif_only=True, **filters) -> dict
get_stats(baslangic_tarih=None, bitis_tarih=None) -> dict
get_monthly_summary() -> list[dict]
list_fuel_documents(db, limit: int) -> list[dict]         # yakıt fişi belge arşivi
get_fuel_accuracy_stats(db, days, arac_id=None, sofor_id=None) -> dict  # MAPE/RMSE admin ops

# Periods
create_fuel_periods(fuel_records: list[YakitAlimi]) -> list[YakitPeriyodu]
distribute_fuel_to_trips(period, trips: list[Sefer]) -> list[Sefer]
match_periods_with_trips(periods, all_trips) -> list[PeriyotSeferMatch]
recalculate_vehicle_periods(arac_id: int, yakit_repo=None, sefer_repo=None) -> None
PeriyotSeferMatch                              # domain/period_matcher.py dataclass

# Consumption prediction (modül-içi basit regresyon, prediction_ml'den FARKLI —
# hiçbir API endpoint'i çağırmıyor, bkz. aşağıdaki not)
train_consumption_model(arac_id: int) -> dict
predict_consumption(arac_id, mesafe_km, ton, ascent_m=0, flat_distance_km=0, zorluk="Normal", sofor_id=None) -> dict
retrain_all_models() -> dict
# LinearRegressionModel + train_consumption_model/predict_consumption/retrain_all_models
# 2026-07-18 ölü-kod temizliğinde SİLİNDİ (domain/consumption_prediction.py +
# domain/local_regression.py — hiçbir prod çağıranı yoktu, DB-erişimli domain ihlaliydi)

# Fuel-card integrations
FuelCardProvider, FuelTransaction, OpetFuelProvider   # infrastructure/integrations/opet_client.py

# Coverage ops alarm
CoverageResult, compute_coverage(db, days)     # infrastructure/tasks.py; + celery task monitoring.fuel_coverage_check

# Repository
YakitRepository, get_yakit_repo(session=None)

# Schemas
YakitBase, YakitCreate, YakitUpdate, YakitResponse, YakitListResponse,
OcrParsedFields, OcrPreviewResponse, FuelDocumentItem, FuelDocumentList
```

**Önemli**: `YakitService`/`PeriodCalculationService`/`YakitTahminService`
sınıfları YOK. Her use-case bağımsız bir fonksiyon (B.1, location/
notification/fleet ile aynı karar). Pre-migration `YakitService.__init__(repo=...)`
parametresi dead weight'ti — her metot kendi `UnitOfWork()`'ünü açıyordu,
enjekte edilen `self.repo` hiçbir metot gövdesinde okunmuyordu; buraya
taşınmadı. Aynı şekilde `PeriodCalculationService.__init__(yakit_repo=...,
sefer_repo=...)` opsiyonel repo enjeksiyonu, sadece `recalculate_vehicle_periods`
free function'ında (`yakit_repo=None, sefer_repo=None` parametreleri) korundu
— testler kendi test-injected repo'larını geçiriyor (`app/tests/test_business_flows.py`).
Eski `analiz_service.py`'nin (`AnalizService.recalculate_vehicle_periods`
delegasyonu) bu parametreleri kullanan çağıranı dalga 11'de silindi (dead
code, hiçbir prod kod çağırmıyordu) — kalan tek çağıran `import_excel`'in
`yakit_importer.py`'si zaten `yakit_repo`/`sefer_repo` vermeden çağırıyor.

`YakitTahminService`'in `self.model = LinearRegressionModel()` constructor
attribute'u da dead weight'ti — hiçbir metot `self.model`'i okumuyordu, her
çağrıda `local_model = LinearRegressionModel()` ile yeni instance açılıyordu
(concurrent request izolasyonu için kasıtlı). Free function'a geçişte bu
attribute hiç oluşturulmuyor.

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar)

1. **`OpetFuelProvider`** (`infrastructure/integrations/opet_client.py`) —
   stateless tek-pipeline (bkz. "Opet entegrasyonu" bölümü aşağıda);
   `FuelCardProvider` arayüzünün tek implementasyonu, constructor'da API
   client bağımlılığı enjekte edilir.
2. ~~`LinearRegressionModel`~~ — 2026-07-18 ölü-kod temizliğinde
   `domain/local_regression.py` + `domain/consumption_prediction.py` ile
   birlikte SİLİNDİ (aşağıdaki "dead subsystem" bölümüne bakın).

## Modül-içi consumption prediction — ✅ SİLİNDİ (2026-07-18 ölü-kod temizliği)

`domain/consumption_prediction.py` + `domain/local_regression.py`
(`train_consumption_model`/`predict_consumption`/`retrain_all_models`/
`LinearRegressionModel`) tam-denetim düzeltme turunda SİLİNDİ — dalga 4'ten
beri "dead subsystem" olarak dokümante idi (hiçbir API endpoint'i
çağırmıyordu, üstelik domain katmanından DB'ye erişiyordu — çifte ihlal).
`public.py` export'ları ve testleri (`test_yakit_tahmin_service_coverage.py`,
kök `tests/test_fuel_prediction.py`) da kaldırıldı. Asıl tahmin pipeline'ı
`EnsembleFuelPredictor`/`PhysicsBasedFuelPredictor` (prediction_ml modülü)
üzerinden işler.

## Yayınladığı / dinlediği event'ler (events.py DTO'ları)

✅ **DÜZELTİLDİ (2026-07-16, dedektif denetimi — bkz. `events.py`'nin kendi
changelog'u, bu bölüm 2026-07-17'de bayat kaldığı için güncellendi):**
`YAKIT_ADDED`, `YAKIT_UPDATED`, `YAKIT_DELETED` — `@publishes(...)`
decorator'ı `add_yakit`/`update_yakit`/`delete_yakit` üzerinde hâlâ
metadata-only, ama her fonksiyon artık gerçekten transactional outbox'a
yazıyor (`save_outbox_event(uow.session, EventType.YAKIT_X, ...)`, aynı
transaction, `uow.commit()`'ten önce). Eskiden ölü olan iki gerçek
abonelik artık Celery'nin `relay-outbox-events-every-60s` task'ı satırı
relay ettiğinde GERÇEKTEN tetikleniyor: `app/core/handlers/
model_training_handler.py` (`YAKIT_ADDED` → ML retrain sayaç) ve
`app/infrastructure/cache/cache_invalidation.py` (üç YAKIT_* event'inin
hepsi, wildcard cache temizliği). Her iki handler da artık app startup'ta
(`app/main.py` lifespan) gerçekten register ediliyor — eskiden ne
`ModelTrainingHandler.setup()` ne `setup_cache_invalidation()` hiçbir
yerden çağrılmıyordu.

## Şema & tablo sahipliği

`yakit_alimlari`, `yakit_periyotlari`, `yakit_formul`.
`yakit_alimlari.durum` CHECK constraint'i `['Bekliyor','Onaylandı','Reddedildi']`
— Türkçe+aksanlı, FAZ3 dil geçişinin riskli enum adaylarından biri. **Bu
dalgada DEĞİŞTİRİLMEDİ.**

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **trip (taşındı, dalga 14)**: `recalculate_vehicle_periods`
  `v2.modules.trip.public.Sefer` üzerinden `sefer_repo.get_all(...)`/
  `sefer_repo.update_trips_fuel_data(...)` çağırır — periyot-sefer
  eşleştirmesi ve dağıtılan-yakıt/tüketim yazımı aynı transaction'da. Bu
  bağımlılık BİLİNÇLİ OLARAK fuel tarafında kalıyor (görev dosyası kararı).
- ✅ **ÇÖZÜLDÜ (dalga 11, 2026-07-16)** — eski `analiz_service.py`
  (`AnalizService`) `create_fuel_periods`/`distribute_fuel_to_trips`/
  `match_periods_with_trips`/`recalculate_vehicle_periods`'i doğrudan import
  edip delege eden bir facade'dı (pure pass-through, kendi gerçek mantığı
  yoktu) — dedektif denetiminde hiçbir prod kod tarafından çağrılmadığı
  bulundu (dead code) ve kullanıcı kararıyla tamamen silindi. fuel↔
  analytics_executive arasında bu yönde artık HİÇBİR bağımlılık yok.
- **import_excel (taşındı, ters yön)**: `application/yakit_importer.py`
  `v2.modules.fuel.public`'ten `bulk_add_yakit` + `recalculate_vehicle_periods`'i
  doğrudan çağırır (location'ın `create_location` tüketimiyle aynı desen).
- **fleet (senkron)**: `add_yakit`/`bulk_add_yakit` `uow.arac_repo` üzerinden
  aktif araç kontrolü yapar (plaka değil, aktiflik + son-km).
- **admin_platform (taşındı, dalga 15, ters yön, ARA/interim)**:
  `v2/modules/admin_platform/infrastructure/integrations/registry.py`
  `v2.modules.fuel.public`'ten `FuelCardProvider`/`OpetFuelProvider`
  import eder (cross-module, public.py üzerinden — sanctioned surface,
  import-linter ihlali yok). Bu registry.py'nin NİHAİ adresi değil:
  admin_platform'un kendi CLAUDE.md'si bu dosyanın AVL+Fuel provider
  seçimini tek dosyada birleştirdiğini ve nihai adresinin `platform_infra`
  (henüz başlamamış modül) olduğunu dokümante ediyor — `platform_infra`
  doğduğunda bu import zincirinin güncellenmesi gerekecek, fuel tarafında
  şimdilik borç yok (`get_fuel_provider()` zaten sıfır prod çağıranlı stub).
- **notification (senkron)**: `infrastructure/tasks.py`'deki
  `_run_fuel_coverage_check` Telegram uyarısı için
  `v2.modules.notification.public.notify_error` (2026-07-18: public'e çevrildi)
  çağırır (notification zaten taşınmış, kalıcı bağımlılık).

## Opet entegrasyonu — doğrulanmamış + kullanılmıyor

`infrastructure/integrations/opet_client.py`'deki `OpetFuelProvider` gerçek
OPET API'sine karşı doğrulanmamış (dosyanın kendi docstring'i bunu açıkça
belirtiyor) VE hiçbir prod kod tarafından çağrılmıyor — `registry.py`'nin
`FUEL_PROVIDERS["opet"]` kaydı var ama onu tüketen bir ingestion pipeline
yok (taşımadan önce de böyleydi, regresyon değil).

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-fuel` kontratı: `application/`
diğer modüllerin yalnız `public`/`events`'ini import edebilir (KEPT).
Diğer modüller bu modüle yalnız `v2.modules.fuel.public` üzerinden erişir
(`get_yakit_repo` dahil — container.py/repositories/__init__.py
composition-root istisnası hariç, proje-geneli desen). `infrastructure/
tasks.py`'nin `notification.public.notify_error` çağrısı 2026-07-18'de
public'e çevrildi.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`yakit`=fuel, `yakit_alimi`=fuel transaction/purchase, `yakit_periyodu`=fuel
period, `depo_durumu`=tank status (`Dolu`/`Doldu`/`Kısmi`/`Bilinmiyor`),
`durum`=status (`Bekliyor`/`Onaylandı`/`Reddedildi` — riskli enum, bkz.
üstteki not), `istasyon`=station, `fis_no`=receipt number.

## Modüle özel iş kuralları & gotcha'lar

- ✅ **DÜZELTİLDİ (2026-07-15/16, ilk 9 dalganın tam-yeniden dedektif
  denetiminde bulundu)** — `api/fuel_routes.py::delete_yakit` iki yerde
  `db.get(YakitAlimi, yakit_id)` (ORM) çağırıyordu — zaten import edilmiş
  `get_yakit_by_id()`'ye taşındı. Taşıma sırasında 2 GERÇEK regresyon
  yakalanıp düzeltildi: (1) `get_yakit_by_id`'nin döndürdüğü
  `app.core.entities.models.YakitAlimi` Pydantic entity'sinde `aktif` alanı
  yoktu (`current.aktif` → `AttributeError`) — entity'ye `aktif: bool =
  True` eklendi; (2) `repo.get_by_id()` varsayılan olarak pasif kayıtları
  filtreler, ama smart-delete'in "zaten pasif kaydı hard-delete et" akışı
  pasif kaydı da görebilmeli — `get_yakit_by_id(yakit_id,
  include_inactive=...)` parametresi eklendi. Mevcut `unittest.mock`'lu
  testler bunu YAKALAMADI (MagicMock her attribute'a "sahip" görünür) —
  `mypy v2/` taramasıyla bulundu, gerçek DB + gerçek HTTP client ile yeni
  bir regresyon testi eklendi
  (`test_yakit_service_soft_delete.py::test_delete_route_hard_deletes_passive_record_via_http`).
- ✅ **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu, `TASKS/bug-route-layer-bypasses-application.md` sınıfı)** —
  `api/fuel_routes.py`'nin `list_fuel_documents`/`get_fuel_accuracy`
  endpoint'leri `application/`'ı atlayıp doğrudan `db.execute(text(...))`
  çalıştırıyordu — yeni `application/list_fuel_documents.py` +
  `application/get_fuel_accuracy.py`'ye taşındı. Mekanik, davranış
  değişikliği yok.
- **Rolling outlier check** (`application/add_yakit.py::_check_rolling_outlier`):
  tekil kayıt yerine son 5 dolumun ortalamasına bakar (partial-fill senaryoları
  için); 18-55 L/100km dışına çıkarsa `ANOMALY_DETECTED` event'i publish eder
  (bu event GERÇEKTEN yayınlanıyor — `self.event_bus.publish(...)` doğrudan
  çağrılıyor, YAKIT_* event'lerinin aksine `@publishes` dekoratörüne bağımlı
  değil).
- **Para hesabı Decimal'de** (`infrastructure/repository.py::add`/`update_yakit`,
  `application/bulk_add_yakit.py`): `toplam = fiyat * litre` float çarpımı
  ~7 işlemde 1'inde cent yuvarlama hatası veriyor; her yerde
  `Decimal(str(...))` + `ROUND_HALF_UP` kullanılıyor.
- **N+1 önleme** (`bulk_add_yakit.py`): `get_son_km_bulk()` ile tüm araçların
  son km'si tek GROUP BY sorgusuyla önceden çekilir.
- **Full-tank pencere algoritması** (`domain/period_matcher.py::sync_create_fuel_periods`):
  periyot yalnızca `depo_durumu` "dolu"/"full" içeren iki alım arasında
  hesaplanır — ara kısmi dolumlar litre olarak toplanır ama periyot sınırı
  olamaz.
- **Ton-Km ağırlıklı dağıtım + fallback** (`domain/period_matcher.py::sync_distribute_fuel_to_trips`):
  birincil dağıtım `mesafe × (boş_ağırlık + yük)` faktörüne göre; toplam
  faktör 0 ise (tüm seferler net_kg/ton eksik) salt mesafe oranına düşer.
- **Idempotency-Key desteği** (`api/fuel_routes.py::create_yakit`): opsiyonel
  header — aynı key + aynı gövde tekrar POST edilirse önbelleklenen yanıt
  aynen döner, çift kayıt oluşmaz (client timeout+retry senaryosu).

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_yakit_service*.py` — use-case fonksiyon
  testleri (0-mock: gerçek repo + `db_session`).
- `app/tests/api/test_fuel_coverage.py`, `test_fuel_more.py` — endpoint
  testleri (`TEST_DATABASE_URL` zorunlu).
- `app/tests/unit/test_yakit_import_periyot_trigger.py` — bulk import →
  periyot recalc entegrasyon testi.
- Free-function `unittest.mock.patch` hedefi HER ZAMAN **tüketen modül**
  (`v2.modules.fuel.api.fuel_routes.<fn>` gibi) — kaynak modül değil,
  location/fleet'teki aynı gotcha burada da geçerli.
