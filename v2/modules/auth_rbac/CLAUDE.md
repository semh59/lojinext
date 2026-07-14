# Modül: auth_rbac

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

JWT login/refresh/logout + oturum yönetimi, kullanıcı CRUD'u (admin +
self-service), rol/yetki (RBAC) CRUD'u, granular permission-check (`Permission`
bitwise enum + string-key `require_yetki`), token blacklist (Redis-backed,
logout revocation), kullanıcı tercihleri (kayıtlı filtre/sütun ayarları),
lisans/ticari kısıt motoru (`LicenseEngine` — araç/sefer limit kontrolü),
WebSocket bağlantı bileti (`ws_ticket`). `kullanicilar`, `roller`,
`kullanici_oturumlari`, `kullanici_ayarlari` tablolarının tek sahibi.

NE YAPMAZ: multi-worker güvenlik state'i (`BruteForceDetector`/
`RBACViolationTracker`, bugün `app/infrastructure/monitoring/security_probe.py`'de
— platform-infra'da cross-cutting infra olarak KALIYOR, bu modüle
taşınmadı). Redis-backed hale getirilmesi **FAZ2 görevi**
(`TASKS/faz2-guvenlik-state-redis.md`) — dalga 6'nın kapsamı dışında,
bilinçli olarak ertelendi.

## Public API (public.py imzaları)

```python
# Auth (module import — login/refresh/session/password-reset)
auth_service.authenticate(email, password, request, uow=None) -> (access_token, refresh_token)
auth_service.refresh_session(refresh_token, uow=None) -> (access_token, refresh_token)
auth_service.revoke_session(user_id, uow=None) -> None
auth_service.request_password_reset(email, uow=None) -> str | None
auth_service.reset_password(token, new_password, uow=None) -> bool

# User CRUD
list_users(skip=0, limit=100, uow=None) -> list[dict]
get_user(user_id, uow=None) -> dict
create_user(data: dict, created_by_id: int, uow=None) -> dict
update_user(user_id, data: dict, uow=None) -> dict
delete_user(user_id, uow=None) -> bool                       # soft delete (aktif=False)
change_password(user_id, current_password, new_password, uow=None) -> bool

# Preferences
get_preferences(user_id, modul, ayar_tipi=None, uow=None) -> list[KullaniciAyari]
save_preference(user_id, modul, ayar_tipi, deger, ad=None, is_default=False, uow=None) -> KullaniciAyari
delete_preference(user_id, pref_id, uow=None) -> bool
set_default(user_id, pref_id, uow=None) -> bool

# RBAC
Permission(IntFlag)                                # NONE/READ/WRITE/DELETE/ADMIN/SUPERADMIN
SecurityService.has_permission(user, required) -> bool
SecurityService.verify_permission(user, required) -> None     # raises 403
SecurityService.verify_ownership(user, owner_id, field_name="sofor_id") -> None
SecurityService.apply_isolation(user, filters, field_name="sofor_id") -> dict
PermissionChecker(required_permission)             # FastAPI Depends factory
require_yetki(permission) -> PermissionChecker

# JWT / password hashing (domain/jwt_handler.py — delegation katmanı,
# domain/security.py kanonik implementasyon)
jwt_handler.create_access_token(data, expires_delta=None) -> str
jwt_handler.create_refresh_token(data, expires_delta=None) -> str
jwt_handler.decode_token(token, audience=None) -> dict
jwt_handler.decode_refresh_token(token) -> dict
jwt_handler.hash_token(token) -> str               # SHA-256, oturum/reset token storage
jwt_handler.verify_token_hash(token, token_hash) -> bool
jwt_handler.get_password_hash(password) -> str     # bcrypt, delegates to domain/security.py
jwt_handler.verify_password(plain, hashed) -> bool
hash_password(password) -> str                      # domain/security.py kanonik (jwt_handler bunu sarar)
verify_password_core(plain, hashed) -> bool
create_access_token_core(data, expires_delta=None) -> str
get_jwks() -> dict                                  # RS256 JWKS endpoint desteği

# Token blacklist (Redis-backed, logout revocation)
TokenBlacklist, blacklist                           # module-level singleton instance
blacklist.add(token, expires_at) -> None
blacklist.is_blacklisted(token) -> bool              # fail-secure: Redis down → True

# License (araç/sefer ticari limit kontrolü — sınıf, bkz. istisna notu)
LicenseEngine, get_license_engine()

# Repositories
KullaniciRepository, RolRepository, SessionRepository

# Schemas
KullaniciCreate, KullaniciRead, KullaniciUpdate, RolCreate, RolRead,
PreferenceCreate, PreferenceItem, PreferenceListResponse
```

