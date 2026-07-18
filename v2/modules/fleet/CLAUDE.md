# Modül: fleet

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Araç (vehicle) + dorse (trailer) + bakım (maintenance) CRUD'u, arıza
bildirimi, tahmine dayalı bakım motoru (Feature D), RFC 5545 .ics takvim
dışa aktarımı. `araclar`, `dorseler`, `arac_bakimlari`, `vehicle_event_log`,
`vehicle_spec_timeline` tablolarının tek sahibi.

NE YAPMAZ: yakıt tüketim tahmini/fizik hesabı (prediction_ml —
`vehicle_health_factor.py` oraya taşındı, bağımsız doğrulama ajanı
bulgusu), sefer planlama (trip), Excel import orkestrasyonu (import_excel
— bu modül yalnız `bulk_add_vehicles`/`create_trailer` tek-satır use-case'lerini sunar).

## Public API (public.py imzaları)

```python
# Vehicle
create_vehicle(data: AracCreate, uow=None) -> int
count_active_vehicles() -> int                # LicenseEngine (auth_rbac) araç limit kontrolü için
update_vehicle(arac_id: int, data: AracUpdate, uow=None) -> bool
delete_vehicle(arac_id: int) -> bool          # smart delete: aktif→pasif→hard
delete_all_vehicles() -> int
bulk_add_vehicles(data_list: list[AracCreate]) -> int
get_all_vehicles(only_active=True) -> list[AracEntity]
get_all_vehicles_paged(skip=0, limit=100, aktif_only=True, search=None, marka=None, model=None, min_yil=None, max_yil=None) -> dict
get_vehicle_by_id(arac_id: int, include_inactive=False) -> AracEntity | None
get_vehicle_raw_by_id(arac_id: int, include_inactive=False) -> dict | None  # AracEntity dönüşümü YOK, bkz. aşağı
get_vehicle_stats(arac_id: int) -> VehicleStats | None
get_vehicle_fleet_stats() -> dict            # {total, active, inspection_expiring, inspection_overdue}
get_vehicle_inspection_alerts(within_days: int) -> dict   # {expiring: [...], overdue: [...]}
get_vehicle_events(arac_id: int, limit=20) -> list[dict]  # vehicle_event_log, son N kayıt
# log_vehicle_event artık application/vehicle_event_log.py'de (2026-07-18: DB'ye yazan yardımcı domain/'den taşındı — domain saf/I/O'suz kuralı)

# Trailer — repo parametresi caller'ın UoW'undan geçirilir (uow.dorse_repo)
create_trailer(repo, **data) -> int
update_trailer(repo, dorse_id: int, **data) -> bool
delete_trailer(repo, dorse_id: int) -> bool
get_trailer_by_id(repo, dorse_id: int, include_inactive=False) -> dict | None
get_all_trailers(repo, **kwargs) -> list[dict]
get_all_trailers_paged(repo, skip=0, limit=100, ...) -> list[dict]
export_all_trailers(repo) -> bytes
get_trailer_template() -> bytes
import_trailers(repo, content: bytes) -> dict
get_trailer_fleet_stats(repo) -> dict
get_trailer_inspection_alerts(repo, within_days: int) -> dict

# Maintenance
create_maintenance_record(arac_id, bakim_tipi, km_bilgisi, bakim_tarihi, maliyet=0.0, detaylar="") -> AracBakim
create_breakdown(*, bakim_tipi, arac_id=None, dorse_id=None, km_bilgisi=0, detaylar="") -> AracBakim
get_vehicle_maintenance_history(arac_id) -> list[AracBakim]
mark_maintenance_completed(bakim_id) -> bool
get_upcoming_maintenance_alerts() -> list[dict]
generate_ics_for_maintenance(bakim, arac) -> str
get_maintenance_ics_data(bakim_id: int) -> tuple[AracBakim, Arac | None] | None
MaintenancePredictor, Prediction, PredictionInput      # application/maintenance_prediction.py
get_all_maintenance_predictions() -> list[Prediction]   # application/get_maintenance_predictions.py
get_maintenance_prediction_for_vehicle(arac_id) -> Prediction | None

# Repositories
AracRepository, get_arac_repo(session=None)
DorseRepository, get_dorse_repo(session=None)
MaintenanceRepository
```

**Önemli**: `AracService`/`DorseService`/`MaintenanceService` sınıfları
YOK. Her use-case bağımsız bir fonksiyon (B.1, `location` modülüyle aynı
karar). Vehicle use-case'leri (create/update/delete/list/stats)
constructor-injected bir repo'ya bağımlı DEĞİL — pre-migration
`AracService`'in bu metotları zaten kendi `UnitOfWork()`'ünü açıyordu,
enjekte edilen `self.repo` hiç kullanılmıyordu (dead constructor param,
buraya taşınmadı). Trailer use-case'leri ise pre-migration `DorseService`
gibi repo'yu açıkça parametre alır (caller kendi UoW'undan `uow.dorse_repo`
geçirir) çünkü orijinal kod hiç kendi UoW'unu açmıyordu.

