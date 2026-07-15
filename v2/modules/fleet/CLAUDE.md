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
update_vehicle(arac_id: int, data: AracUpdate, uow=None) -> bool
delete_vehicle(arac_id: int) -> bool          # smart delete: aktif→pasif→hard
delete_all_vehicles() -> int
bulk_add_vehicles(data_list: list[AracCreate]) -> int
get_all_vehicles(only_active=True) -> list[AracEntity]
get_all_vehicles_paged(skip=0, limit=100, aktif_only=True, search=None, marka=None, model=None, min_yil=None, max_yil=None) -> dict
get_vehicle_by_id(arac_id: int) -> AracEntity | None
get_vehicle_stats(arac_id: int) -> VehicleStats | None
get_vehicle_fleet_stats() -> dict            # {total, active, inspection_expiring, inspection_overdue}
get_vehicle_inspection_alerts(within_days: int) -> dict   # {expiring: [...], overdue: [...]}
get_vehicle_events(arac_id: int, limit=20) -> list[dict]  # vehicle_event_log, son N kayıt

# Trailer — repo parametresi caller'ın UoW'undan geçirilir (uow.dorse_repo)
create_trailer(repo, **data) -> int
update_trailer(repo, dorse_id: int, **data) -> bool
delete_trailer(repo, dorse_id: int) -> bool
get_trailer_by_id(repo, dorse_id: int) -> dict | None
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
MaintenancePredictor, Prediction, PredictionInput      # domain/maintenance_prediction.py

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

- **import_excel** (senkron, geçici doğrudan import):
  `app/core/services/import_service.py` toplu araç/dorse import'unda
  `bulk_add_vehicles`/`create_trailer`'ı doğrudan çağırır (location'ın
  `create_location` tüketimiyle aynı desen). import_excel henüz
  `public.py`'sini yayınlamadı; fleet bu bağımlılığın YÖNÜ (tüketen taraf
  import_excel) olduğu için kendi CLAUDE.md'sinde not düşülmüş bir borç
  değil.
- **prediction_ml** (senkron, geçici, ai_assistant/reports/analytics_executive
  üzerinden dolaylı): `ensemble_service.py`, `ai_service.py`,
  `recommendation_engine.py`, `cost_analyzer.py`, `cashflow_projector.py`,
  `analiz_service.py`, `report_service.py`, `triage_aggregator.py`,
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
- **Tahmin motoru stateless** (`domain/maintenance_prediction.py`): ML
  modeli eğitilmez, her istekte hesaplanır (hibrit kural-tabanlı interval +
  kullanım hızı + tüketim trendi). Redis cache (`maintenance_cache.py`)
  TTL 1 saat; bakım create/complete'te invalidate edilir.

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
