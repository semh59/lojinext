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
`RBACViolationTracker`, bugün `v2/modules/platform_infra/monitoring/security_probe.py`'de
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

# Roles (RBAC role CRUD — module import, `role_service.<fn>`)
role_service.list_roles() -> list[Rol]
role_service.get_role(role_id) -> Rol
role_service.create_role(ad, yetkiler, current_user) -> Rol
role_service.update_role(role_id, ad, yetkiler, current_user) -> Rol
role_service.delete_role(role_id) -> str            # döner: silinen rolün adı
role_service.assert_no_privilege_escalation(current_user, yetkiler) -> None

# RBAC
Permission(IntFlag)                                # NONE/READ/WRITE/DELETE/ADMIN/SUPERADMIN
SecurityService.has_permission(user, required) -> bool
SecurityService.verify_permission(user, required) -> None     # raises 403
SecurityService.verify_ownership(user, owner_id, field_name="sofor_id") -> None
SecurityService.apply_isolation(user, filters, field_name="sofor_id") -> dict
PermissionChecker(required_permission)             # FastAPI Depends factory
require_yetki(permission) -> PermissionChecker

# JWT / password hashing
# DÜZELTME (2026-07-15, dedektif denetiminde bulundu): jwt_handler.py TAM bir
# "delegasyon katmanı" DEĞİL — 8 fonksiyondan yalnız 3'ü (get_password_hash/
# verify_password/create_access_token) domain/security.py'ye delege eder;
# create_refresh_token/hash_token/verify_token_hash/decode_token/
# decode_refresh_token/get_decode_key SADECE jwt_handler.py'de yaşar, security.py'de
# karşılığı yok (JWT oturum-token yaşam döngüsü onun asıl sorumluluğu). Ayrıca
# hash_password()/verify_password_core() (security.py'den doğrudan export) ile
# jwt_handler.get_password_hash()/jwt_handler.verify_password() AYNI capability'ye
# iki farklı public isimden erişim sağlıyor — davranış hatası değil ama gelecekte
# drift riski taşıyan gereksiz ikili-yüzey, bilerek dokümante ediliyor.
jwt_handler.create_access_token(data, expires_delta=None) -> str
jwt_handler.create_refresh_token(data, expires_delta=None) -> str
jwt_handler.decode_token(token, audience=None) -> dict
jwt_handler.decode_refresh_token(token) -> dict
jwt_handler.hash_token(token) -> str               # SHA-256, oturum/reset token storage
jwt_handler.verify_token_hash(token, token_hash) -> bool
jwt_handler.get_password_hash(password) -> str     # bcrypt, delegates to domain/security.py
jwt_handler.verify_password(plain, hashed) -> bool
hash_password(password) -> str                      # domain/security.py kanonik (jwt_handler.get_password_hash bunu sarar)
verify_password_core(plain, hashed) -> bool
create_access_token_core(data, expires_delta=None) -> str
get_jwks() -> dict                                  # RS256 JWKS endpoint desteği

# Token blacklist (Redis-backed, logout revocation)
TokenBlacklist, blacklist                           # module-level singleton instance
blacklist.add(token, expires_at) -> None
blacklist.is_blacklisted(token) -> bool              # fail-secure: Redis down → True

# License (araç/sefer ticari limit kontrolü — sınıf, bkz. istisna notu)
LicenseEngine, get_license_engine()

# Repositories (3 ayrı dosya: infrastructure/kullanici_repository.py,
# infrastructure/rol_repository.py, infrastructure/session_repository.py —
# driver/fuel/location'daki "her repository.py = tek sınıf" deseniyle
# tutarlı; 2026-07-15'e kadar üçü tek dosyadaydı, dedektif denetiminde
# B.1 ihlali olarak bulunup bölündü, bkz. aşağıdaki not)
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

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar — 4 adet)

**DÜZELTME (2026-07-15, dedektif denetiminde bulundu):** bu liste önceden 3
sınıf sayıyordu, `PermissionChecker` unutulmuştu — `public.py`'de export
edilen gerçek bir sınıf olmasına rağmen. Liste şimdi tam.

1. **`SecurityService`** (`domain/security_service.py`) — yalnız
   `@classmethod` içerir, hiçbir constructor/instance-state yok.
   `UserService`/`PreferenceService`'in aksine hiçbir zaman bir DI/constructor
   parametresi taşımadı — free function'a bölünmedi çünkü zaten stateless bir
   isim alanı (Permission enum ile birlikte gruplu kullanım), CRUD-benzeri bir
   servis değil.
