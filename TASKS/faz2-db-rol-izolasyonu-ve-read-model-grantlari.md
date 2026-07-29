# FAZ2 — DB Rol İzolasyonu + Read-Model Grant'ları

**Amaç:** Her modüle kendi şemasında ALL, başkasında yalnız granted SELECT veren PG rolleri kurmak; 42 çapraz-şema FK'yı `fk_registry.yml` ile izlenebilir kılmak; raw-SQL sınır ihlalini FAZ1'in "yaklaşık" taramasından FAZ2'nin "kesin" runtime stop'una geçirmek.

**Giriş kriteri:** `faz2-schema-per-module-postgres.md` tamamlandı — 14/14 şema kurulu. ✅ Karşılanıyor.
**Çıkış kriteri:** rol ihlali hem testte hem prod'da `permission denied`; `fk_registry.yml` ↔ `information_schema` pytest diff'i CI'da aktif.

Görev iki bağımsız dalgaya ayrıldı:

- **Wave 1 (✅ TAMAMLANDI, 2026-07-24)** — 17 rol + grant matrisi DB'de var, `fk_registry.yml` + CI testi var. **Hiçbir yerde `SET ROLE` çağrılmıyor** — sıfır davranış değişikliği, uygulama hâlâ tek login role ile çalışıyor.
- **Wave 2 (🔲 bekliyor)** — `SET LOCAL ROLE` enforcement'ının gerçekten bağlanması. **DURMA NOKTASI: Kullanıcı onayı olmadan uygulanmaz.**

---

## Wave 1 — roller + grant'lar (TAMAMLANDI)

### Rol tanımları (14 iş modülü + platform + 2 read-model + m_ops = 17 rol)

