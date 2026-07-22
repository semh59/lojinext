# Modül: admin_platform

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Yönetici (admin) panelinin sistem-yönetimi yüzeyi: sistem konfigürasyonu
(`sistem_konfig` — validasyon + Redis cache + pubsub invalidation),
runtime-config okuma köprüsü (diğer modüllerin env yerine DB'den okuduğu
tek kanonik yol), yönetici audit logu (`admin_audit_log`), dış entegrasyon
API anahtarları (`entegrasyon_ayarlari` — Mapbox/OpenRoute/Groq/bot
token'ları, write-only), AVL sağlayıcı scaffolding (Mobiliz adapter, hepsi
stub), idempotency-key altyapısı (`idempotency_keys` — trip/fuel'in yazma
uçları kullanır), Telegram bot ↔ backend köprüsü (`internal.py` uçları),
sistem sağlık kontrolü (`HealthService` — DB/Redis/AI/Sentry/circuit
breaker/backup), hata-olayı (error_events) admin-yönetim yüzeyi (liste/
istatistik/resolve/trace-chain), SSE canlı hata akışı, ML eğitim ilerleme
WebSocket'i.

NE YAPMAZ: `error_events`/`error_occurrences`/`error_hourly_stats`
tablolarının YAZIM yolu (`v2/modules/platform_infra/monitoring/` — cross-cutting
altyapı, audit_logger.py/event_bus.py ile aynı kategori; bu modül yalnız
admin-facing okuma/yönetim katmanını sağlar; `container_health.py` bu
alt sistemden dalga 17'de admin_platform'a taşındı, aşağıya bkz.),
veritabanı yedekleme
zamanlanmış görevi (`app/workers/tasks/backup_tasks.py` — Celery beat
cron job, `app/infrastructure/database/backup_manager.py`'yi kullanır;
`HealthService.trigger_manual_backup()` da aynı infra manager'ı BAĞIMSIZ
bir yoldan çağırır, celery task'ını tetiklemez), hata-digest/partition/
db-health-check zamanlanmış görevleri (`app/workers/tasks/error_digest.py`
— aynı gerekçe, cross-cutting monitoring infra'sı, `error_hourly_stats`
materialized view refresh'i de dahil).

## Dosya envanteri düzeltmeleri (task dosyası vs gerçek kod)

`TASKS/modules/admin-platform.md`'nin 26-dosyalık/3718-satır/25-route
envanteri denetimde 5 kategori gerçek sapma gösterdi:

1. **Route sayısı hataları**: `admin_integrations.py` gerçekte 3 route
   (`GET /`, `GET /planned`, `PUT /{servis_adi}`) — task dosyası 2 diyordu.
   `admin_ws.py` gerçekte 1 route (`/training`) — task dosyası 2 diyordu;
   `/live` route'u zaten dalga 2'de `notification` modülüne taşınmıştı
   (bkz. `v2/modules/notification/CLAUDE.md`).
2. **Ölü kod**: `app/database/repositories/config_repo.py`
   (`ConfigRepository`) — grep ile doğrulandı, sıfır çağıranı (prod veya
   test) yoktu. SİLİNDİ.
3. **Tablo-sahipliği yanlış dosya**: `app/database/repositories/
   audit_repo.py` (`AuditRepository`, `model = AdminAuditLog` taşıyordu)
   — TEK gerçek metodu `get_sefer_timeline` hiçbir zaman
   `admin_audit_log`'a dokunmuyordu, yalnızca trip'in `seferler_log`
   tablosunu sorguluyordu. Dosya adı/sınıf adı admin_platform'u ima
   ediyordu ama gerçek davranışı trip'e aitti — `v2/modules/trip/
   infrastructure/sefer_timeline_repo.py`'ye taşındı (tablo sahipliği
   koduna göre, dosya adına göre değil). `app/database/repositories/
   setting_repository.py` (`SettingRepository`, `kullanici_ayarlari`
   yönetiyor) benzer şekilde `v2/modules/auth_rbac/infrastructure/
   setting_repository.py`'ye taşındı — tek tüketicisi zaten
   `auth_rbac/application/preference_service.py` idi.
4. **Eksik tablo dokümantasyonu**: task dosyası `sistem_konfig`/
   `konfig_gecmis`/`idempotency_keys`/`error_events` ailesini hiç
   listelememişti — bu dosya bunları düzeltiyor.
5. **Route-layer-bypass bug'ı**: `app/api/v1/endpoints/system.py`'nin
   7 route'undan 4'ü (`get_error_events`, `get_error_stats`,
   `resolve_error_event`, `get_trace_chain`) doğrudan route handler
   İÇİNDE raw SQL çalıştırıyordu (`TASKS/bug-route-layer-bypasses-
   application.md` bug sınıfı). `application/error_events.py`'ye
   çıkarıldı, route'lar artık ince (thin) — yalnız çağırıp Pydantic
   response modeline sarıyor.

Ayrıca task dosyasının önerdiği tek `infrastructure/tasks.py` (backup +
error-digest birleşimi) uygulanmadı — bu iki dosya hiç taşınmadı (yukarı
"NE YAPMAZ" bölümüne bkz., ikisi de cross-cutting infra kalıyor, ayrıca
birbiriyle ilgisiz iki concern'ü tek dosyada birleştirmek B.1'i ihlal
ederdi).

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar)

1. **`HealthService`** (`application/health_service.py`) — genuine
   mutable state: `self.start_time` (uptime hesaplama) + `self._bg_tasks`
   (asyncio Task GC-koruma seti, manuel backup tetikleme için). Trip'in
   `stats_refresh.py::_bg_stats_tasks` ile aynı gerekçe kategorisi.
2. **`AdminConfigRepository`** (`infrastructure/repository.py`) —
   repository pattern istisnası (tüm modüllerde repo bir sınıf).

**Dissolve edilenler** (B.1 gereği, gerçek mutable state yoktu — her
metod zaten kendi bağımlılığını taze kuruyordu):
- `KonfigService` → `application/konfig_service.py` free function'ları
  (`get_all_by_group`, `get_all_configs`, `get_config_value`,
  `update_config`, `get_config_history`). Tek alan `self.repo` her
  çağrıda `get_admin_config_repo(session)` ile trivially yeniden
  kurulabiliyordu.
- `AdminAuditService` → `application/admin_audit_service.py`
  (`log_action`, `log_login`, `log_config_change`). Sınıf zaten hiçbir
  alan tutmuyordu, her metod kendi `UnitOfWork`'ünü açıyordu.
- `InternalService` → `application/telegram_bridge.py` (`get_sofor_by_
  telegram_id`, `kaydet_belge`, `get_seferler`, `get_sofor_id`,
  `report_driver_breakdown`, `olustur_pdf`, `get_coaching_snapshot`).
  Tek alan `self._sofor_repo` her çağrıda `get_sofor_repo()` ile
  trivially yeniden kurulabiliyordu. Container'ın `internal_service`
  lazy-property'si ve `.importlinter`'daki karşılık gelen ignore satırı
  da kaldırıldı (artık DI-injected bir servis yok).

## Public API (public.py imzaları)

```python
# Sistem konfigürasyonu
get_all_by_group(session, group) -> list[dict]
get_all_configs(session) -> list[dict]
get_config_value(session, key, default=None) -> Any
update_config(session, key, value, user_id=None, reason=None) -> dict
get_config_history(session, key, limit=10) -> list[dict]

# Runtime-config okuma köprüsü (diğer modüllerin env yerine kullandığı)
get_runtime_value(key, fallback, uow=None) -> Any
get_runtime_float(key, fallback, uow=None) -> float

# Audit logu
log_action(user, aksiyon_tipi, hedef_tablo=None, hedef_id=None, ..., request=None, ...) -> AdminAuditLog
log_login(user, request, basarili=True) -> None
log_config_change(user, key, old_val, new_val, request) -> None

# Dış entegrasyon secret'ları
KNOWN_SERVICES, BOT_TOKEN_SERVICES, IntegrationStatus
get_integration_secret(servis_adi, env_fallback=None) -> Optional[str]
set_integration_secret(servis_adi, plaintext, user_id) -> None
get_integration_statuses() -> list[IntegrationStatus]

# Idempotency-key altyapısı (trip/fuel yazma uçları kullanır)
IdempotencyKeyConflictError, IdempotencyKeyInProgressError
reserve_or_get_cached(key, ...) -> ...
finalize_response(key, response) -> None
release_reservation(key) -> None

# Sağlık kontrolü (sınıf istisnası)
HealthService, get_health_service() -> HealthService

# Telegram bot köprüsü
get_sofor_by_telegram_id(telegram_id) -> Optional[dict]
kaydet_belge(telegram_id, belge_tipi, image_bytes, content_type, telegram_mesaj_id=None) -> dict
get_seferler(telegram_id, limit=10) -> Optional[list[dict]]
get_sofor_id(telegram_id) -> Optional[int]
report_driver_breakdown(telegram_id, *, detaylar="", acil=False) -> dict
olustur_pdf(telegram_id, baslangic, bitis) -> Optional[bytes]
get_coaching_snapshot(telegram_id) -> Optional[dict]

# error_events admin yönetim yüzeyi
list_error_events(layer=None, severity=None, resolved=False, page=1, page_size=50) -> tuple[list[dict], int]
get_error_stats() -> list[dict]
resolve_error_event(event_id, user_id) -> bool
get_trace_chain(trace_id) -> dict

# ML training WebSocket connection manager (api katmanından, bkz. gotcha)
training_ws_manager: ConnectionManager

# Repository
AdminConfigRepository, get_admin_config_repo(session) -> AdminConfigRepository

# Docker container sağlık sorgusu (Telegram bot container'ları, admin Integrations paneli)
get_container_status(compose_service: str) -> ContainerStatus
```

**Dalga 17 (platform-infra) eklentisi**: `infrastructure/container_health.py`
`app/infrastructure/monitoring/container_health.py`'den taşındı — tek
çağıranı `api/admin_integrations_routes.py` idi (monitoring alt
sisteminin genel-amaçlı bir parçası değil, admin_platform'un kendi
Integrations panel özelliği). `v2.modules.platform_infra.monitoring`'e
(models/emit) bağımlılığı yok, yalnız `httpx`/`app.config`/logger kullanıyor.

## Yayınladığı / dinlediği event'ler (events.py)

Kendi `EventType`'ını tanımlamaz, `app.infrastructure.events.event_bus`
üzerinden hiçbir domain event yayınlamaz/dinlemez. `update_config` yalnız
ham Redis pub/sub kanalı `"config_updates"`'e yayın yapar (multi-worker
cache invalidation, domain event bus'tan kasıtlı ayrı — detaylar
`events.py`'de).

## Şema & tablo sahipliği

`sistem_konfig` (`SistemKonfig` — `AdminConfigRepository`), `konfig_gecmis`
(`KonfigGecmis` — değişiklik geçmişi, aynı repo), `admin_audit_log`
(`AdminAuditLog` — `admin_audit_service.log_action` yazar; kolon adları
kök CLAUDE.md'nin "admin_audit_log — Türkçe column names" bölümünde),
`entegrasyon_ayarlari` (`EntegrasyonAyari` — `integration_secrets.py`,
write-only: plaintext bir kez yazılır, asla geri okunmaz), `idempotency_keys`
(`IdempotencyKey` — `idempotency_service.py`).

`error_events`/`error_occurrences`/`error_hourly_stats` KISMEN bu modülün
kapsamında: YAZIM yolu `v2/modules/platform_infra/monitoring/` (cross-cutting,
bu modüle ait değil), admin_platform yalnız `application/error_events.py`
üzerinden admin-facing OKUMA/YÖNETİM katmanını sağlar (`system_routes.py`).

## Sınıf istisnası olmayan ama sınıf kalan altyapı: AVL scaffolding

`infrastructure/integrations/{registry.py, avl/base.py, avl/mobiliz.py}`
— `AVLProvider` Protocol + `MobilizAVLProvider` adapter, hepsi stub
(`fetch_trips`/`fetch_transactions` `NotImplementedError` fırlatır,
`healthcheck()` her zaman `False`). Hiçbir prod kod `get_avl_provider()`/
`get_fuel_provider()`'ı çağırmıyor (`docs/onboarding/API_ENTEGRASYON.md`'nin
"Şu an için sınırlamalar" bölümü zaten bunu dokümante ediyor). Silinmedi —
task dosyasının kararı "taşı", gelecekteki gerçek entegrasyon için gerçek
bir Protocol/adapter iskeleti.

**`registry.py`'nin tek-görev istisnası (dürüst not, dalga 15'in kendi
denetiminde bulundu)**: bu dosya İKİ ayrı sağlayıcı-seçim sorumluluğunu
bir arada taşıyor — `get_avl_provider()`/`AVL_PROVIDERS` (admin_platform'un
kendi AVL alanı) VE `get_fuel_provider()`/`FUEL_PROVIDERS` (fuel modülünün
`OpetFuelProvider`'ını `v2.modules.fuel.public`'ten cross-module import
ederek seçen, fuel'e ait bir sorumluluk). Bu B.1'in "bir dosya = bir görev"
ilkesini katı anlamda ihlal ediyor. Bilinçli olarak BÖLÜNMEDİ: (1) hem
`get_avl_provider()` hem `get_fuel_provider()` sıfır prod çağıranlı saf
stub'lar (yukarıdaki paragraf) — bölme riski olmadan da davranış
etkilenmiyor; (2) fuel'in kendi CLAUDE.md'si bu dosyanın nihai adresini
zaten `platform_infra` (henüz başlamamış modül, kök CLAUDE.md'nin modül
tablosuna bkz.) olarak öngörmüştü — `admin_platform`'a taşınması yalnızca
`platform_infra` doğana kadarki ARA (interim) bir karar, iki kalıcı ev
arasında geçici bir duraktır, kalıcı mimari karar değil. `platform_infra`
başladığında bu dosya oraya taşınmalı (veya en azından iki ayrı registry
dosyasına bölünüp her biri kendi modülüne gitmeli). İmport-linter bunu
bir ihlal olarak görmüyor (`v2.modules.fuel.public` üzerinden, sanctioned
surface) — yalnız B.1'in ruhuna aykırı, mektubuna değil.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **driver (taşındı, ters yön)**: `telegram_bridge.py` →
  `v2.modules.driver.public.{get_by_sofor_id, get_sofor_repo,
  get_driver_coaching_engine, SoforSeferPDFService}`.
- **fleet (taşındı, ters yön)**: `telegram_bridge.py::report_driver_
  breakdown` → `v2.modules.fleet.public.create_breakdown`.
- **auth_rbac (taşındı)**: her `api/*.py` route dosyası →
  `v2.modules.auth_rbac.public.require_yetki`.
- **trip (taşındı, ileri yön)**: `api/trip_write_routes.py` →
  `admin_platform.public.{reserve_or_get_cached, finalize_response,
  release_reservation, IdempotencyKeyConflictError,
  IdempotencyKeyInProgressError}` (sefer create idempotency guard'ı).
  Ters yön: `sefer_timeline_repo.py` bu dalgada admin_platform'dan
  trip'e taşındı (yukarı "Dosya envanteri düzeltmeleri" bölümüne bkz.).
- **fuel (taşındı, ileri yön)**: `api/fuel_routes.py` → aynı
  idempotency fonksiyonları + `admin_platform.api.internal_routes`'un
  `_ALLOWED_MIME_TYPES`/`_looks_like_allowed_image` private yardımcıları
  (önceden `app.api.v1.endpoints.internal`'dan aynı desende alınıyordu —
  mekanik taşıma, davranış değişikliği yok).
- **anomaly, prediction_ml, route_simulation, ai_assistant, openroute_service
  (app/core/services/, henüz taşınmadı) (ileri yön)**:
  `public.get_runtime_float`/`get_integration_secret` — runtime config
  okuma + dış API anahtarı çözümleme tek kanonik yoldan.
- **prediction_ml (taşındı, ters yön)**: `application/ml_service.py` →
  `admin_platform.public.training_ws_manager` (eğitim ilerlemesi
  WebSocket broadcast'i).
- **auth_rbac (taşındı, ters yön #2)**: `setting_repository.py` bu
  dalgada admin_platform'dan auth_rbac'a taşındı.

**Task dosyasının kendi notu (kabul kriteri #4, burada dokümante edilir)**:
`TASKS/modules/admin-platform.md` §4, `internal.py`+`internal_service.py`
(→ `api/internal_routes.py`+`application/telegram_bridge.py`) ikilisinin
"tek-modüle temiz oturmadığını" kendisi işaretlemişti — bu ikili gerçekte
Docker-internal Telegram-bot köprüsü ama ağırlıklı olarak **driver-yüzlü**
(belge upload, coaching snapshot, sofor seferler, PDF — hepsi şoför
verisine dokunuyor, admin_platform'un kendi tablolarına değil).
admin_platform'da kalması savunulabilir (bot-token bootstrap +
internal-token auth guard'ı gerçekten admin_platform'un "dış entegrasyon
erişimi" sorumluluğuna giriyor) ama **saf** değil — gelecekte ayrı bir
"integration-bridge" modülü açılırsa (Docker-internal servis-servis
köprüleri için, yalnız bu ikili değil, benzer başka köprüler de varsa)
bu ikili ilk taşınacak aday. Şimdilik bölünmedi: `telegram_bridge.py`'nin
7 fonksiyonu tek bir tutarlı üst-anlatıya sahip ("Telegram bot'un backend
tarafı temsilcisi") — driver modülüne bölünseydi, admin_platform'un kendi
sorumluluğu olan bot-token/internal-token auth guard'ı ile birlikte
yaşayan cohesive bir dosya kaybedilirdi.

## Modüle özel iş kuralları & gotcha'lar

- **`training_ws_manager` api katmanından public.py'ye sızıyor**:
  `ConnectionManager()` instance'ı `api/admin_ws_routes.py`'de modül
  seviyesinde tanımlı (route dosyasının kendisi WebSocket bağlantılarını
  saklıyor). `public.py` kendi modülünün `api/`'sinden import edebilir
  (`.importlinter`'ın `admin_platform.public -> admin_platform.**` ignore
  kuralı) — ama bu, api-katmanı state'inin application-katmanı
  tüketicilere (prediction_ml'in `ml_service.py`'si) sızdığı tek yer.
  Mekanik taşıma sırasında davranış korundu, gelecekte bu instance'ı
  `application/`'a taşımak temiz bir iyileştirme olur (bu dalganın
  kapsamı dışında bırakıldı).
- **`internal_routes.py` → `fuel/api/fuel_routes.py` private-isim importu**:
  `_ALLOWED_MIME_TYPES`/`_looks_like_allowed_image` (alt çizgili, gizli
  isimler) `fuel_routes.py` tarafından doğrudan import ediliyor —
  public.py'den DEĞİL. Bu, taşımadan ÖNCE de aynı desende
  `app.api.v1.endpoints.internal`'dan alınıyordu; mekanik taşıma bunu
  birebir korudu, yeni bir sızıntı değil.
- **`get_internal_service`/`InternalService` container property'si
  kaldırıldı**: DI container'ın (o zaman `app/core/container.py`, dalga
  17'de `v2/modules/platform_infra/container.py`'ye taşındı) `internal_service`
  lazy property'si ve `__init__`'teki `self._internal_service` alanı silindi
  — dissolve edilen sınıfın artık DI-injected bir instance'ı yok, her
  tüketici `telegram_bridge.py`'nin free function'larını doğrudan
  çağırıyor.
- **`log_login` hiçbir prod call site'ı yok**: yalnız kendi test dosyasında
  egzersiz ediliyor (login akışı şu an bunu çağırmıyor) — sınıftan
  dissolve edilirken davranış korundu, yeni bir "ölü kod" bulgusu değil
  (eski sınıfta da aynı durumdaydı).

## İzin verilen / yasak import'lar (import-linter özeti)

`public-surface-only-admin_platform` kontratı: `application/` diğer 14
modülün yalnız `public`/`events`'ini import edebilir. `14 modulun domain/
infrastructure katmanlari birbirinden bagimsiz` kontratına
`admin_platform.domain`/`admin_platform.infrastructure` eklendi (domain/
şu an boş — bu modülde pure/I/O-suz bir hesaplama katmanı yok, tüm mantık
ya application ya infrastructure'da). `Modul-ici katman sirasi` kontratına
(`api → application → infrastructure → domain`) `v2.modules.admin_platform`
container olarak eklendi. Diğer 14 modülün her birinin kendi
`public-surface-only-X` kontratına `admin_platform.{api,application,
domain,infrastructure}` 4 satırı eklendi (yeni modül, herkesin forbidden
listesinde yer alması gerekiyordu). `app.core.container -> app.core.
services.internal_service` ignore satırı 16 kontrattan kaldırıldı (artık
mevcut değil); `app.core.container -> app.core.services.health_service`
→ `app.core.container -> v2.modules.admin_platform.application.
health_service`'e güncellendi (16 kontratın hepsinde).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`konfigrasyon/ayar`=config/setting, `yeniden başlat gerektirir`=requires
restart, `entegrasyon`=integration, `gizli anahtar`=secret key,
`yapılandırılmamış`=not configured, `denetim kaydı`=audit log,
`aksiyon tipi`=action type, `hedef tablo`=target table, `başarılı`=
successful, `hata mesajı`=error message, `süre`=duration, `iz kimliği`=
trace id, `çözüldü`=resolved, `sağlık`=health, `devre kesici`=circuit
breaker, `yedekleme`=backup, `belge`=document (OCR upload).

## Test stratejisi

- `app/tests/unit/test_services/test_konfig_service.py` — `KonfigService`
  sınıfının dissolve edilmiş free-function çağrılarına çevrildi
  (`konfig_service.get_config_value(session, ...)` vb., `session=None`
  ile mock repo/cache/pubsub patch'lenir).
- `app/tests/unit/test_services/test_admin_audit_service_coverage.py` —
  aynı desen, `admin_audit_service.log_action`/`log_login`/
  `log_config_change` modül-seviyesi fonksiyonlarına çevrildi.
- `app/tests/unit/test_services/test_internal_service_coverage.py` —
  gerçek DB entegrasyon testleri (`@pytest.mark.integration`),
  `InternalService()` instantiation'ları `telegram_bridge.<fn>()` free
  function çağrılarına çevrildi. Trivial placeholder `test_internal_
  service.py` (yalnız `service is not None` assert'leri, hiç gerçek
  coverage değeri yoktu) silindi.
- `app/tests/api/test_internal_coverage.py` — `_override_internal_service`
  (FastAPI `Depends()` override) deseni tamamen kaldırıldı; artık
  `_patch_bridge(**overrides)` helper'ı `v2.modules.admin_platform.api.
  internal_routes.<fn>` üzerinde doğrudan patch yapıyor (route'lar artık
  free function'ları modül-seviyesinde import ediyor, DI injection point'i
  yok).
- `app/tests/unit/test_repositories/test_sefer_timeline_repo_coverage.py`
  (eski `test_audit_repo_coverage.py`'den yeniden adlandırıldı) —
  `AuditRepository.<staticmethod>` çağrıları `sefer_timeline_repo.<fn>`
  modül-seviyesi çağrılarına, `get_sefer_timeline(uow=...)` mock UoW
  (`MagicMock(session=mock_session)`) enjeksiyonuna çevrildi.
- `app/tests/unit/test_services/test_sefer_prediction_contract.py` —
  `AuditRepository._normalize_event_type` çağrısı `sefer_timeline_repo.
  _normalize_event_type`'a güncellendi (trip'e taşınan dosyadan import).
- Free-function `unittest.mock.patch` hedefi diğer 14 modülle tutarlı:
  modül-seviyesi import'lar için **tüketen modülün namespace'i**
  (`internal_routes.get_sofor_by_telegram_id` gibi), fonksiyon-içi
  (inline) import'lar için **kaynak modül**.