## Yayınladığı / dinlediği event'ler (events.py DTO'ları)

`ARAC_ADDED`, `ARAC_UPDATED`, `ARAC_DELETED` — `@publishes(...)` decorator'ı
`create_vehicle`/`update_vehicle`/`delete_vehicle` üzerinde var ama
**repo-genelinde ölü kod**: hiçbir yerde `event_bus.publish(...)` çağrısı
yok, `_publishes` attribute'u okunmuyor (location'ın aynı bulgusunun
tekrarı — dalga 3'te tekrar doğrulandı). Bu modülün getirdiği bir
regresyon değil.

## TOCTOU kilit değişikliği (davranışsal not, dalga 3)

Pre-migration `AracService`/`DorseService` her ikisi de `self._lock =
asyncio.Lock()` instance-level kilit kullanıyordu — ama üretim yolu
(`app/api/deps.py::get_arac_service`/`get_dorse_service`) her request'te
YENİ bir service instance'ı oluşturduğu için bu kilit gerçek istekler arası
karşılıklı dışlama sağlamıyordu (yalnız "aynı process içinde aynı
instance'ı paylaşan çağrılar" için anlamlıydı — üretimde böyle bir çağıran
yoktu). Gerçek koruma zaten `UNIQUE(plaka)` constraint'i (kod içindeki
yorum bunu açıkça belirtiyor). Free-function'a geçişte bu kilit
`create_vehicle.py`/`create_trailer.py` içinde MODÜL-SEVİYESİ (process
ömürlü, gerçekten paylaşılan) bir `asyncio.Lock()` oldu — davranışsal
olarak kesin bir gerileme değil, tam tersine artık süreç genelinde gerçek
bir fast-path guard sağlıyor; hiçbir test bu kilidin instance-özel
izolasyonuna bağımlı değildi (doğrulandı).

## Şema & tablo sahipliği + çapraz-şema FK kontratları

`araclar`, `dorseler`, `arac_bakimlari`, `vehicle_event_log`,
`vehicle_spec_timeline`. Çapraz-şema FK: `araclar.olusturan_id` →
auth_rbac.kullanicilar; `arac_bakimlari.arac_id`/`.dorse_id` modül-içi.