**Önemli**: `AuthService`/`UserService`/`PreferenceService` sınıfları YOK. Her
use-case bağımsız bir fonksiyon (B.1, location/notification/fleet/fuel/driver
ile aynı karar). `auth_service.py`'nin eski hâli (`AuthService`) bir
UnitOfWork'e bağımlı PER-REQUEST sınıftı — free function'a geçişte her
fonksiyon opsiyonel `uow: UnitOfWork | None = None` alır: verilirse
DOĞRUDAN kullanılır (driver dalga 5'in score-breakdown 500 gotcha'sını
TEKRARLAMAMAK için — burada `kullanici_repo`/`rol_repo`/`session_repo`'nun
hiçbir modül-seviyeli session'sız singleton'ı olmadığı için o risk zaten
YOK, ama tutarlılık için aynı imza deseni korundu), verilmezse fonksiyon
kendi `UnitOfWork()`'ünü açar ve commit eder.

`app/api/deps.py::get_auth_service` (eski `AuthService(uow)` factory'si)
KALDIRILDI — `AuthServiceDep` artık yok. `auth_routes.py`'deki endpoint'ler
doğrudan `UOWDep` alıp `auth_service.authenticate(..., uow=uow)` gibi
çağırıyor (deps.py'nin "1. katman" DI mimarisi — transaction-scoped
servisler UoW ile açılır — aynen korundu, sadece aradaki sınıf katmanı
kalktı).

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar — 3 adet)

1. **`SecurityService`** (`domain/security_service.py`) — yalnız
   `@classmethod` içerir, hiçbir constructor/instance-state yok.
   `UserService`/`PreferenceService`'in aksine hiçbir zaman bir DI/constructor
   parametresi taşımadı — free function'a bölünmedi çünkü zaten stateless bir
   isim alanı (Permission enum ile birlikte gruplu kullanım), CRUD-benzeri bir
   servis değil.
2. **`LicenseEngine`** (`application/license_service.py`) — env'den bir kez
   yüklenen `_LICENSE_HASHES` mutable state'i olan, `app/core/container.py`
   lazy-property singleton'ı olarak yaşayan bir motor. Driver'ın
   `DriverPerformanceML`'iyle aynı gerekçe sınıfı (mutable durum, yeniden
   hesaplaması pahalı/anlamsız).
3. **`TokenBlacklist`** (`domain/token_blacklist.py`) — `__new__`'de
   thread-safe singleton deseni (`_instance`/`_lock`), Redis-backed. Zaten
   stateless bir wrapper ama sınıf-tabanlı singleton deseni pre-migration'dan
   korundu (davranış değişikliği gerektirmiyor, dokunulmadı).

## Yayınladığı / dinlediği event'ler (events.py)

**Diğer taşınan modüllerden FARKLI**: `app/infrastructure/events/event_bus.py::EventType`
içinde KULLANICI_ADDED/UPDATED/DELETED veya ROL_* için hiçbir enum değeri
YOK — bu modül hiçbir zaman event-bus'a bağlanmadı (taşımadan önce de
böyleydi, regresyon değil, `grep -rn "KULLANICI_\|ROL_ADDED"` ile
doğrulandı). `events.py` boş `__all__` ile bu durumu dokümante eder.

## Şema & tablo sahipliği

`kullanicilar`, `roller`, `kullanici_oturumlari`, `kullanici_ayarlari`.

**`kullanicilar` sistemin en büyük FK mıknatısı — ~28 inbound çapraz-şema
kenar.** Sistemdeki neredeyse her tablo bir `olusturan_id`/`guncelleyen_id`/
`onaylayan_id`/`kullanici_id` audit-actor kolonu taşır ve bu kolon
`kullanicilar.id`'ye FK'lidir (sefer/yakit/arac/anomaly/import/audit/
notification/coaching vb.). **FAZ2'nin şema-per-modül tasarımında** bu, tüm
diğer 16 modülün `auth_rbac` şemasına SELECT-only grant talep edeceği
anlamına gelir — `fk_registry.yml` taslağına özellikle not düşülmeli (bkz.
`TASKS/modules/auth-rbac.md` §3, §6). B.2 pairwise kararı: `*→auth_rbac`
HER ZAMAN senkron olmalı (kimlik/permission çözümü anlık gerekir);
audit-actor id'leri DEĞER olarak taşınır (join gerektirmez) — bu yüzden 28
FK kenarına rağmen runtime çağrı sayısı düşük kalır (sadece login/
permission-check senkron çağrılar, diğer 17 modülün auth_rbac'a `out=1`
görünmesinin sebebi).

## Multi-worker güvenlik state'i — BU MODÜLE TAŞINMADI (FAZ2 TODO)