2. **`LicenseEngine`** (`application/license_service.py`) — env'den bir kez
   yüklenen `_LICENSE_HASHES` mutable state'i olan, `v2/modules/
   platform_infra/container.py` lazy-property singleton'ı olarak yaşayan bir
   motor. Driver'ın
   `DriverPerformanceML`'iyle aynı gerekçe sınıfı (mutable durum, yeniden
   hesaplaması pahalı/anlamsız).
3. **`TokenBlacklist`** (`infrastructure/token_blacklist.py` — 2026-07-18'de
   `domain/`'den taşındı: Redis I/O yapan bir sınıf domain'de duramaz) — `__new__`'de
   thread-safe singleton deseni (`_instance`/`_lock`), Redis-backed. Zaten
   stateless bir wrapper ama sınıf-tabanlı singleton deseni pre-migration'dan
   korundu (davranış değişikliği gerektirmiyor, dokunulmadı).
4. **`PermissionChecker`** (`domain/permission_checker.py`) — `__init__(self,
   required_permission)` + `__call__` ile klasik FastAPI
   `Depends(SomeClass(param))` closure/dependency-factory deseni. Yukarıdaki
   3 resmi gerekçeden hiçbirine harfiyen uymuyor (client-injected pipeline
   değil, mutable/singleton motor değil, classmethod-only namespace de değil
   — gerçek instance-state'i var: `self.required_permission`), ama FastAPI'nin
   parametrik `Depends()` mekanizması saf bir fonksiyonla ifade edilemez
   (bound-parameter taşıyan bir callable gerekir) — bu yüzden meşru, ayrı bir
   5. gerekçe kategorisi: **(d) FastAPI dependency-factory closure'ı**.

## Yayınladığı / dinlediği event'ler (events.py)

**Diğer taşınan modüllerden FARKLI**: `v2/modules/platform_infra/events/event_bus.py::EventType`
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
`v2/modules/platform_infra/monitoring/security_probe.py`'de yaşıyor —
process-local in-memory state (multi-worker/multi-replica deployment'ta her
worker kendi sayacını tutuyor, brute-force/RBAC-ihlali tespiti worker'lar
arası paylaşılmıyor). Bu modülün sınırları İÇİNDE mantıksal olarak ait
olmasına rağmen, ÇÖZÜMÜ (Redis-backed hale getirme) bilinçli olarak ayrı bir
FAZ2 görevine bırakıldı: `TASKS/faz2-guvenlik-state-redis.md`. Bu dalgada
dokunulmadı, davranış değişikliği yok.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

**DÜZELTME (2026-07-17 B.1 dedektif denetimi):** bu bölüm önceden "diğer
modüller require_yetki/Permission'a deps.py üzerinden dolaylı erişiyor"
diyordu — bu YANLIŞTI. Gerçekte 7 v2 modülü (`analytics_executive`,
`anomaly`, `fleet`, `import_excel`, `notification` — hem api/ hem
application/'da —, `reports`) + `app/core/services/sefer_read_service.py`
+ 5 admin endpoint (`admin_calibration.py`/`admin_config.py`/
`admin_health.py`/`admin_integrations.py`/`admin_ml.py`/`error_stream.py`)
+ 3 script `require_yetki`/`Permission`/`SecurityService`/
`get_password_hash`'i `domain`/`application`'dan DOĞRUDAN import
ediyordu, `public.py`'yi tamamen atlıyordu. Hepsi düzeltildi.

- **admin_platform (senkron, henüz taşınmadı)**: en yoğun tüketici — 6
  endpoint (`admin_calibration.py`/`admin_config.py`/`admin_health.py`/
  `admin_integrations.py`/`admin_ml.py`/`error_stream.py`) artık
  `require_yetki`/`Permission`/`SecurityService`'i `auth_rbac.public`
  üzerinden çekiyor; `get_current_user`/`get_current_active_user` hâlâ
  `app/api/deps.py` üzerinden (o dosya kendisi composition-root
  istisnası, aşağıya bkz.).
- **notification (senkron, zaten taşınmış)**: iki yönlü —
  `auth_rbac→notification`: `auth_routes.py::request_password_reset`
  `v2.modules.notification.public.send_password_reset` çağırır
  (2026-07-18: public'e çevrildi). `notification→auth_rbac`: `notification_routes.py`
  (`require_yetki`) ve `application/quiet_hours.py` (`get_preferences`)
  artık `auth_rbac.public` üzerinden.
- **fleet, anomaly, import_excel, analytics_executive, reports** —
  `require_yetki`'yi artık `auth_rbac.public` üzerinden import ediyor.
- **trip, fuel, driver, route_simulation, prediction_ml** — bu modüller
  henüz auth_rbac'a doğrudan bir simge import etmiyor (yalnız `app/api/
  deps.py`'nin genel `get_current_active_user`/`require_permissions`
  wiring'ini dolaylı kullanıyor).

## Modüle özel iş kuralları & gotcha'lar

- ✅ **DÜZELTİLDİ (2026-07-15/16, ilk 9 dalganın tam-yeniden dedektif
  denetiminde bulundu)** — 2 çapraz-modül/katman bulgusu:
  (1) `LicenseEngine.check_car_limit()` (`application/license_service.py`)
  `Arac` tablosuna doğrudan (ORM) erişiyordu — fleet zaten tam taşınmış
  olduğu için `v2.modules.fleet.public.count_active_vehicles()` (fleet'in
  zaten var olan `AracRepository.count_active()`'ini saran yeni ince
  wrapper) üzerinden çağrılacak şekilde düzeltildi. `check_monthly_trip_limit()`'in
  `Sefer` erişimi trip modülü henüz taşınmadığı için (delege edilecek
  `public.py` yok) BİLİNÇLİ, dokümante geçici borç olarak bırakıldı
  (fonksiyonun kendi docstring'inde not var). (2) `api/ws_ticket_routes.py`
  `application/`'ı tamamen atlayıp Redis'e (`set_redis_val`) doğrudan
  yazıyordu — yeni `application/create_ws_ticket.py`'ye taşındı (route
  handler'ıyla aynı isim çakışması burada da vardı, `as
  create_ws_ticket_usecase` alias'ıyla düzeltildi). Mekanik, davranış
  değişikliği yok.
- **`app/api/deps.py` taşınmadı** — FastAPI-wiring katmanı (driver/fleet
  dalgalarındaki kararla aynı), yalnızca import kaynakları
  `v2.modules.auth_rbac.domain.security_service` (Permission/SecurityService,
  değişmedi) ve `v2.modules.auth_rbac.infrastructure.token_blacklist`
  (2026-07-18'de `domain/`'den `infrastructure/`'a taşınan yeni yol) olarak
  güncellendi; deps.py'nin public.py YERİNE domain/infrastructure-leaf
  import etmesi bilinçli — public, `PermissionChecker` üzerinden deps.py'nin
  kendisini import ettiği için döngü oluşur, deps.py içinde yorumla
  dokümante. `get_auth_service`/`AuthServiceDep` KALDIRILDI (yukarı bakınız).
- **Super-admin break-glass bypass** (`api/auth_routes.py::login`) —
  `SUPER_ADMIN_PASSWORD` env değişkeni + IP-scoped rate-limit bucket
  (`super_admin_login:{ip}`, 5dk'da 3 deneme) — genel `auth_token` bucket'ından
  AYRI (2026-07-01 prod-grade denetimi P1 fix'i, taşımayla DEĞİŞMEDİ).
- **Bcrypt event-loop blocking fix** (`application/auth_service.py::_authenticate`) —
  `asyncio.to_thread(jwt_handler.verify_password, ...)` — connection-pool-leak
  bug'ının 2. kök nedeniydi (`TASKS/bug-connection-pool-leak-under-load.md`),
  taşımayla KORUNDU.
- **Fail-secure token blacklist** (`infrastructure/token_blacklist.py::is_blacklisted`) —
  Redis erişilemezse token'ı REVOKED say (SEC-004), taşımayla değişmedi.
- **Privilege-escalation guard'ı** (`application/role_service.py::assert_no_privilege_escalation`)
  — çağıran, kendisinde olmayan bir yetkiyi başka role veremez
  (super_admin/wildcard `*` hariç) — hem `create_role` hem `update_role`'da
  uygulanır.
- ✅ **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu, `TASKS/bug-route-layer-bypasses-application.md`)** —
  `api/admin_role_routes.py` diğer 5 auth_rbac route dosyasının aksine
  `application/`'a delege etmiyordu, `RolRepository`'yi doğrudan
  örnekliyordu; privilege-escalation guard'ı da `create_role` içinde
  (bağımsız inline kod) ve `_assert_no_privilege_escalation` fonksiyonunda
  (`update_role` için) iki kez neredeyse birebir tekrarlanmıştı.
  `application/role_service.py`'ye taşındı, guard tek fonksiyona
  (`assert_no_privilege_escalation`) indirgendi. Mekanik, davranış
  değişikliği yok.

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

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-auth_rbac` kontratı: `application/`
diğer modüllerin yalnız `public`/`events`'ini import edebilir (KEPT).
Diğer modüller bu modüle yalnız `v2.modules.auth_rbac.public` üzerinden
erişir; istisnalar (kontrat ignore listesinde dokümante): `app/api/deps.py`
(composition-root — public'e geçmek `PermissionChecker` üzerinden döngü
üretir), `v2/modules/platform_infra/container.py`/`app/database/repositories/__init__.py`
(proje-geneli DI-wiring istisnası), `app/main.py`/`app/infrastructure/
websocket/ws_auth.py` (2026-07-18'den beri public üzerinden).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`kullanıcı`=user, `rol`=role, `yetki`=permission, `oturum`=session,
`kara liste`=blacklist, `şifre sıfırlama`=password reset,
`ayrıcalık yükseltme`=privilege escalation, `lisans`=license,
`tercih`=preference.