`arac_repo.py`'nin `seferler` (trip modülü) tablosuna raw-SQL erişimi
(`get_all_with_stats_paged`, `get_arac_with_stats`, `get_maintenance_candidates`,
`get_eligible_for_planning`) FAZ2'nin rol matrisine not düşüldü —
`seferler` üzerinde SELECT-only grant ihtiyacı doğuracak.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **import_excel** (senkron, taşındı — dalga 9): toplu araç/dorse
  import'unda `bulk_add_vehicles`/`create_trailer`'ı doğrudan çağırır
  (location'ın `create_location` tüketimiyle aynı desen). import_excel
  artık `v2/modules/import_excel/public.py`'yi yayınlıyor; fleet'in kendi
  export/template ihtiyaçları (`vehicle_routes.py`, `export_trailers.py`)
  da bu `public.py` üzerinden import_excel'i tüketiyor (ÇİFT yönlü
  bağımlılık — fleet hem import_excel'e sağlıyor hem ondan tüketiyor).
- **prediction_ml** (senkron, geçici, ai_assistant/reports/analytics_executive
  üzerinden dolaylı): `ensemble_service.py`, `ai_service.py`,
  `recommendation_engine.py`, `analyze_costs.py`/`project_cashflow.py`
  (dalga 11'de analytics_executive'e taşındı — eski adları
  `cost_analyzer.py`/`cashflow_projector.py`'ydi; `analiz_service.py`
  dalga 11'de dead-code olarak silindi, listeden düşürüldü), `triage_aggregator.py`,
  `rag_sync_service.py`, `context_builder.py`, `trip_planner.py`,
  `physics_handler.py`, `sefer_write_service.py`, `yakit_service.py`,
  `yakit_tahmin_service.py` bu modülün `AracRepository`/`get_arac_repo`
  ve/veya `araclar` tablosuna raw-SQL ile okuma erişir (fleet `out=4/in=19`
  profilinin `in` tarafı — bkz. TASKS/modules/fleet.md §4). Bunların
  tamamı okuma-amaçlı tüketim; fleet'in kendi iş kuralı bu modüllere
  sızmaz.

## İzin verilen / yasak import'lar (import-linter özeti)

FAZ1'in import-linter gate'i henüz aktif değil (rapor modu). Hedef kontrat:
diğer modüller yalnız `v2.modules.fleet.public`/`.events`'i import eder;
`application/`/`domain/`/`infrastructure/`'a doğrudan erişim yasak — bu
kontrat aktive olana kadar mevcut 19 tüketicinin çoğu (özellikle raw-SQL
`araclar` erişimi ve `AracRepository`/`get_arac_repo` doğrudan import'u)
geçici borç olarak kalıyor, dokümante edildi.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`arac`=vehicle, `dorse`=trailer, `bakim`=maintenance, `ariza`=breakdown,
`plaka`=plate, `aktif`=active, `muayene`=inspection.

## Modüle özel iş kuralları & gotcha'lar

- ✅ **DÜZELTİLDİ (2026-07-15/16, ilk 9 dalganın tam-yeniden dedektif
  denetiminde bulundu)** — `vehicle_routes.py::create_arac` ve
  `trailer_routes.py::create_dorse` oluşturulan kaydı aynı transaction
  içinde `uow.arac_repo.get_by_id(...)`/`uow.dorse_repo.get_by_id(...)` ile
  doğrudan okuyordu (create-then-read-back, application katmanını
  atlıyordu). Vehicle: `get_vehicle_raw_by_id`'ye opsiyonel `uow` parametresi
  eklendi (verilmezse eskisi gibi kendi `UnitOfWork()`'ünü açar — mevcut
  `read_arac`/`update_arac` çağıranları etkilenmedi); route artık
  `get_vehicle_raw_by_id(arac_id, include_inactive=True, uow=uow)`
  çağırıyor. Trailer: zaten `uow` parametresi kabul eden
  `get_trailer_by_id(repo, ...)` (`read_dorse`/`update_dorse`'un da
  kullandığı) kullanılacak şekilde yönlendirildi. Mekanik, davranış
  değişikliği yok.
- ✅ **DÜZELTİLDİ (2026-07-15, dedektif denetiminde bulundu)** —
  `api/vehicle_routes.py`/`api/trailer_routes.py`'deki `fleet-stats`/
  `inspection-alerts`/`{arac_id}/events` handler'ları raw SQL'i doğrudan
  route içinde çalıştırıyordu (application katmanına delege etmiyordu,
  API-only-orkestrasyon ilkesini ihlal ediyordu, hiçbir yerde dokümante
  edilmemişti). Raw SQL `infrastructure/{vehicle,trailer}_repository.py`'ye
  (`get_fleet_stats`/`get_inspection_alerts`/`get_vehicle_events` metotları),
  orkestrasyon `application/get_fleet_stats.py` /
  `application/get_inspection_alerts.py` / `application/get_vehicle_events.py`
  use-case'lerine taşındı. Davranış değişikliği yok (aynı SQL, aynı yanıt
  şekli), gerçek Docker container + `lojinext_test` DB'ye karşı doğrulandı.
- ✅ **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu, `TASKS/bug-route-layer-bypasses-application.md`)** — aynı
  ailenin 2 kalıntısı daha bulundu: `api/admin_maintenance_routes.py`'nin
  `download_ics` handler'ı `UnitOfWork` açıp `select(AracBakim)`/
  `select(Arac)`'ı route içinde çalıştırıyordu (→
  `application/get_maintenance_ics_data.py`); `api/vehicle_routes.py`/
  `api/trailer_routes.py`'nin tekil-GET/PUT handler'ları (`read_arac`/
  `update_arac`/`read_dorse`/`update_dorse`) `db.get(...)`/`select(...)`
  ile doğrudan ORM erişiyordu — artık `get_vehicle_raw_by_id`/`get_trailer_by_id`
  kullanıyor (`include_inactive=True` ile — ham PK lookup'ın aktif/pasif
  ayrımı yapmama davranışı korunuyor, `list`/`count` varsayılanından
  FARKLI, bilerek).
  🔴 **CI'da yakalanan gerçek regresyon (ilk düzeltme turunda)**: `read_arac`/
  `update_arac` başta mevcut `get_vehicle_by_id` (→ `AracEntity.model_validate`)
  kullanıyordu — bu, `AracEntity` dönüşüm zincirinde `plaka` alanının
  değerini değiştiriyordu (gerçek entegrasyon testinde `"34TEST01"` →
  `"34 TEST 01"` farkı yakalandı, kök neden tam izole edilemedi ama
  `AracEntity` katmanına atfedildi). Düzeltme: `get_vehicle_raw_by_id`
  (yeni fonksiyon, `AracEntity` dönüşümü YOK, ham repo dict'i döner) eklendi,
  yalnız tekil-GET/PUT endpoint'leri bunu kullanıyor. 2 MagicMock-tabanlı
  test de (`test_update_vehicle_success`/`test_read_arac_found`) eski
  `get_db`-override deseninden `get_vehicle_raw_by_id` patch'lemeye
  çevrildi (route artık `db`/`SessionDep` üzerinden değil kendi UoW'undan
  okuyor, eski mock hedefi artık hiçbir şeyi kesişmiyordu).
- **Smart delete state machine** (`delete_vehicle.py`): aktif araç →
  soft-delete (aktif=False); zaten pasif araç → hard-delete (FK ihlali
  varsa `ValueError`'a çevrilir). Aynı desen `Dorse`'ta repo katmanında.
- **Reaktivasyon teknik-özellik geçişi** (`create_vehicle.py`, 2026-07-09
  bulgusu): pasif bir aracı aynı plakayla yeniden eklerken TÜM teknik
  özellikler (ağırlık/aerodinamik/motor/lastik/yük/dingil/yakıt
  tipi/muayene) güncellenir — eskiden yalnız marka/model/yıl/tank/hedef
  tüketim/notlar geçiyordu, fizik-tabanlı tahminin okuduğu gerçek girdiler
  sessizce eski kalıyordu.
- **Pasif araca sessiz PATCH koruması** (`update_vehicle.py`): `get_by_id`
  soft-delete filtreli olduğu için pasif bir araç genel PATCH ile
  reaktivasyon akışını bypass ederek güncellenemez — yalnız açık
  `aktif=True` payload'ı buna izin verir.
- **N+1 önleme** (`bulk_add_vehicles.py`): `get_plaka_id_map()` ile tüm
  plakalar tek sorguda önceden çekilir, satır-başına ayrı SELECT atılmaz.
- **RFC 5545 satır katlama** (`export_maintenance_calendar.py`): UTF-8
  multi-byte karakter (Türkçe ş/ğ/ı/ü) ortadan kesilmez; 75 oktet sınırı
  bayt-güvenli şekilde bölünür.
- **Tahmin motoru stateless** (`application/maintenance_prediction.py`): ML
  modeli eğitilmez, her istekte hesaplanır (hibrit kural-tabanlı interval +
  kullanım hızı + tüketim trendi). Redis cache (`maintenance_cache.py`)
  TTL 1 saat; bakım create/complete'te invalidate edilir.
- ✅ **DÜZELTİLDİ (2026-07-17, dedektif denetimi bulgusu)** —
  `MaintenancePredictor` (gerçek `UnitOfWork()` açıp ham SQL çalıştırıyor)
  `domain/`'de yaşıyordu (I/O yok kuralına aykırı, `route_simulation`'ın
  eşdeğeri `RouteSimulator` doğru şekilde `application/`'da) — `application/
  maintenance_prediction.py`'a taşındı. `api/admin_maintenance_routes.py`'nin
  `/predictions` + `/predictions/{arac_id}` handler'ları onu DOĞRUDAN
  çağırıyordu (modülün diğer route'larının hepsi application/ katmanından
  geçerken bu 2 endpoint istisnaydı) — yeni `application/
  get_maintenance_predictions.py` (`get_all_maintenance_predictions`/
  `get_maintenance_prediction_for_vehicle`) eklendi, route'lar artık onu
  çağırıyor. Cache/audit orkestrasyonu route'ta kalır (diğer route'larla
  aynı desen). Davranış değişikliği yok (path/method/response/yetki
  birebir), gerçek Docker container'a karşı doğrulandı.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_arac_service*.py`,
  `test_arac_dorse_reactivate_specs.py` — use-case fonksiyon testleri
  (0-mock: gerçek repo + `db_session`).
- `app/tests/unit/test_maintenance_predictor.py`,
  `test_ics_generator.py` — saf domain/application testleri (DB'siz).
- `app/tests/api/test_vehicles_*.py`, `test_trailers_coverage.py`,
  `test_admin_maintenance*.py` — endpoint testleri (`TEST_DATABASE_URL` zorunlu).
- Free-function `unittest.mock.patch` hedefi HER ZAMAN **tüketen modül**
  (`v2.modules.fleet.api.vehicle_routes.<fn>` gibi) — kaynak modül değil,
  location'daki aynı gotcha burada da geçerli.
