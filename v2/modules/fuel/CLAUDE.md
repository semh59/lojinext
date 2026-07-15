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
add_yakit_alimi(**kwargs) -> int              # add_yakit alias (backward-compat, dead — hiçbir prod çağıran yok)
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
LinearRegressionModel                          # domain/local_regression.py

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
— `analiz_service.py` (analytics_executive, henüz taşınmadı) bu parametreleri
gerçekten kullanıyor (kendi test-injected repo'larını geçiriyor).

`YakitTahminService`'in `self.model = LinearRegressionModel()` constructor
attribute'u da dead weight'ti — hiçbir metot `self.model`'i okumuyordu, her
çağrıda `local_model = LinearRegressionModel()` ile yeni instance açılıyordu
(concurrent request izolasyonu için kasıtlı). Free function'a geçişte bu
attribute hiç oluşturulmuyor.

## Modül-içi consumption prediction — kullanılmıyor (dead subsystem, taşımadan önce de böyleydi)

`domain/consumption_prediction.py` (`train_consumption_model`/
`predict_consumption`/`retrain_all_models`) hiçbir API endpoint'i tarafından
çağrılmıyor — doğrulandı (dalga 4). Tek prod referansı
`app/services/prediction_service.py`'deki `PredictionService.__init__`'te
`self.yakit_tahmin_service = YakitTahminService()` idi; bu attribute
hiçbir metotta okunmuyordu (dead constructor call) — kaldırıldı, buraya
taşınmadı. Bu bir regresyon DEĞİL — taşımadan önce de aynı şekilde
kullanılmıyordu. Asıl tahmin pipeline'ı `EnsembleFuelPredictor`/
`PhysicsBasedFuelPredictor` (prediction_ml modülü) üzerinden işler.

## Yayınladığı / dinlediği event'ler (events.py DTO'ları)

`YAKIT_ADDED`, `YAKIT_UPDATED`, `YAKIT_DELETED` — `@publishes(...)`
decorator'ı `add_yakit`/`update_yakit`/`delete_yakit` üzerinde var ama
**repo-genelinde ölü kod** (location/notification/fleet'in aynı bulgusu):
`publishes()` yalnızca fonksiyona `_publishes` attribute'u ekliyor, hiçbir
yerde okunmuyor; fonksiyon gövdeleri de `event_bus.publish(...)` çağırmıyor.

**Bu modülde diğerlerinden FARKLI olarak gerçek abonelikler var ve onlar da
etkisiz kalıyor**: `app/core/handlers/model_training_handler.py`
`YAKIT_ADDED`'a subscribe olup ML retrain tetiklemeyi bekliyor;
`app/infrastructure/cache/cache_invalidation.py` her üç YAKIT_* event'ine
subscribe olup cache invalidation bekliyor. İkisi de bugün hiç tetiklenmiyor.
Taşımadan önce de aynıydı (orijinal `yakit_service.py` aynı decorator-only
kablolamaya sahipti) — regresyon değil, ama fleet/location'ın ARAC_*/
LOKASYON_* bulgularından daha yüksek etkili bir önceden var olan boşluk.

## Şema & tablo sahipliği

`yakit_alimlari`, `yakit_periyotlari`, `yakit_formul`.
`yakit_alimlari.durum` CHECK constraint'i `['Bekliyor','Onaylandı','Reddedildi']`
— Türkçe+aksanlı, FAZ3 dil geçişinin riskli enum adaylarından biri. **Bu
dalgada DEĞİŞTİRİLMEDİ.**

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **trip (senkron, henüz taşınmadı)**: `recalculate_vehicle_periods`
  `sefer_repo.get_all(...)`/`sefer_repo.update_trips_fuel_data(...)`
  çağırır — periyot-sefer eşleştirmesi ve dağıtılan-yakıt/tüketim yazımı aynı
  transaction'da. Bu bağımlılık BİLİNÇLİ OLARAK fuel tarafında kalıyor (görev
  dosyası kararı) — trip taşınınca bu dosyanın importu güncellenir.
- **analytics_executive (senkron, henüz taşınmadı)**: `analiz_service.py`
  (`AnalizService`) `create_fuel_periods`/`distribute_fuel_to_trips`/
  `match_periods_with_trips`/`recalculate_vehicle_periods`'i doğrudan import
  edip delege ediyor (facade pattern) — kendi `yakit_repo`/`sefer_repo`
  fallback'leriyle. analytics_executive henüz `public.py` yayınlamadığı
  için bu geçici bir borç değil, YÖNÜ (tüketen taraf analytics_executive)
  fuel'in CLAUDE.md'sinde not düşülmüş bir konu değil.
- **import_excel (senkron, henüz taşınmadı)**: `import_service.py`
  `process_yakit_import` içinde `bulk_add_yakit` + `recalculate_vehicle_periods`'i
  doğrudan çağırır (location'ın `create_location` tüketimiyle aynı desen).
- **fleet (senkron)**: `add_yakit`/`bulk_add_yakit` `uow.arac_repo` üzerinden
  aktif araç kontrolü yapar (plaka değil, aktiflik + son-km).
- **platform-infra (senkron, geçici, ters yön)**: `app/core/integrations/registry.py`
  (henüz taşınmadı) `infrastructure/integrations/opet_client.py`'den
  `FuelCardProvider`/`OpetFuelProvider` import eder — registry taşınınca
  bu import v2 tarafında zaten doğru yerde kalacak, fuel tarafında borç yok.
- **notification (senkron)**: `infrastructure/tasks.py`'deki
  `_run_fuel_coverage_check` Telegram uyarısı için
  `v2.modules.notification.infrastructure.telegram_client.notify_error`
  çağırır (notification zaten taşınmış, kalıcı bağımlılık).

## Opet entegrasyonu — doğrulanmamış + kullanılmıyor

`infrastructure/integrations/opet_client.py`'deki `OpetFuelProvider` gerçek
OPET API'sine karşı doğrulanmamış (dosyanın kendi docstring'i bunu açıkça
belirtiyor) VE hiçbir prod kod tarafından çağrılmıyor — `registry.py`'nin
`FUEL_PROVIDERS["opet"]` kaydı var ama onu tüketen bir ingestion pipeline
yok (taşımadan önce de böyleydi, regresyon değil).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`yakit`=fuel, `yakit_alimi`=fuel transaction/purchase, `yakit_periyodu`=fuel
period, `depo_durumu`=tank status (`Dolu`/`Doldu`/`Kısmi`/`Bilinmiyor`),
`durum`=status (`Bekliyor`/`Onaylandı`/`Reddedildi` — riskli enum, bkz.
üstteki not), `istasyon`=station, `fis_no`=receipt number.

## Modüle özel iş kuralları & gotcha'lar

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