`BruteForceDetector`/`RBACViolationTracker` bugün
`app/infrastructure/monitoring/security_probe.py`'de yaşıyor —
process-local in-memory state (multi-worker/multi-replica deployment'ta her
worker kendi sayacını tutuyor, brute-force/RBAC-ihlali tespiti worker'lar
arası paylaşılmıyor). Bu modülün sınırları İÇİNDE mantıksal olarak ait
olmasına rağmen, ÇÖZÜMÜ (Redis-backed hale getirme) bilinçli olarak ayrı bir
FAZ2 görevine bırakıldı: `TASKS/faz2-guvenlik-state-redis.md`. Bu dalgada
dokunulmadı, davranış değişikliği yok.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **admin_platform (senkron, henüz taşınmadı)**: en yoğun tüketici — 7 import
  (`admin_attribution.py`/`admin_config.py`/`admin_health.py`/
  `admin_integrations.py`/`admin_ml.py`/`admin_imports.py`/
  `fleet_insights.py`/`error_stream.py` — `require_yetki`/`get_current_user`/
  `Permission` kullanıyor).
- **notification (senkron, zaten taşınmış)**: `auth_rbac→notification` (tek
  `out` kenarı) — `auth_routes.py::request_password_reset`
  `v2.modules.notification.infrastructure.email_client.send_password_reset`
  çağırır.
- **trip, fuel, fleet, driver, route_simulation, prediction_ml, anomaly,
  import_excel, analytics_executive** (senkron, `in` kenarları) —
  `require_permissions`/`get_current_active_user` gibi `app/api/deps.py`
  wiring'ini kullanır (deps.py auth_rbac'a import eder, bu modüller deps.py'yi
  kullanır — dolaylı bağımlılık).

## Modüle özel iş kuralları & gotcha'lar

- **`app/api/deps.py` taşınmadı** — FastAPI-wiring katmanı (driver/fleet
  dalgalarındaki kararla aynı), yalnızca import kaynakları
  `v2.modules.auth_rbac.domain.security_service`/`v2.modules.auth_rbac.domain.token_blacklist`
  olarak güncellendi. `get_auth_service`/`AuthServiceDep` KALDIRILDI (yukarı
  bakınız).
- **Super-admin break-glass bypass** (`api/auth_routes.py::login`) —
  `SUPER_ADMIN_PASSWORD` env değişkeni + IP-scoped rate-limit bucket
  (`super_admin_login:{ip}`, 5dk'da 3 deneme) — genel `auth_token` bucket'ından
  AYRI (2026-07-01 prod-grade denetimi P1 fix'i, taşımayla DEĞİŞMEDİ).
- **Bcrypt event-loop blocking fix** (`application/auth_service.py::_authenticate`) —
  `asyncio.to_thread(jwt_handler.verify_password, ...)` — connection-pool-leak
  bug'ının 2. kök nedeniydi (`TASKS/bug-connection-pool-leak-under-load.md`),
  taşımayla KORUNDU.
- **Fail-secure token blacklist** (`domain/token_blacklist.py::is_blacklisted`) —
  Redis erişilemezse token'ı REVOKED say (SEC-004), taşımayla değişmedi.
- **Privilege-escalation guard'ı** (`api/admin_role_routes.py`) — çağıran,
  kendisinde olmayan bir yetkiyi başka role veremez (super_admin/wildcard `*`
  hariç) — hem `create_role` hem `update_role`'da uygulanır.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_auth_service_coverage.py`,
  `test_license_service.py`, `test_preference_service.py`,
  `test_security_service.py` — use-case fonksiyon testleri (0-mock: gerçek
  repo + `db_session`), sınıf-mock'tan free-function-mock desenine çevrildi
  (`v2.modules.auth_rbac.api.<x>_routes.<fn>` gibi TÜKETEN modül patch
  edilir — kaynak modül değil, location/fleet/fuel/driver'daki aynı gotcha).
- `app/tests/api/test_admin_users.py`, `test_auth_logout_blacklist.py`,
  `app/tests/security/test_rbac_coverage.py`,
  `app/tests/security/test_idor_notifications.py`,
  `app/tests/unit/test_rol_repository.py`,
  `app/tests/unit/test_core_security_coverage.py`,
  `app/tests/unit/test_schemas/test_user_schema_coverage.py` — endpoint +
  schema + repo testleri (`TEST_DATABASE_URL` zorunlu olanlar için).
- `app/tests/test_db_hardening.py` — connection-pool-leak regresyon testleri
  (bcrypt to_thread fix'i doğrulayan testler dahil) — dokunulmadı, yalnız
  import path güncellendi.
- Kök `tests/` klasörü de tarandı (dalga 1/4 gotcha'sı tekrarı) —
  `tests/test_admin_ws.py`, `tests/test_auth_brute_force.py`,
  `tests/test_user_admin.py`, `tests/api/test_api_integration.py`,
  `tests/conftest.py` dönüştürüldü.