Tek doğruluk kaynağı: `v2/modules/platform_infra/database/role_grants.py`
(`MODULE_SCHEMA_ROLES`, `READER_SELECT_GRANTS`, `WRITE_EXCEPTIONS`, `m_ops`).
DDL üretimi `generate_role_grant_ddl()` — idempotent (CREATE ROLE bir
existence-check DO-block'u içinde), hem Alembic migration'ından
(`alembic/versions/0061_faz2_role_grants.py`) hem test conftest'lerinden
(`app/tests/conftest.py`, `tests/conftest.py` — her test oturumunun şema
drop/recreate döngüsünden HEMEN SONRA) çağrılıyor. Bu ikinci çağrı
kritik: conftest'ler Alembic'i hiç çalıştırmıyor (`Base.metadata.
create_all()` ile şema kuruyorlar), bu yüzden roller/grant'lar Alembic'ten
bağımsız da sıfırdan kurulabilmeli — gerçek, Alembic hiç çalışmamış bir
Postgres'e karşı doğrulandı (bkz. Doğrulama bölümü).

### Reader/grant matrisi — DÜZELTİLMİŞ (orijinal taslak YANLIŞ/eksikti)

Doğrudan kaynak okumasıyla doğrulandı (3 Explore ajanı + 1 Plan ajanı,
2026-07-24) — bu tablonun ilk hali (aşağıda ESKİ olarak işaretlendi)
birkaç noktada yanlıştı:

| Okuyucu rolü | SELECT grant aldığı şemalar | Yazma istisnası |
|---|---|---|
| `m_analytics_executive` | trip, fleet, driver, fuel, anomaly, **location** | INSERT+DELETE on `fuel.yakit_formul` (`save_model_params`, prediction_ml'den çağrılır) |
| `m_reports` | trip, fleet, driver, fuel, **anomaly** | — |
| `m_anomaly` | trip, driver, fleet | UPDATE(arac_id, sofor_id, is_corrected, correction_reason) on `trip.seferler` (`attribute_loss.py::override_attribution`) |
| `m_ai_assistant` | fleet, trip, **driver, location** | — |
| `m_fleet` | trip | — |
| `m_fuel` | fleet, trip | — |
| `m_driver` | trip | — |
| `m_prediction_ml` | fleet | — |
| `m_route_simulation` | location | UPDATE(api_mesafe_km, api_sure_saat, ascent_m, descent_m, last_api_call) on `location.lokasyonlar` (`openroute_client.py::_save_to_cache`) |
| `m_import_excel` | — | INSERT+DELETE on `fleet.araclar`, `driver.soforler`, `trip.seferler`, `fuel.yakit_alimlari`; INSERT on `driver.sofor_ad_soyad_trigram` (toplu Excel import, repository'leri bilerek bypass eder) |

**ESKİ taslağın hataları** (düzeltildi): `analytics_executive`'in
`notification`/`reports` şeması hiç okumadığı, ama `location`'ı okuduğu
gözden kaçmıştı. `reports`'un `import_excel`'i (yalnız public API
üzerinden, raw SQL değil) okumadığı, ama `anomaly`'yi okuduğu
gözden kaçmıştı. `anomaly`'nin `fuel`'i hiç okumadığı (taslakta vardı,
kaynakta yoktu) gözden kaçmıştı. `ai_assistant`'ın `fuel`'i (2026-07-17'de
public API'ye geçirildi) ve `reports`'u (hiç referans yok) OKUMADIĞI, ama
`driver`+`location`'ı okuduğu gözden kaçmıştı. Taslak ayrıca 6 ek
okuyucu/yazıcıdan (`fleet`→trip, `fuel`→fleet+trip, `driver`→trip,
`prediction_ml`→fleet, `route_simulation`→location, `import_excel`'in
toplu yazma istisnası) hiç bahsetmiyordu — bunların bir kısmı ilgili
modüllerin kendi CLAUDE.md'lerinde zaten not düşülmüştü ama bu görev
dosyasına hiç yansıtılmamıştı.

### Tasarım kararı: izolasyon sınırı "raw-SQL bypass" ile sınırlı

Bir modülün `public.py` fonksiyonu başka bir modülün zaten açık
transaction'ı İÇİNDE çağrılırsa (nested `UnitOfWork()` aynı session'ı
paylaşır — bkz. `unit_of_work.py`'nin `_owns`/`_session_ctx` mekaniği),
çağıranın rolüyle çalışmaya devam eder. Bu KASITLI: görevin amacı raw-SQL
sınır ihlalini durdurmak, her meşru public-API çağrısını yeniden
kimliklendirmek değil.

### `fk_registry.yml` (42 kenar — doğrulandı, MEMORY §2.2'nin iddiası doğru çıktı)

`arch/fk_registry.yml` — elle yazılmış/commit'lenmiş, `scripts/
faz2_generate_fk_registry_seed.py` (tek-seferlik, CI'da ÇALIŞMAZ) ile
gerçek/migrate edilmiş bir DB'ye karşı üretilip doğrulanan 42-kenar
listesi. İki kenar (`platform.error_events.user_id`/`.resolved_by` →
`auth_rbac.kullanicilar`) `v2/modules/shared_kernel/infrastructure/
error_monitoring_models.py`'de yaşıyor — `v2/modules/*/infrastructure/
models.py` glob'u bunu kaçırır, seed script'i `pg_constraint` sorgusuyla
gerçek katalogdan okuduğu için kaçırmaz.

CI testi: `app/tests/integration/test_fk_registry_matches_live_schema.py`
— `pg_constraint`/`pg_class`/`pg_namespace` sorgusuyla canlı şemayı okuyup
`arch/fk_registry.yml` ile simetrik fark alır (hem yeni dokümante
edilmemiş kenar hem bayat registry kaydı FAIL verir). `.github/workflows/
ci.yml`'ye eklendi.

### `m_ops` rolü — Wave 1'de gerçekten oluşturuldu

`faz2-schema-per-module-postgres.md`'de yalnız planlanmıştı, hiçbir yerde
yaratılmamıştı. Wave 1, 14 iş-modülü şemasının hepsinde `USAGE, CREATE` +
`ALL ON ALL TABLES/SEQUENCES` (+ `ALTER DEFAULT PRIVILEGES`) veren geniş
ama superuser-olmayan bu bakım rolünü oluşturdu. Not: `reset_business_
data.py`'nin `SET session_replication_role=replica` ihtiyacı hâlâ gerçek
superuser gerektirir — `m_ops` bunu ÇÖZMÜYOR, ayrı/elle-onaylı bir
operasyon olarak kalmaya devam ediyor (Postgres bu yetkiyi rol
üyeliğiyle devretmeyi desteklemiyor).

### Doğrulama (Wave 1, gerçek Postgres 16'da yapıldı)

- `alembic upgrade head` (0001→0061) baştan sona başarılı; `alembic check`
  temiz; `alembic downgrade 0060_platform_schema_move` → tekrar `upgrade
  head` round-trip temiz — 17 rolün hepsi drop/recreate ediliyor,
  doğrulandı (`\du` ile).
- `psql \dp`/`information_schema.role_table_grants`/`role_column_grants`
  ile spot-check: kendi şemada ALL, okuyucularda yalnız SELECT, yazma
  istisnalarının GERÇEKTEN kolon-scope olduğu (örn. `m_anomaly`
  `trip.seferler`'in yalnız 4 kolonuna UPDATE alıyor, `DELETE`/diğer
  kolonlara `UPDATE` YOK) doğrulandı.
- **Kritik test-ortamı senaryosu**: Alembic'in HİÇ çalışmadığı, sıfırdan
  bir Postgres DB'sinde (`lojinext_test_fresh`) tam bir pytest alt kümesi
  çalıştırıldı — roller/grant'lar conftest'in kendi çağrısıyla sıfırdan
  doğru kuruldu, tüm testler yeşil.
- `app/tests/integration/test_role_grants_bootstrap.py` (49 parametrized
  test — her modül rolü, her okuyucu/şema çifti, her yazma istisnası,
  m_ops) ve `test_fk_registry_matches_live_schema.py` — ikisi de yeşil,
  hem migrate edilmiş hem "fresh" DB'de.
- **Tam pytest suite (`-m "unit or not integration"`, temiz `lojinext_test`,
  Alembic'ten geçmiş DB)**: **5202 passed, 0 failed, 0 error, 17 skipped**
  — Wave 1 öncesiyle BİREBİR AYNI sonuç (yalnız yeni eklenen integration-
  only testler `deselected` sayısına eklendi: 1335→1385). Sıfır davranış
  değişikliği iddiasının nihai kanıtı.
- `ruff check --select E,F,W,I` ve `mypy` yeni dosyalarda temiz (bir
  `alembic.op` attribute-resolution uyarısı — tüm migration dosyalarının
  paylaştığı, mypy'nin alembic'in dinamik `op` proxy'sini çözememesinden
  kaynaklanan, projenin kendi baseline-relative mypy gate'inin zaten
  kapsadığı pre-existing bir durum, yeni değil).

### Kritik dosyalar (Wave 1)

- `v2/modules/platform_infra/database/role_grants.py` (yeni — tek doğruluk kaynağı)
- `alembic/versions/0061_faz2_role_grants.py` (yeni migration)
- `app/tests/conftest.py`, `tests/conftest.py` (schema-reset sonrası `apply_role_grants_async` çağrısı)
- `arch/fk_registry.yml` (yeni) + `scripts/faz2_generate_fk_registry_seed.py` (yeni, tek-seferlik)
- `app/tests/integration/test_fk_registry_matches_live_schema.py` (yeni)
- `app/tests/integration/test_role_grants_bootstrap.py` (yeni)
- `.github/workflows/ci.yml` (yeni named step)
- `app/requirements-dev.txt` (PyYAML/types-PyYAML eklendi — registry parse için)

---

## Wave 2 — enforcement (🔲 bekliyor, ayrı DURMA NOKTASI)

> **DURMA NOKTASI: Kullanıcı onayı olmadan uygulanmaz.**

Wave 1'in kurduğu roller/grant'lar bugün hiçbir yerde bağlı değil —
uygulama hâlâ tek bir login role ile çalışıyor. Wave 2 bunu gerçekten
enforce eder: bu, gerçek davranış değişikliği taşıyan, "permission
denied" regresyonlarının triyaj edilmesini gerektiren riskli kısım.

### Uygulama noktası
`v2/modules/shared_kernel/infrastructure/unit_of_work.py` — bugün
`__init__(self, session=None)`, hiç modül kavramı yok. `~168 gerçek
çağıran var`, çoğu `application/*.py` içinde derin, `public.py` sınırında
değil — "her use-case'e `module_role=` kwarg'ı geç" tarzı bir tasarım
~100+ dosyaya dokunurdu. Bunun yerine planlanan yaklaşım: bir
`ContextVar[str]` (`v2/modules/platform_infra/database/module_role.py`,
henüz yazılmadı) küçük, kapalı bir giriş-noktası kümesinde set edilir
(`api_router.py`'nin ~50 `include_router()` çağrısına `Depends(
require_module_role(...))`, `celery_app.py`'nin `task_prerun`/
`task_postrun` sinyali, 16 m_ops script'i için ayrı bir `open_role_
scoped_session()` yolu) — `UnitOfWork.__aenter__`'ın yalnız session'ı
YARATAN ("owning") dalı bu context'i okuyup `SET LOCAL ROLE` çağırır.

### Açık karar noktası — ÇÖZÜLDÜ (2026-07-28, spike)

**Karar: SQLAlchemy ORM `after_begin` event listener.**

Gerçek Postgres 16'ya karşı izole bir throwaway DB'de (`docker run
postgres:16-alpine` + `alembic upgrade head`, migration 0061'in 17
rolü/grant matrisi dahil) 6 senaryolu bir spike koşuldu
(`event.listens_for(Session, "after_begin")` + `ContextVar[str|None]` +
`connection.execute(text("SET LOCAL ROLE <rol>"))`):

1. `after_begin` hem explicit `async with session.begin()` hem SQLAlchemy
   2.0 autobegin (ilk `execute()` begin'i örtük tetikler) yolunda güvenilir
   ateşleniyor.
2. Greenlet-bridge içinde SENKRON `connection.execute()` çağrısı
   sorunsuz çalıştı — bu projede daha önce sürpriz çıkaran async+greenlet
   etkileşimi bu SQLAlchemy/asyncpg/Postgres16 kombinasyonunda
   gözlenmedi.
3. `ContextVar` ardışık iki farklı-rollü session arasında sızıntı
   yapmadı (`m_trip` → `m_fuel` sıralı çağrıda ikisi de doğru rol
   aldı).
4. `SET LOCAL ROLE` Postgres'in `LOCAL` semantiğine uygun şekilde
   rollback/commit sonrası otomatik sıfırlanıyor (yeni transaction
   `lojinext_user`'a dönüyor) — session/connection-pool arası rol
   sızıntısı riski yok.
5. **Gerçek enforcement canlı doğrulandı**: `m_trip` rolüyle
   `fleet.araclar`'a `INSERT` denemesi
   `asyncpg.exceptions.InsufficientPrivilegeError: permission denied
   for schema fleet` ile reddedildi — Wave 1'in grant matrisi hem
   yeterince kısıtlayıcı hem `SET ROLE` üzerinden fiilen etkin.

Sonuç: **3-açık-çağrı-noktası** alternatifi (UnitOfWork/get_db()/
session_scope(), ~15 bare `AsyncSessionLocal()` dosyasının
`session_scope()`'a taşınmasını gerektirirdi) elendi — `after_begin`
tek nokta olarak TÜM session yaratma yollarını (UnitOfWork'ün owning
dalı + 17 bare çağrı dosyasının hepsi) otomatik kapsıyor, hiçbir
dosyanın session-oluşturma şeklini değiştirmeye gerek yok.

### Kabul Kriterleri (Wave 2)
- [x] `module_role.py` (`ContextVar`, `module_role_scope`, `require_module_role`, `open_role_scoped_session`) — 2026-07-28, `v2/modules/platform_infra/database/module_role.py`
- [x] Enforcement noktası seçildi (spike sonucuna göre) ve bağlandı — `connection.py`'ye `after_begin` event listener eklendi (`_apply_module_role`); rol set edilmediği sürece no-op, henüz sıfır davranış değişikliği
- [x] `trip` modülünün 4 router'ı (`trip_write_router`/`trip_bulk_router`/`trip_approval_router`/`trip_read_router`) `dependencies=[Depends(require_module_role("trip"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "Pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı (`POST /trips/` → 201, iki farklı sefer)
- [x] `fleet` modülünün 4 router'ı (`vehicle_router`/`maintenance_router`/`admin_maintenance_router`/`trailer_router`) `dependencies=[Depends(require_module_role("fleet"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "fleet pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı (`POST /vehicles/` → 201, `DELETE /vehicles/{id}` → 200, `admin_audit_log`'a her iki işlem de yazıldı)
- [x] `driver` modülünün 2 router'ı (`driver_router`/`coaching_router`) `dependencies=[Depends(require_module_role("driver"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "driver pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı (`POST /drivers/` → 201, `GET /drivers/{id}/score-breakdown` → 200, `GET /coaching/{id}/insights` → 200, `DELETE /drivers/{id}` → 200)
- [x] `fuel` modülünün 2 router'ı (`fuel_router`/`admin_fuel_accuracy`) `dependencies=[Depends(require_module_role("fuel"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "fuel pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı (`POST /fuel/` → 201, `GET /fuel/stats` → 200, `GET /admin/fuel-accuracy` → 200, `DELETE /fuel/{id}` → 200) — **sıfır yeni grant açığı bulundu**, mevcut `m_fuel: ["fleet","trip"]` zaten yeterliydi (trip/fleet pilotlarında önceden düzeltilmişti)
- [x] `location` modülünün router'ı `dependencies=[Depends(require_module_role("location"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "location pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı (`POST /locations/` → 201, `GET /locations/stats` → 200, `GET /locations/geocode` → 200 gerçek Nominatim çağrısıyla, `DELETE /locations/{id}` → 200) — **sıfır yeni grant açığı bulundu** (location'ın kendi tablosu dışında raw-SQL cross-schema erişimi yok, route_simulation/prediction_ml/admin_platform bağımlılıkları hep `public.py` fonksiyon çağrısı üzerinden)
- [ ] Diğer 9 modülün routerları — kalan 9 modül aynı desenle (`dependencies=[Depends(require_module_role("<modül>"))]`) tek tek bağlanacak, her biri kendi pilot doğrulamasından geçmeli
- [ ] `celery_app.py`'nin `task_prerun`/`task_postrun` sinyali görev adından modül rolü çıkarıyor
- [ ] 16 m_ops script'i `open_role_scoped_session("m_ops")` kullanıyor
- [x] Bilinçli rol ihlali testi (yanlış modülden yazma denemesi) `permission denied` üretiyor (`test_role_isolation_enforcement.py`) — 6 test, gerçek Postgres 16'ya karşı doğrulandı
- [x] `trip` için tam regresyon + triyaj turu tamamlandı — 4 gerçek Wave 1 grant açığı bulunup düzeltildi (aşağıya bkz.); 238/238 trip/sefer/outbox entegrasyon testi + 112 Wave1/Wave2/deep_audit testi + 804 trip/sefer unit/api testi yeşil

### Pilot bulgusu (2026-07-28) — trip'in api_router.py wiring'i TAMAMLANDI

`trip`'in 4 router'ına `dependencies=[Depends(require_module_role("trip"))]`
eklenip gerçek bir backend + Postgres 16 + gerçek HTTP isteğiyle
(`POST /trips/`) uçtan uca test edildi. **4 gerçek, önceden var olan Wave 1
grant-matrisi açığı** bulunup düzeltildi (main'de, commit `573c83c` +
sonraki commit):

1. `m_trip`, `READER_SELECT_GRANTS`'te hiç yoktu — `add_trip.py`/
   `bulk_add_trips.py`/`reconcile_costs.py`/`sla.py`/
   `trip_prediction_enrichment.py` `fleet`/`driver`/`location`/`fuel`'i
   `uow.<repo>` ile okuyor, hepsi eklendi.
2. `platform.outbox_events` INSERT'i (her modülün event yayınlarken
   çağırdığı paylaşılan altyapı) hiçbir modül rolüne WriteException
   olarak tanımlı değildi — 14 modülün hepsine birden eklendi.
3. `_write_exception_stmts`'ın DDL üretiminde 2 gerçek bug bulundu:
   `GRANT USAGE ON SCHEMA` eksikti (tablo grant'ı tek başına yetersiz) ve
   `INSERT` ayrıcalıklarında sequence `USAGE`'ı hiç verilmiyordu (serial/
   identity PK'nin `nextval()`'ı için şart) — ikisi de düzeltildi.
4. **Kök neden — asıl engelleyici**: madde 1-3 düzeltildikten SONRA bile
   `POST /trips/` hâlâ `permission denied for table outbox_events` ile
   500 dönüyordu, `current_user`'ın `m_trip` olduğu ve INSERT grant'ının
   var olduğu doğrulanmış olmasına rağmen. Ham `asyncpg` ile izole tekrar
   üretilerek kanıtlandı: sorun `RETURNING id` klozuydu — SQLAlchemy
   ORM'un her `flush()`'ta otomatik-artan PK'yı geri okumak için kullandığı
   standart desen, Postgres'te `INSERT` yetkisi yetmiyor, dönen kolon için
   ayrıca `SELECT` de gerekiyor. `_write_exception_stmts` artık `INSERT`
   verilen her durumda otomatik olarak `SELECT` de veriyor — bu, henüz
   bağlanmamış diğer 5 `WriteException`'ı da aynı RETURNING tuzağından
   kurtarıyor. Ayrıca (5.) her korumalı endpoint'in `get_current_user`'ı
   `auth_rbac.kullanicilar`'ı okuduğu (süper-admin'in break-glass fallback'i
   bunu maskeliyordu, normal kullanıcı testlerinde ortaya çıktı) ve (6.)
   `Idempotency-Key` desteğinin `platform.idempotency_keys`'e SELECT+INSERT+
   UPDATE gerektirdiği (trip VE fuel kullanıyor) bulunup TÜM modül
   rollerine evrensel olarak eklendi — ikisi de "tek modüle özel değil,
   her modül aynı duvara çarpacaktı" sınıfından.

**Migrationlar**: `0062_faz2_trip_role_grants_fix` (madde 1) +
`0063_faz2_returning_fix` (madde 4-6). Bu pilot, "önce 1 modülle dene"
kararının doğruluğunu kanıtladı — 15 modülü aynı anda bağlamak bu 6
bulguyu çok daha zor teşhis edilir hale getirirdi.

### Fleet pilot bulgusu (2026-07-28) — fleet'in api_router.py wiring'i TAMAMLANDI

`fleet`'in 4 router'ına `dependencies=[Depends(require_module_role("fleet"))]`
eklenip gerçek bir backend + Postgres 16 + gerçek HTTP isteğiyle
(`POST /vehicles/`, `DELETE /vehicles/{id}`) uçtan uca test edildi.
**1 gerçek, önceden var olan Wave 1 grant-matrisi açığı** bulunup
düzeltildi:

1. **Kök neden**: `platform_infra.audit.audit_logger`'ın `@audit_log`/
   `log_audit_event`'i EVERY modülün write endpoint'inde `admin_platform.
   admin_audit_log`'a unqualified bir `INSERT` yapıyor (yalnız
   admin_platform'un kendi endpoint'lerinde değil). `m_fleet`'in bu şemaya
   USAGE grant'ı yoktu — Postgres bunu "relation does not exist" olarak
   raporluyor (USAGE'sız bir rol şemanın var olduğunu bile göremez,
   "permission denied" değil). Bu tek başına audit_logger'ın kendi
   try/except'i tarafından yutulup loglanıyordu, AMA audit-persist
   kodunun `session.begin_nested()` SAVEPOINT koruması yalnızca
   `session.in_transaction()` zaten true olduğunda devreye giriyor —
   fleet'in soft-delete akışı (`delete_vehicle.py`) kendi `uow.commit()`'ini
   audit decorator'ın post-processing'inden ÖNCE inline çağırdığı için, o
   noktada korunacak aktif bir transaction yok; gerçek UndefinedTableError
   session'ı kalıcı zehirliyor, kurtarma yolu olmadan. Fix: `admin_platform.
   admin_audit_log`'a TÜM modül rollerine (m_admin_platform + m_ops hariç)
   evrensel `INSERT` WriteException'ı eklendi — trip pilotundaki
   `outbox_events`/`idempotency_keys` ile aynı "tek modüle özel değil, her
   modül aynı duvara çarpacaktı" sınıfından.

2. **Ayrı, kod-hatası OLMAYAN bulgu — stale Docker image gotcha'sı**:
   fix'i doğrularken `docker compose run --no-deps backend ...` ve manuel
   pilot container'lar tekrar tekrar "permission denied for schema fleet/
   auth_rbac" verdi, migration'ın 0046'da donduğu ve `role_grants.py`'nin
   Wave 2 fix'lerinin (0062-0064 dahil) hiç uygulanmadığı görüldü — kök
   neden kod DEĞİL, kök CLAUDE.md'nin zaten belgelediği gotcha
   ("Backend source code is baked into the image — there is no volume
   mount"): `docker compose run`/`docker run` ile başlatılan container'lar
   image'a build-zamanında donmuş ESKİ kaynak kodu kullanıyordu (11 gün
   önceki image), benim lokal düzenlemelerim (yeni migration'lar +
   `role_grants.py`/`api_router.py` edit'leri) hiç görünmüyordu. Fix:
   `docker compose build backend` ile gerçek rebuild, ardından sıfırdan
   bir Postgres 16 + `alembic upgrade head` (0064'e ulaştığı doğrulandı) +
   yeni bir pilot backend container'ı ile tekrar test edildi — bu sefer
   `has_schema_privilege('m_fleet','fleet','USAGE')=true` ve gerçek
   `POST /vehicles/`→201 + `DELETE /vehicles/{id}`→200 + `admin_audit_log`'a
   her iki aksiyonun da yazıldığı doğrulandı.

**Migration**: `0064_faz2_audit_log_universal`. Ders: birden fazla
`docker compose run`/manuel `docker run` ile hızlı ardışık pilot testi
yaparken, her testten önce **image'ın gerçekten güncel olduğunu**
(`docker images <ad> --format "{{.CreatedSince}}"`) doğrulamadan "kod
hatası" sonucuna varmak yanlış teşhise yol açar — çok sayıda kod
düzenlemesi olan bir dilimde `docker cp` tek-dosya patch'i yerine tam
rebuild tercih edilmeli.

**Not (driver pilotunda düzeltildi)**: yukarıdaki tavsiye ("tam rebuild
tercih edilmeli") çok genişti. Yeni bağımlılık eklenmeyen, saf Python
değişikliklerinde (yeni migration dosyası dahil) `docker cp <dosya>
<container>:/app/<yol> && docker restart <container>` çok daha hızlı ve
güvenilir — entrypoint her restart'ta `alembic upgrade head`'i zaten
otomatik çalıştırıyor, yeni migration dosyası container'a kopyalanmışsa
gerçekten uygulanıyor (driver pilotunda 0065 bu yolla doğrulandı). Tam
`docker compose build` YALNIZCA `requirements.txt` değiştiğinde veya
`docker cp` ile en son değişikliklerin gerçekten göründüğünden şüphe
duyulduğunda gerekli — driver pilotunda bir rebuild denemesi `chown -R
appuser:appgroup /app` adımında >1 saat asılı kalıp (WSL2 vhdx disk
baskısı, bkz. `docker_disk_full_gotcha` hafıza kaydı) sonunda kendiliğinden
bitti; bu riskten kaçınmak için kalan modül pilotlarında varsayılan yöntem
`docker cp` olacak.

### Driver pilot bulgusu (2026-07-29) — driver'ın api_router.py wiring'i TAMAMLANDI

`driver`'ın 2 router'ına (`driver_router`/`coaching_router`)
`dependencies=[Depends(require_module_role("driver"))]` eklenip gerçek bir
backend + Postgres 16 + gerçek HTTP isteğiyle (`POST /drivers/`, `GET
/drivers/{id}/score-breakdown`, `GET /drivers/{id}/route-profile`, `GET
/coaching/{id}/insights`, `DELETE /drivers/{id}`) uçtan uca test edildi.
**1 gerçek Wave 1 grant-matrisi açığı** bulunup düzeltildi:

`GET /coaching/{id}/insights` (driver'ın `DriverCoachingEngine` →
`get_anomaly_detector().get_recent_anomalies(...)` çağrısı üzerinden)
`UndefinedTableError: relation "anomalies" does not exist` ile 500
döndü. Kök neden: `anomaly/infrastructure/anomaly_repository.py::
get_anomalies()` tek bir ham SQL sorgusunda 4 unqualified tablo adını
birlikte JOIN'liyor — `anomalies` (anomaly şeması), `seferler` (trip
şeması, zaten grantlıydı), `soforler` (driver'ın kendi şeması), `araclar`
(fleet şeması, grantlı DEĞİLDİ). `m_driver`'ın `READER_SELECT_GRANTS`'i
yalnızca `["trip"]` idi — `fleet` ve `anomaly` hiç yoktu. Fix:
`READER_SELECT_GRANTS["m_driver"]` → `["trip", "fleet", "anomaly"]`
(migration `0065_faz2_driver_role_grants_fix`).

**Migration**: `0065_faz2_driver_role_grants_fix` — `docker cp` +
`docker restart` ile doğrulandı (yukarıdaki nota bkz.), tam rebuild
GEREKMEDİ.

### Fuel pilot bulgusu (2026-07-29) — fuel'in api_router.py wiring'i TAMAMLANDI, sıfır yeni bug

`fuel`'in 2 router'ına (`fuel_router`/`admin_fuel_accuracy`)
`dependencies=[Depends(require_module_role("fuel"))]` eklenip gerçek bir
backend + Postgres 16 + gerçek HTTP isteğiyle (`POST /fuel/`, `GET
/fuel/stats`, `GET /admin/fuel-accuracy`, `DELETE /fuel/{id}`) uçtan uca
test edildi. **Sıfır yeni grant açığı** — `role_grants.py`'de `m_fuel:
["fleet", "trip"]` zaten fleet/driver pilotlarından önce doğru şekilde
tanımlıydı (fuel'in `uow.arac_repo` aktif-araç kontrolü + `seferler`
raw-SQL sorguları için), migration eklemeye gerek kalmadı. Bu, ilk 3
pilotun (trip/fleet/driver) READER_SELECT_GRANTS matrisindeki gerçek
açıkları önceden temizlediğinin bir kanıtı — kalan modüller için
beklenen model artık "her pilotta mutlaka yeni bug bulunur" değil, "bazı
modüller zaten temiz çıkabilir".

### Location pilot bulgusu (2026-07-29) — location'ın api_router.py wiring'i TAMAMLANDI

`location`'ın tek router'ına `dependencies=[Depends(require_module_role
("location"))]` eklenip gerçek bir backend + Postgres 16 + gerçek HTTP
isteğiyle (`POST /locations/`, `GET /locations/stats`, `GET /locations/
geocode` — gerçek Nominatim çağrısı dahil, `DELETE /locations/{id}`) uçtan
uca test edildi. İlk turda bunlar sıfır yeni grant açığıyla geçti —
**AMA `GET /locations/route-info` endpoint'i test edilmemişti**, ve bu
endpoint main'e push edildikten sonra GitHub CI'ın frontend real-backend
suite'inde (`LocationFormModal.test.tsx`, `location-service.test.ts::
getRouteInfo`) 2 test'i ART ARDA (rerun sonrası da) aynı şekilde
kırdı — flaky değil, gerçek bir regresyondu.

**Kök neden**: `GET /locations/route-info` `route_simulation.public.
get_route_details()` üzerinden `route_simulation.route_paths` tablosunu
(bbox cache lookup) okuyor. Bu nested çağrı kendi session'ını açıyor,
AMA `require_module_role("location")`'ın set ettiği `module_role`
`ContextVar`'ı **task-local** (session-local DEĞİL) — aynı async request
içinde AÇILAN HER `AsyncSessionLocal()` bu context'i miras alıyor, nested
route_simulation session'ı dahil. Yani `m_route_simulation` değil,
`m_location`'ın KENDİSİ route_simulation şemasına SELECT yetkisine
ihtiyaç duyuyor. Fix: `READER_SELECT_GRANTS["m_location"] →
["route_simulation"]` (migration `0066_faz2_location_route_sim_fix`).

**Genel ders (kalan tüm modüller için geçerli)**: bir modülün role-scope
enforcement'ı yalnızca KENDİ raw-SQL sorgularını değil, `public.py`
üzerinden çağırdığı DİĞER modüllerin nested session'larını da etkiler —
ContextVar task-local olduğu için. Pilot testinde artık yalnız "bu modülün
KENDİ tabloları" değil, "bu modülün `public.py` ile çağırdığı TÜM
cross-module fonksiyonlar" da test edilmeli (fleet/driver/fuel
pilotlarında bu sınıf bulunamamıştı çünkü onların cross-module
çağrıları ya hiç yoktu ya da test edilen endpoint'ler o çağrı yollarını
tetiklemiyordu — location'ın `route-info`'su İLK KEZ bu deseni açığa
çıkardı).
