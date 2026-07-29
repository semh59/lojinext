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
- [x] `route_simulation` modülünün 3 router'ı (`route_router`/`weather_router`/`admin_calibration_router`) `dependencies=[Depends(require_module_role("route_simulation"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "route_simulation pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı (`POST /routes/simulate`, `GET /weather/dashboard-summary` → 200, `GET /locations/route-info` regresyon tekrar-testi de dahil)
- [x] `anomaly` modülünün 3 router'ı (`anomalies_router`/`investigations_router`/`admin_attribution_router`) `dependencies=[Depends(require_module_role("anomaly"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "anomaly pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı; **6 gerçek grant açığı bulundu** (tek migration `0070`)
- [x] `prediction_ml` modülünün 4 router'ı (`predictions_router`/`admin_ml_router`/`admin_pilot_router`/`admin_predictions_router`) `dependencies=[Depends(require_module_role("prediction_ml"))]` alıyor — **PİLOT TAMAMLANDI VE MAIN'E ALINDI** (bkz. aşağıdaki "prediction_ml pilot bulgusu"), gerçek backend + Postgres 16 + gerçek HTTP isteğiyle uçtan uca doğrulandı; **6 grant açığı + 1 pre-existing (Wave2'den bağımsız) session bug'ı** bulunup düzeltildi (tek migration `0071`)
- [ ] Diğer 6 modülün routerları — kalan 6 modül aynı desenle (`dependencies=[Depends(require_module_role("<modül>"))]`) tek tek bağlanacak, her biri kendi pilot doğrulamasından geçmeli
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

**Devam — 0066 tek başına yetmedi, 2 ek katman daha bulundu (0067, 0068)**:
0066 push edildikten sonra GitHub CI'da AYNI 2 test yine ard arda fail
etti — ama artık farklı bir hatayla ("permission denied for TABLE
route_paths" — bir SELECT değil, bir **INSERT**). Kök neden: cache-miss
senaryosunda `get_route_details()` yeni hesaplanan rotayı `route_paths`
tablosuna geri yazıyor (`BaseRepository.create`), bu da m_location'ın
rolüyle çalışıyor. Fix: `WriteException("m_location", "route_simulation",
"route_paths", ("INSERT",))` (migration `0067`). Bu ikinci bulgudan sonra
location'ın TÜM `public.py` cross-module çağrılarını kapsamlı taradım
(`grep "from v2.modules.*.public import"`) — 3. bir açık daha bulundu:
`openroute_geocode_client.py::_resolve_api_key()` `admin_platform.
entegrasyon_ayarlari`'ı okuyor (DB-configured ORS anahtarı), ama bu
sessizce yutulup `.env` fallback'ine düşüyordu (WARNING, crash değil) —
CI'ın gerçek hata olarak yakalamadığı ama production'da DB-configured
anahtarın sessizce görmezden gelinmesi anlamına gelen gerçek bir
fonksiyonel regresyon. Fix: `READER_SELECT_GRANTS["m_location"]` →
`["route_simulation", "admin_platform"]` (migration `0068`).

**Sonuç — location pilotu toplam 3 migration'da (0066/0067/0068) 3 gerçek
grant açığı buldu**, hepsi aynı kök mekanizmadan (`public.py` cross-module
çağrısı + task-local ContextVar). route_simulation pilotuna geçmeden önce
BU SEFER route_simulation'ın kendi `public.py` cross-module çağrılarını da
(varsa) baştan kapsamlı tarayarak başlanacak — aynı ard-arda-bulma
döngüsünü tekrarlamamak için.

### Route_simulation pilot bulgusu (2026-07-29) — TEK TURDA tamamlandı

Location'ın 3 turluk deneyiminden ders alınarak, wiring eklenmeden ÖNCE
`grep "from v2.modules.*.public import" v2/modules/route_simulation/ -r`
ile TÜM cross-module çağrıları taranıp CLAUDE.md ile çapraz kontrol
edildi. Bu, 3 gerçek grant açığını TEK migration'da (`0069_faz2_route_sim_
grants`) yakaladı — CI'a hiç gitmeden:

1. **`fleet`**: `create_route_simulation.py`'nin `POST /routes/simulate`
   handler'ı `db.get(Arac, arac_id)` ile aracı doğrudan okuyor.
2. **`trip`**: `weather_routes.py`'nin `GET /weather/dashboard-summary`'si
   `SeferService.get_all_paged(...)` (trip'in request-scoped factory'si)
   ile planlanan seferleri listeliyor.
3. **`admin_platform`**: hem `openroute_client.py` hem `mapbox_client.py`
   `admin_platform.public.get_integration_secret`'i çağırıyor (DB-configured
   API anahtarları — location pilotunun 0068'de bulduğu AYNI
   `entegrasyon_ayarlari` tablosu).

`route_router`/`weather_router`/`admin_calibration_router` wiring'i
eklenip gerçek backend + Postgres 16 + gerçek HTTP isteğiyle (`POST
/routes/simulate`, `GET /weather/dashboard-summary`) doğrulandı — hiçbir
"permission denied" hatası çıkmadı (yalnız beklenen dış-servis hataları:
Mapbox/ORS anahtarı eksik, manuel test ortamında normal). `GET
/locations/route-info` regresyon tekrar-testi de bu turda tekrar
çalıştırıldı — location'ın önceki fix'i bozulmadı.

**Sonuç**: "önce kapsamlı tara, sonra wiring ekle" yaklaşımı location'ın
3 CI-turluk keşif döngüsünü route_simulation'da SIFIRA indirdi — kalan 8
modül için de standart prosedür bu olacak.

### Anomaly pilot bulgusu (2026-07-29) — 6 grant açığı, 2 YENİ keşif sınıfı

`anomaly`'nin 3 router'ına (`anomalies_router`/`investigations_router`/
`admin_attribution_router`) wiring eklenmeden ÖNCE `grep "from
v2.modules.*.public import"` ile kapsamlı tarama yapıldı. Bu tarama 1
açık buldu (`admin_platform` — `get_runtime_float`), AMA gerçek HTTP
testinde **2 YENİ keşif sınıfı** ortaya çıktı — statik `public.py`
taraması bunları kaçırıyor:

**Sınıf A — "gömülü repository metodu"**: `GET /anomalies/fleet/insights`
`uow.sefer_repo.get_cost_leakage_stats()`'i çağırıyor (trip'in KENDİ
repository'si), ama bu metodun içindeki ham SQL location'ın
`lokasyonlar`'ını (JOIN) ve fuel'in `yakit_alimlari`'nı (ayrı sorgu)
unqualified olarak okuyor. anomaly'nin kendi kodunda `location`/`fuel`
import'u YOK — yalnız `trip`'in repository implementasyonunu okuyunca
görülebilir. Fix: `READER_SELECT_GRANTS["m_anomaly"]` → `location`+`fuel`
eklendi.

**Sınıf B — "senkron event-bus subscriber zinciri"**: `attribute_loss.
override_attribution()` `SEFER_UPDATED`'i **senkron/in-process**
`get_event_bus().publish_async(...)` ile yayınlıyor (outbox relay
DEĞİL). Bu event'in İKİ abonesi de aynı async task içinde INLINE
çalışıyor ve `m_anomaly`'nin `SET LOCAL ROLE`'ünü miras alıyor:
- `notification` modülünün handler'ı `notification.bildirim_kurallari`'ı
  okuyor → `READER_SELECT_GRANTS["m_anomaly"]`'e `notification` eklendi.
- `prediction_ml`'in `PhysicsRecalculationHandler`'ı `trip.seferler.
  tahmini_tuketim`'i geri yazıyor → mevcut `WriteException`'ın kolon
  listesine `tahmini_tuketim` eklendi.

Ayrıca (Wave 1'den kalan, bu pilotun ürettiği bir regresyon DEĞİL): aynı
`WriteException`'ın kolon listesinde `updated_at` hiç yoktu (Sefer
modelinin Python-side `onupdate=get_utc_now`'ı SQLAlchemy'nin her
UPDATE'e bunu otomatik eklemesine neden oluyor) — gerçek HTTP isteğiyle
"permission denied for table seferler" olarak yakalanıp düzeltildi.

**Genel ders (yeni)**: statik `public.py` grep'i yalnız DOĞRUDAN
cross-module çağrılarını yakalar. İki görünmez sınıf daha var: (1) başka
bir modülün KENDİ repository metodunun içine gömülü çapraz-şema
sorguları (yalnız o metodun kaynak kodunu okuyunca görülür), (2)
senkron/in-process event-bus publish'lerinin TÜM subscriber'larının
sorguları (event'i yayınlayan endpoint'in rolü altında çalışırlar).
Kalan modüller için pilot metodolojisi üçe çıktı: (1) `public.py` grep
taraması, (2) çağrılan diğer modüllerin repository metotlarının kaynak
kodunu okuma, (3) modülün yayınladığı event'lerin TÜM abonelerini
(`events.py`'de "dinler" listesi) bulup her birinin write/read
yollarını kontrol etme — ardından gerçek HTTP testiyle doğrulama.

**Migration**: `0070_faz2_anomaly_admin_key` — 6 açığın tümü tek
migration'da, `docker cp` + doğrudan `apply_role_grants_async` çağrısıyla
(pilot container zaten 0070'i alembic ile uygulamıştı, sonraki
düzeltmeler için alembic yerine doğrudan fonksiyon çağrısı kullanıldı —
son hâli migration dosyasının docstring'ine yansıtıldı).

### Prediction_ml pilot bulgusu (2026-07-29) — 6 grant açığı + 1 pre-existing bug

`prediction_ml`'in 4 router'ına (`predictions`/`admin_ml`/`admin_pilot`/
`admin_predictions`) wiring eklenmeden ÖNCE kapsamlı `public.py` taraması
yapıldı — 3 açık buldu (`trip`, `driver`, `admin_platform`). Gerçek HTTP
testinde 3 açık DAHA çıktı (Sınıf A — gömülü repository metodu, anomaly
pilotundaki aynı desen):

1-3. **trip/driver/admin_platform** (statik tarama): `predictions.py`'nin
   `db.get(Sofor,...)`/ORM `select(Sefer)`'i, `ensemble_service.py`'nin
   `get_sefer_repo`/`get_driver_stats`'i, `prediction_service.py`'nin
   `get_runtime_float("VEHICLE_AGE_DEGRADATION_RATE")`'i.

4. **location** (gerçek HTTP testinde bulundu): `POST /predictions/
   train/{id}` → trip'in KENDİ `sefer_repo.get_for_training()` metodu
   `seferler`'i location'ın `lokasyonlar`'ıyla unqualified LEFT JOIN
   yapıyor (anomaly pilotundaki `get_cost_leakage_stats` ile aynı sınıf).

5-6. **fuel + anomaly** (gerçek HTTP testinde bulundu): `GET /admin/
   pilot-status` `admin_pilot.py` içinde doğrudan ham
   `COUNT(*) FROM yakit_alimlari` + `COUNT(*) FROM anomalies` çalıştırıyor.

**Ayrıca — Wave2'den TAMAMEN bağımsız, gerçek pre-existing bir bug
bulunup düzeltildi**: `ensemble_service.py::train_for_vehicle`
`self.arac_repo`/`self.sefer_repo`'yu (process-ömürlü, session'sız
singleton'lar) `UnitOfWork` açmadan kullanıyordu — HER çağrıda
(rol kısıtlaması olsun olmasın, `lojinext_user` gibi tam yetkili bir
rolle bile) "Database session not initialized" ile çöküyordu. Kardeş
metod `predict_consumption` zaten doğru `uow.arac_repo`/`uow.dorse_repo`
desenini kullanıyordu (root CLAUDE.md'nin "Singleton repos need UoW"
gotcha'sı). Fix: `train_for_vehicle` artık kendi `UnitOfWork`'ünü açıyor.

**Doğrulama**: `predict`/`train`/`comparison`/`ensemble/status`/
`pilot-status`/`versions`/`backfill` — hepsi gerçek HTTP isteğiyle 500/
permission-denied hatasız test edildi (backfill'in arka plan job'ı da
dahil — `BackgroundJobManager`'ın asyncio task'ı `module_role`
ContextVar'ını miras aldığı doğrulandı, ayrı bir wiring gerekmedi).

**Migration**: `0071_faz2_prediction_ml_grants`.

**Ayrı bulgu — CI regresyonu ve düzeltmesi (2026-07-29)**: `train_for_
vehicle`'ın UoW fix'i push edildikten sonra CI'ın "Backend unit tests"
step'i anormal uzun sürdü — kök neden, 9 mevcut unit testinin
`svc._arac_repo`/`svc._sefer_repo`'yu (artık kullanılmayan session'siz
singleton) doğrudan mock'laması, gerçek `UnitOfWork()`'ün DB'ye
bağlanmaya çalışmasıydı. 9 test `UnitOfWork.__aenter__`/`__aexit__`
patch'lenecek şekilde güncellendi (commit `784e30d`), lokal olarak 476
test/4 skip/0 fail doğrulandı.

**Ayrı bulgu — SONRADAN DÜZELTİLDİ (kullanıcı "2 bug niye düzeltilmedi"
diye sorunca, 2026-07-29)**: aynı dosyada `train_general_model` de
`self.sefer_repo.get_all_for_training(...)` çağırıyordu (AYNI
session'sız-singleton sınıfı) AMA bu metot `SeferRepository`'de **hiç
tanımlı değildi** — `get_all_for_training` kod tabanında sıfır tanım,
sıfır başka çağıran. İlk turda "hiçbir HTTP endpoint'ten tetiklenmiyor,
Wave2 kapsamı dışı" gerekçesiyle atlanmıştı — bu gerekçe kullanıcının
"önce hatayı düzelt" kuralına göre YETERSİZDİ, geri bildirim üzerine tam
düzeltildi (commit `eb99d66`): `SeferRepository.get_all_for_training()`
gerçekten eklendi (`get_for_training` ile aynı JOIN deseni, arac_id
filtresi olmadan + `araclar.tank_kapasitesi` JOIN'i — vehicle-class
bucketing için gerekli), `train_general_model` de `train_for_vehicle`
gibi kendi `UnitOfWork`'ünü açacak şekilde düzeltildi, 3 ek unit testi
güncellendi + yeni repository metodu için 1 kontrol testi eklendi.

### Reports pilot bulgusu (2026-07-29) — grant açığı SIFIR, tek turda tamamlandı

`reports`'un 7 router'ına (`reports`/`advanced_reports`/`page_view`/
`page_view_admin`/`today_triage`/`fleet_insights`/`reports_studio`) wiring
eklenmeden ÖNCE kapsamlı 3-adım denetim yapıldı: `public.py` import grep'i,
çağrılan `AnalizRepository`/`analyze_costs.py`/trip-repo metotlarının
kaynak kodu satır satır okundu, `events.py` kontrol edildi (read-only,
event yayınlamıyor).

**Sonuç: `role_grants.py`'de YENİ bir grant/migration gerekmedi.** Mevcut
`m_reports: ["trip", "fleet", "driver", "fuel", "anomaly"]` girdisi
(+otomatik eklenen `auth_rbac`), reports'un dokunduğu TÜM çapraz-şema
erişimini zaten kapsıyordu:

- `aggregate_today_triage`: `anomalies`+`fuel_investigations` (anomaly),
  `seferler`+`araclar` (trip/fleet, `MaintenancePredictor` üzerinden).
- `compute_fleet_comparison`: `seferler` (trip), `anomalies` (anomaly).
- `get_dashboard_counters`: `araclar` (fleet), `soforler` (driver),
  `seferler` (trip), `analiz_repo.get_month_over_month_trends` (trip-only).
- `get_consumption_trend`: `yakit_alimlari` (fuel).
- `analyze_costs.py` (`calculate_period_cost`/`get_monthly_trend`/vb.,
  reports'un kendi `UnitOfWork()`'ü üzerinden — rol task-local olduğu için
  bu yeni UoW da `m_reports` altında çalışıyor): `yakit_alimlari` (fuel),
  `seferler` (trip), `araclar` (fleet).
- `AnalizRepository`'nin `location` şemasına dokunan TEK metodu
  (`get_training_seferler`) reports tarafından hiç çağrılmıyor — bu yüzden
  `m_analytics_executive`'in aksine `m_reports`'a `location` eklenmedi.

**Doğrulama (gerçek HTTP, admin token, tüm 7 router)**:
`GET /reports/dashboard`, `GET /reports/consumption-trend`,
`GET /reports/today/triage`, `GET /reports/insights/fleet/comparison`,
`GET /reports/studio/templates`, `GET /admin/analytics/page-views`,
`GET /advanced-reports/cost/period`, `POST /analytics/page-view` —
hepsi 200/204, sıfır permission-denied.

**Yan not — pre-existing bug DEĞİL, operasyonel gotcha**: reset sırasında
`/reports/dashboard` (503) ve `/admin/analytics/page-views` (500)
`UndefinedTableError: relation "seferler"/"page_views" does not exist`
ile patladı — kök neden PgBouncer'ın, DB şema resetinden ÖNCE açılmış
fiziksel bağlantılarının eski (kısa) `search_path`'i taşıması. PgBouncer
restart edilince (`ALTER ROLE lojinext_user SET search_path=...` yeni
fiziksel bağlantılarda doğru uygulandı) her iki endpoint de 200'e döndü —
kodda bir hata yoktu, tamamen benim manuel DB reset prosedürümün yan
etkisiydi. Migration: yok (grant değişikliği olmadığı için gerekmedi).

**Ayrı bulgu — GERÇEK pre-existing bug, CI'da yakalandı ve TAMAMEN
düzeltildi (2026-07-29)**: reports'un router'ları push edildikten sonra
CI'ın "Integration — Business lifecycle" step'i `permission denied for
table seferler` ile kırmızıya döndü (`test_full_tir_lifecycle`'ın
Step 8'i — trip soft-delete). Kök neden `docker exec` ile gerçek bir
Postgres 16 + gerçek pytest koşumuyla (test dosyaları + dev bağımlılıkları
container'a `docker cp`'lenerek) yeniden üretildi ve `after_begin`
listener'ına geçici bir debug print eklenerek doğrulandı:

`v2/modules/reports/api/dashboard_routes.py`'nin `get_dashboard_stats`
handler'ı TEK BAŞINA tüm codebase'te `SessionDep` (`Depends(get_db)`) +
elle `async with UnitOfWork(session=db) as uow:` (`_owns=False`, borrowed
session) kombinasyonunu kullanıyordu — her DİĞER endpoint `UOWDep`
(`Depends(get_uow)`, `_owns=True`) kullanıyor. `_owns=False` olduğu için
`UnitOfWork.__aexit__` `session.close()`'u ATLIYOR (doğru davranış —
borrowed session'ın sahibi `get_db()`). Ama `get_db()`'nin kendi
`async with AsyncSessionLocal() as session:` bloğunun çıkışı, test
fixture'ının (`app/tests/conftest.py::db_session`) TÜM HTTP istekleri
arasında paylaşılan `NonClosingSession` wrapper'ı sayesinde bilinçli
olarak no-op — bu yüzden dashboard'un (salt-okunur, hiç commit çağırmayan)
transaction'ı KAPANMADAN aynı shared session'da AÇIK kalıyordu. FAZ2 Wave
2'nin `after_begin` listener'ı yalnız YENİ bir transaction başladığında
ateşleniyor (`SET LOCAL ROLE`); dashboard'un transaction'ı açık kaldığı
için hemen ardından gelen `DELETE /trips/{id}` isteği YENİ bir transaction
başlatamadı, dashboard'un `m_reports` rolünü miras aldı — `m_reports`
trip şemasında yalnız SELECT'e sahip, UPDATE reddedildi.

Bu, reports'un router wiring'inden ÖNCE de vardı (dashboard hep bu
pattern'i kullanıyordu) ama HARMLESS'tı: dashboard'un hiç rol bağımlılığı
yokken `after_begin` no-op'tu (`get_module_role() is None`), açık kalan
transaction hiçbir SET LOCAL ROLE taşımıyordu. Reports'un kendi rolü wire
edilince aynı ön-var-olan tasarım kusuru İLK KEZ görünür/kırıcı hale
geldi — sıradaki her Wave2 pilotu da (notification/auth_rbac/admin_platform/
import_excel/analytics_executive/ai_assistant) kendi `SessionDep`
kullanan bir endpoint'i varsa aynı sınıftan bir regresyona yol açabilirdi.

**Düzeltme**: `dashboard_routes.py`'nin `get_dashboard_stats` VE
`get_consumption_trend` handler'ları `SessionDep`+elle-`UnitOfWork`
yerine standart `UOWDep` (`Depends(get_uow)`) pattern'ine çevrildi — artık
codebase'teki HER endpoint aynı DI konvansiyonunu kullanıyor, hiçbir özel
istisna kalmadı. (İlk denemede conftest.py'nin `NonClosingSession.
__aexit__`'ine bir rollback eklemek denendi — bu, farklı bir gerçek
regresyon yarattı: `POST /trips/`'in kendi `add_sefer`→`get_sefer_by_id`
read-after-write akışını bozdu, çünkü aynı shared session'ı KULLANAN ama
FARKLI bir iç semantiğe sahip diğer nested çağrılar da etkileniyordu —
bu yaklaşım terk edildi, üretim-kodu seviyesindeki asıl kök neden
düzeltildi.) `app/tests/unit/test_reports_silent_failure.py`'nin
`get_dashboard_stats(db=...)` çağrısı `get_dashboard_stats(uow=...)`'a
güncellendi. Doğrulama: gerçek Postgres 16 + gerçek pytest
(`test_business_lifecycle.py::test_full_tir_lifecycle` — 1 passed),
tüm `app/tests/integration/` suite'i (415 passed / 5 skipped-env / 5 fail
— 5 fail tamamen ortamsal, bu container'da `MAPBOX_API_BASE_URL`/
`OPENROUTE_API_BASE_URL` api-stub'a yönlendirilmediği için, reports/rol
işiyle ilgisiz), reports-özel unit testleri (39 passed).

### Notification pilot bulgusu (2026-07-29) — grant açığı SIFIR, tek turda tamamlandı

`notification`'ın 3 router'ına (`notification_live_ws_router`/
`notification_router`/`push_router`) wiring eklenmeden ÖNCE 3-adım denetim
yapıldı: `public.py` import grep'i (`notification_routes.py`/
`push_routes.py` yalnız `auth_rbac.public`'i, `quiet_hours.py` fonksiyon-içi
`auth_rbac.public.get_preferences`'i, `handle_trip_events.py` yalnız
`platform_infra.public`'i çağırıyor — hiçbiri auth_rbac dışında çapraz-şema
dokunmuyor), `events.py` kontrol edildi (notification kendi event'ini
YAYINLAMIYOR, yalnız trip'in `SEFER_UPDATED`/`SLA_DELAY`'ini dinliyor —
yayıncı tarafın (trip) kendi rolüne notification şeması gerekip
gerekmediği AYRI bir konu, bu pilotun kapsamı dışı).

**Sonuç: `role_grants.py`'de YENİ bir grant/migration gerekmedi.** Mevcut
`m_notification: ["auth_rbac"]` (otomatik eklenen) girdisi yeterliydi —
`bildirim_kurallari`/`bildirim_gecmisi`/`push_subscriptions` tablolarının
hepsi zaten notification'ın KENDİ şemasında.

**Doğrulama (gerçek HTTP, admin token)**: `GET /admin/notifications/rules`,
`GET /admin/notifications/my`, `GET /push/vapid-public-key` — hepsi 200,
sıfır permission-denied. Ayrıca `test_business_lifecycle.py` +
`test_notification_ownership_integration.py` gerçek Postgres 16'ya karşı
tekrar koşuldu (5 passed) — reports pilotunun role-leak fix'inin
notification'ı da etkilemediği doğrulandı. notification-özel unit/api
testleri (50 passed). Migration: yok.

### Auth_rbac pilot bulgusu (2026-07-29) — grant açığı SIFIR, tek turda tamamlandı

`auth_rbac`'ın 6 router'ına (`auth`/`admin_roles`/`admin_users`/
`preferences`/`users`/`ws_ticket`) wiring eklendi. Bu modül FAZ2'nin
matrisinde ÖZEL bir konumda: `kullanicilar` sistemin en büyük FK
mıknatısı (~28 inbound çapraz-şema kenar — audit-actor kolonları) ama bu
YÖN TERSİ (diğer modüller auth_rbac'ı okuyor, auth_rbac onları değil) —
`role_grants.py`'nin evrensel-ekleme döngüsü zaten `m_auth_rbac`'ı hariç
tutuyor (kendi şemasına zaten `ALL` sahip, `auth_rbac`'a kendi kendini
eklemesine gerek yok).

3-adım denetim: `public.py` import grep'i auth_rbac'ın TEK bir dış çağrısı
olduğunu gösterdi — `auth_routes.py::request_password_reset` →
`notification.public.send_password_reset`; kaynağı okundu
(`infrastructure/email_client.py`), SAF SMTP gönderimi, hiç DB dokunuşu
yok. `events.py` boş (`__all__ = []`, auth_rbac hiçbir event yayınlamıyor/
dinlemiyor — taşımadan önce de böyleydi).

**Sonuç: `role_grants.py`'de YENİ bir grant/migration gerekmedi** — auth_rbac
zaten kendi şemasına `ALL` sahip, tek dış çağrısı DB'siz.

**Doğrulama (gerçek HTTP, admin token, tüm 6 router)**: `GET /admin/roles/`,
`GET /admin/users/`, `GET /users/me`, `GET /preferences/dashboard`,
`POST /ws/ticket` — hepsi 200, sıfır permission-denied (login endpoint'inin
kendisi zaten test akışının başında dolaylı doğrulandı — token alma her
zaman başarılı oldu). `test_business_lifecycle.py` gerçek Postgres 16'ya
karşı tekrar koşuldu (1 passed). auth_rbac-özel unit/api testleri
(27 passed). Migration: yok.

### Admin_platform pilot bulgusu (2026-07-29) — 5 grant açığı + 2 gerçek pre-existing bug

`admin_platform`'un 8 router'ına (`admin_config`/`admin_health`/
`admin_integrations`/`admin_ws`/`error_stream`/`health`/`internal`/
`system`) wiring eklenmeden ÖNCE kapsamlı `public.py` cross-module denetimi
yapıldı — `telegram_bridge.py`'nin (Telegram bot köprüsü,
`api/internal_routes.py`) `driver.public.get_sofor_repo`/
`get_by_telegram_id`, `driver.public.get_by_sofor_id` (driver'ın KENDİ
fonksiyonu ama `trip.seferler`'i doğrudan sorguluyor —
`driver_trip_queries.py`, önceki pilotlardaki gömülü-repository-metodu
sınıfıyla aynı desen), `driver.public.SoforSeferPDFService` (trip+driver
okur), `driver.public.get_driver_coaching_engine` (anomaly okur), ve
`_arac_plaka()`'nın `uow.arac_repo.get_by_id`'si (fleet) bulundu.

**Grant sonucu**: `role_grants.py`'ye `m_admin_platform: ["driver", "trip",
"fleet", "anomaly", "platform"]` (`platform`, `error_events`/
`error_hourly_stats` — sahibi `platform_infra.monitoring`, `0060_platform_
schema_move`'da "platform" şemasına taşınmış — admin_platform yalnız
admin-facing okuma yüzeyini sağlıyor) + 3 WriteException eklendi:
`trip.sefer_belgeler` INSERT (`kaydet_belge`), `fleet.arac_bakimlari`
INSERT (`report_driver_breakdown` → `create_breakdown`), `platform.
error_events` UPDATE yalnız `resolved_at`/`resolved_by` kolonları
(`resolve_error_event`). Migration: `0072_faz2_admin_platform_grants`.

**Gerçek pre-existing bug #1 (aynı sınıf, TAMAMEN düzeltildi)**:
`application/error_events.py`'nin `list_error_events`/`get_error_stats`/
`get_trace_chain`/`resolve_error_event`'i HER BİRİ kendi bare
`AsyncSessionLocal()`'ını açıyordu (`UOWDep`/request session'ı ALMIYOR-
du) — reports pilotundaki `dashboard_routes.py` bug'ıyla BİREBİR AYNI
sınıf: üretimde zararsız (gerçek per-call session kendi `async with`
çıkışında düzgün kapanır) ama test suite'inin paylaşılan-session
fixture'ında (`app/tests/conftest.py::db_session`'ın
`NonClosingSession`'ı) hiç explicit commit/close çağrılmayan salt-okunur
transaction'lar açık kalıp `SET LOCAL ROLE`'ü paylaşılan test session'ının
bir SONRAKİ HTTP çağrısına sızdırabilirdi. Düzeltme: 4 fonksiyon da artık
çağıranın `UOWDep`-kapsamlı session'ını (`session: AsyncSession`
parametresi) alıyor; `system_routes.py`'nin 4 handler'ı kendi `uow.session`'ını
geçiriyor. `conftest.py`'nin artık gereksiz olan
`error_events.AsyncSessionLocal` monkeypatch satırı kaldırıldı (fonksiyonlar
artık o ismi hiç import etmiyor).

**Gerçek pre-existing bug #2 (test-fixture şema sapması, TAMAMEN
düzeltildi)**: `app/tests/conftest.py`'nin `error_hourly_stats`
materialized view'i ham `CREATE MATERIALIZED VIEW error_hourly_stats`
(şema belirtmeden) ile oluşturuyordu — bu, test session'ının search_path'inin
İLK şeması olan `public`'e düşüyordu. Gerçek `0060_platform_schema_move`
migration'ı bu view'i `platform` şemasına taşımıştı — test fixture'ı ile
gerçek migration zinciri arasında bir SAPMA. `m_admin_platform` (hiçbir
rol `public` şemasında USAGE'a sahip değil — FAZ2'nin şema-per-modül
tasarımında `public` artık hiçbir modülün mülkiyetinde değil) bu view'i
sorgulamaya çalışınca `UndefinedTableError` aldı — CI'da değil ama gerçek
Docker+`lojinext_test` DB'sinde koşulan `test_system_stats`/
`test_get_error_stats_returns_empty` testlerinde yakalandı. Bu sapma
`admin_platform`'un rolü wire edilene kadar hiçbir testte görünmüyordu
çünkü o zamana kadar bu view'i sorgulayan HİÇBİR test herhangi bir
kısıtlı role altında çalışmıyordu. Düzeltme: `CREATE`/`DROP MATERIALIZED
VIEW`/`CREATE UNIQUE INDEX` ifadeleri `platform.error_hourly_stats`'a
şema-nitelendirildi (gerçek migration'la eşleşecek şekilde). Not:
`sefer_istatistik_mv` AYNI sapmayı GÖSTERMİYOR — o view gerçek migration
zincirinde de hiçbir zaman `public`'ten taşınmadı (0056_trip_schema_move
dahil hiçbir migration ona dokunmuyor), yani test fixture'ı ile prod
arasında fark yok — ayrı, kapsamı dışı bir bulgu (trip modülünün kendi
FAZ2 borcu, bu pilotun konusu değil).

**Doğrulama (gerçek HTTP, admin token + `X-Internal-Token`, tüm 8
router)**: `GET /admin/config/`, `GET /admin/integrations/`, `GET
/admin/health/`, `GET /system/error-events`, `GET /system/error-stats`,
`GET /system/debug/trace/{id}` — hepsi 200. Internal bridge: `GET
/internal/sofor-by-telegram/{id}`, `GET /internal/sofor-coaching/{id}`
(anomaly okur), `GET /internal/sofor-seferler/{id}` (trip okur), `POST
/internal/sefer-belge` (gerçek dosya upload, `trip.sefer_belgeler` INSERT
— 200), `POST /internal/driver-breakdown` (`fleet.arac_bakimlari` INSERT
— 201) — hepsi permission-denied'sız. `test_business_lifecycle.py` gerçek
Postgres 16'ya karşı tekrar koşuldu (1 passed). admin_platform-özel
unit/api testleri (141 passed / 3 fail → fix sonrası 144 passed — 3.
fail'in biri `test_check_redis_unhealthy`, redis-sentinel'e özgü, bu
pilotla ilgisiz pre-existing bir flake, dokunulmadı).

### Import_excel pilot bulgusu (2026-07-29) — 3 grant açığı, tek turda tamamlandı

`import_excel`'in 3 router'ına (`import`/`trip_export`/`trip_import`)
wiring eklendi. Bu modülün 5 WriteException'ı ZATEN vardı (`execute_import.py`'nin
bilinçli raw-SQL repository-bypass'ı — fleet.araclar, driver.soforler,
driver.sofor_ad_soyad_trigram, trip.seferler INSERT/DELETE,
fuel.yakit_alimlari — driver/CLAUDE.md'de zaten dokümante), ama `public.py`
cross-module denetimi 2 DAHA çağrı yolu buldu:

- `route_importer.py::import_routes()` → `location.public.create_location
  (uow.lokasyon_repo, ...)` — yeni `lokasyonlar` satırı INSERT ediyor VEYA
  "pasif güzergah yeniden eklendi" dalında keyfi alanlarda tam-tablo UPDATE
  yapıyor.
- `yakit_importer.py` → `fuel.public.recalculate_vehicle_periods()`:
  `uow.yakit_repo.save_fuel_periods(..., clear_existing=True)` `fuel.
  yakit_periyotlari`'na DELETE+INSERT (yakit_alimlari'ndan AYRI bir tablo);
  `uow.sefer_repo.update_trips_fuel_data(...)` `trip.seferler`'e yalnız 3
  kolonda (`dagitilan_yakit`/`tuketim`/`periyot_id`) bulk ORM UPDATE —
  mevcut INSERT/DELETE WriteException'ından AYRI (o, execute_import'un
  raw-SQL toplu sefer import'unu kapsıyor, bu UPDATE yolunu değil).

**3 yeni WriteException**: `location.lokasyonlar` INSERT+UPDATE (tam
tablo), `fuel.yakit_periyotlari` INSERT+DELETE, `trip.seferler` UPDATE
(yalnız 3 kolon). Migration: `0073_faz2_import_excel_grants`.

**Doğrulama**: gerçek HTTP — `GET /trips/export` (200), `GET /admin/
imports/history` (200). Yazma yolları doğrudan Python script ile
`module_role_scope("m_import_excel")` altında test edildi (gerçek Postgres
16'ya karşı, `docker exec`): `create_location` başarıyla INSERT etti,
`recalculate_vehicle_periods` istisnasız tamamlandı (hem yakit_periyotlari
hem seferler yazımı). import_excel-özel unit testleri + `test_business_
lifecycle.py` (148 passed). Bu pilotta pre-existing bug bulunmadı.

**Ayrı bulgu — CI regresyonu, TAMAMEN düzeltildi (2026-07-29)**: admin_platform
pilotunun `error_events.py`'yi `AsyncSessionLocal`'ı kendi başına açmaktan
`session` parametresi almaya çeviren fix'i push edildikten sonra CI'ın
"Backend unit tests" step'i `AttributeError: <module '...error_events'>
has no attribute 'AsyncSessionLocal'` ile TÜM API testlerinde patladı
(23+ test). Kök neden: `app/tests/conftest.py`'deki monkeypatch satırını
kaldırırken KÖK dizindeki İKİNCİ bir conftest'in (`tests/conftest.py` —
kök CLAUDE.md'nin "Kök tests/ klasörü" gotcha'sı, dalga 1/3/4/8'de de aynı
şekilde unutulmuş) `db_session_factory` fixture'ında AYNI monkeypatch
satırının bir KOPYASI olduğu gözden kaçmıştı — `grep -rn
"error_events.*AsyncSessionLocal"` ile İKİNCİ dosya bulunup aynı şekilde
düzeltildi (monkeypatch satırı + artık gereksiz `import
v2.modules.admin_platform.application.error_events` kaldırıldı).
Doğrulama: `tests/api/test_api_integration.py` (23 passed, önceden bu
dosyanın TÜM testleri fixture-setup'ta patlıyordu).

**İkinci CI regresyonu — TAMAMEN düzeltildi (2026-07-29→30)**: bir sonraki
push'ta bu sefer "Frontend — Unit tests with coverage" step'i gerçek
backend'e karşı çalışan `KonfigurasyonPage.test.tsx`'te patladı: `PUT
/admin/config/{key}` 500 döndü (`permission denied for table
sistem_konfig`, gerçek backend log traceback'i ile doğrulandı). Kök
neden: `sistem_konfig`/`konfig_gecmis` admin_platform'un KENDİ birincil
özelliği (sistem konfigürasyonu CRUD'u, `konfig_service.py`) ama —
`error_events` gibi — fiziksel olarak "platform" şemasında yaşıyor;
`0059_admin_platform_schema_move` migration'ının kendi docstring'i bunu
doğruluyor (o migration `entegrasyon_ayarlari`/`admin_audit_log`'u
admin_platform şemasına taşırken `sistem_konfig`/`konfig_gecmis`/
`idempotency_keys`'i platform şemasına yönlendiriyor) — bu pilotun ilk
denetimi modülün CLAUDE.md'sindeki tablo-sahipliği özetine harfiyen
güvenip gerçek migration'ı kontrol etmediği için bu ayrıntıyı kaçırmıştı.
`AdminConfigRepository.update_value()` `sistem_konfig` üzerinde `SELECT
... FOR UPDATE` çalıştırıyor — Postgres bir FOR UPDATE satır kilidi almak
için SELECT'in ötesinde UPDATE yetkisi de istiyor; mevcut
`READER_SELECT_GRANTS`'ın "platform" girdisi (0072'de eklenmişti) yalnız
düz SELECT'i kapsıyordu.

**2 yeni WriteException**: `platform.sistem_konfig` UPDATE
(kolonlar=`deger`/`guncelleyen_id`/`son_guncelleme` — sonuncusu modelin
kendi `onupdate=func.now()` kolonu, her UPDATE'te otomatik dahil olur),
`platform.konfig_gecmis` INSERT (aynı çağrı bir denetim-geçmişi satırı da
ekliyor). Migration: `0074_faz2_admin_platform_grants2`.

**Doğrulama**: gerçek Postgres 16 + gerçek HTTP — `docker exec ... alembic
upgrade head` ile migration uygulandı, backend restart edildi, container
içinden gerçek admin login + `PUT /admin/config/ANOMALY_Z_THRESHOLD`
isteği tekrarlandı → 500 yerine 200 (`{"anahtar":"ANOMALY_Z_THRESHOLD",
"deger":2.5,...}`). admin_platform'un config/error-events'e özel test
takımları (`test_admin_config.py`, `test_admin_config_repo_concurrency.py`,
`test_admin_config_repo_coverage.py`, `test_konfig_service.py`,
`test_admin_health_and_roles.py`, `test_error_stream_coverage.py`,
`test_error_stream_more.py`) gerçek Postgres 16'ya karşı 61 passed.
`test_business_lifecycle.py` tekrar 1 passed.

**Üçüncü CI regresyonu — FAZ2 ile ilgisiz, ayrıca düzeltildi (2026-07-30)**:
sistem_konfig fix'i push edilince "Frontend — Unit tests with coverage"
geçti ama pipeline artık bir sonraki adıma ("OpenAPI schema drift check"
hard gate — bu adım daha önce hep önceki adım fail ettiği için `skipped`
kalmıştı, ilk kez fiilen çalıştı) ulaştı ve orada patladı: committed
`frontend/openapi.json`, `GET /reports/consumption-trend`'in
docstring'inin Türkçeden İngilizceye çevrildiği (ilgisiz, önceki bir
commit'in) drift'ini taşıyordu — o commit `openapi.json`'ı yeniden
üretmemişti. Path/schema-seviyeli diff ile doğrulandı: eklenen/kaldırılan
path veya schema yok, TEK fark bu bir açıklama string'i. Gerçek backend'den
(`docker exec ... curl .../openapi.json`) yeniden üretilip commit edildi.

### Analytics_executive pilot bulgusu (2026-07-30) — grant açığı YOK, sıfır regresyon

`analytics_executive` saf read-model bir modül (`AnalizRepository` 7
modülün tablosuna raw-SQL SELECT yapan tek dosya). `m_analytics_executive`
rolü Wave 1'de zaten `["trip", "fleet", "driver", "fuel", "anomaly",
"location"]` şemalarına SELECT + `fuel.yakit_formul` INSERT/DELETE grantı
almıştı (`save_model_params`/`get_model_params`, prediction_ml'in ensemble
servisinden çağrılıyor). Bu pilotun public.py + kaynak-kodu denetimi
(`aggregate_cross_feature.py`'nin prediction_ml.public.
fetch_health_input_batch çağrısı → fleet.arac_bakimlari; `project_cashflow.py`'nin
fleet.public.MaintenancePredictor çağrısı → fleet.arac_bakimlari/
araclar + trip.seferler; `executive_read_models.py`'nin ham SQL'i →
seferler/lokasyonlar/yakit_alimlari/araclar/soforler/anomalies) hiçbir YENİ
şema/tablo bulmadı — hepsi zaten Wave 1'in 6 şemasının içinde. `bulk_create_alerts`
(anomaly.anomalies'e insight-alert yazma yolu, CLAUDE.md'de dokümante) tek
çağıranı olan `generate_insights.py` 2026-07-18'de silindiği için artık
ölü kod — WriteException gerekmiyor.

2 router wiring: `executive_router` (`/reports/executive/*`) +
`trip_analytics_router` (`/trips/stats`, `/trips/analytics/fuel-performance`,
`/trips/{sefer_id}/cost-analysis` — trip_read_router'ın catch-all'ından ÖNCE
konumu korunarak). **Yeni migration YOK** — Wave 1 grantları yeterliydi.

**Doğrulama**: gerçek Postgres 16 + gerçek HTTP, tüm 9 endpoint (kpi,
carbon, compliance, cashflow, cross-feature, bus-factor, pdf, what-if POST,
trips/stats, trips/analytics/fuel-performance) 200; `/trips/{id}/cost-analysis`
202 → `BackgroundJobManager`'ın ayrı asyncio task'ına submit edilen
`reconcile_costs` (trip.seferler + fuel.yakit_alimlari dokunur) SUCCESS ile
tamamlandı — ContextVar-task-local `module_role`'ün spawned background
job task'ına da düzgün miras kaldığını canlı doğruladı (module_role.py'nin
kendi docstring'i bunu zaten belgeliyordu, ama ilk kez gerçek HTTP + gerçek
async job ile test edildi). analytics_executive-özel test takımları (13
dosya, `test_executive_coverage/more.py`, `test_bus_factor.py`,
`test_carbon_footprint.py`, `test_cashflow_projector*.py`,
`test_compliance_scanner.py`, `test_cost_analyzer.py`,
`test_cross_feature_aggregator.py`, `test_executive_pdf.py`,
`test_fleet_efficiency_index.py`, `test_what_if_engine.py`,
`test_analiz_repo_coverage.py`) + `test_business_lifecycle.py` gerçek
Postgres 16'ya karşı 228 passed. Pre-existing bug bulunmadı.

### ai_assistant pilot bulgusu (2026-07-30) — 3 grant açığı, SON kalan modül

`ai_assistant` hiçbir DB tablosuna sahip değil (FAISS dosya-tabanlı 2
bağımsız store), ama chat/plan-wizard yolu çapraz-modül okuma yapıyor.
Önceki grant (Wave 1) `["fleet", "trip", "driver", "location"]` idi;
public.py + kaynak-kodu denetimi 3 eksik şema buldu:

- `fuel`: `AIService._build_context` (`orchestrate_ai_response.py`)
  `uow.analiz_repo.get_dashboard_stats()` çağırıyor — zaten granted
  trip/fleet/driver tablolarının yanında `fuel.yakit_alimlari`
  (SUM(litre)) da okuyor. `ai_routes.py`'nin `_fuel_trend_chart`'ı da
  aynı tabloyu `fuel.public.get_monthly_cost_trend()` üzerinden okuyor
  (`/ai/query` `category=fuel_trend`).
- `anomaly`: aynı `_build_context` çağrısı `uow.analiz_repo.
  get_recent_unread_alerts()` ile `anomaly.anomalies`'i doğrudan okuyor.
- `admin_platform`: `groq_client.py`/`raw_client.py` (2 bağımsız LLM HTTP
  istemcisi) `admin_platform.public.get_integration_secret()`'i çağırıp
  `admin_platform.entegrasyon_ayarlari`'nı okuyor (DB-tabanlı Groq API key
  override) — m_location/m_route_simulation/m_anomaly/m_prediction_ml'de
  zaten aynı desenle grant edilmiş sistem_konfig-okuma paterni.
  `get_integration_secret()` asla raise etmiyor (DB hatasında env
  fallback'e düşer), yani bu grant eksik olsa `/ai/chat` ÇÖKMEZDİ — yalnız
  DB-tabanlı key override'ı sessizce hep inert bırakırdı; tutarlılık için
  yine de eklendi.

3 router wiring: `ai_router` (`/ai/*`), `feedback_router` (`/feedback`),
`plan_wizard_router` (`/trips/plan-wizard` — `trip_read_router`'ın
catch-all'ından ÖNCE konumu korunarak). Migration: `0075_faz2_ai_
assistant_grants`.

**Doğrulama**: gerçek Postgres 16 + gerçek HTTP — `/ai/chat` (fuel+anomaly
grant'i olmadan 500 verecekken artık 200, gerçek yanıt: "Filonuzda 2 araç
vardır"), `/ai/status` 200, `/ai/progress` 200, `/feedback` 202,
`/trips/plan-wizard` 200 (gerçek araç/şoför önerisi), `/ai/query`
`category=fuel_trend` 200 (fuel.yakit_alimlari okuma yolu gerçek HTTP ile
egzersiz edildi, LLM yanıtı gerçek filo verisine atıfta bulunuyor).
ai_assistant-özel test takımları (22 dosya: `test_ai_query.py`,
`test_feedback_endpoint.py`, `test_plan_wizard_endpoint.py`,
`test_maintenance_factor_integration.py`, `test_rag_and_ai_service.py`,
`test_ai_deep_remediation.py`, `test_ai_privacy.py`, `test_ai_security.py`
×3, `test_groq_service_coverage.py`, `test_llm_client.py`,
`test_rag_engine_coverage/more.py`, `test_rag_sync_service_coverage.py`,
`test_ai_service*.py`, `test_smart_ai_service_coverage.py`,
`test_trip_planner_*.py` ×4) + `test_business_lifecycle.py` gerçek
Postgres 16'ya karşı 266 passed / 4 skipped. Pre-existing bug bulunmadı.

## FAZ2 Wave 2 — TÜM MODÜLLER TAMAMLANDI (2026-07-30)

Rota: `notification` → `auth_rbac` → `admin_platform` (2 gerçek bug +
düzeltme) → `import_excel` → `analytics_executive` → `ai_assistant`.
6/6 modül `require_module_role(...)` ile router-seviyesinde bağlandı,
her biri gerçek Postgres 16 + gerçek HTTP ile doğrulandı. Toplam yeni
migration: `0061`(Wave 1 taban) + `0070`-`0075` (6 migration, Wave 2
grant düzeltmeleri). Ayrıca yol boyunca ilgisiz-ama-CI'ı kıran 2 regresyon
bulunup düzeltildi (kök `tests/conftest.py`'deki ikinci stale monkeypatch;
`frontend/openapi.json` drift — iki ayrı kez, ikincisinde kök neden
Python'un `ensure_ascii=True` ile Node'un literal-UTF8 serileştirmesi
arasındaki byte farkıydı).

Kalan/ertelenmiş (ayrı görev, bu dalganın kapsamı dışı):
Celery `task_prerun`/`task_postrun` sinyalinden modül-rolü türetme (şu an
Celery task'ları module_role=None ile, yani rol kısıtlamasız çalışıyor);
16 `m_ops` script'inin `open_role_scoped_session("m_ops")` kullanımına
geçirilmesi.
