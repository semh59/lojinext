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

### Açık karar noktası (Wave 2 başlamadan önce spike gerekiyor)
`SET LOCAL ROLE`'ün gerçek tetikleyici noktası: SQLAlchemy ORM
`after_begin` event listener'ı (tek nokta, ~15 bare `AsyncSessionLocal()`
dosyası dahil TÜM session yaratma yollarını kapsar, ama async+greenlet
etkileşimi bu projede daha önce sürpriz çıkarmıştı) mı, yoksa
`UnitOfWork`/`get_db()`/`session_scope()`'ta 3 açık çağrı noktası mı
(daha basit/öngörülebilir, ama o ~15 dosyanın ayrıca `session_scope()`'a
taşınmasını gerektirir) — gerçek Postgres'e karşı küçük bir spike ile
karar verilecek.

### Kabul Kriterleri (Wave 2)
- [ ] `module_role.py` (`ContextVar`, `module_role_scope`, `require_module_role`, `open_role_scoped_session`)
- [ ] Enforcement noktası seçildi (spike sonucuna göre) ve bağlandı
- [ ] `api_router.py`'nin ~50 `include_router()` çağrısı modül-bazlı `dependencies=` alıyor
- [ ] `celery_app.py`'nin `task_prerun`/`task_postrun` sinyali görev adından modül rolü çıkarıyor
- [ ] 16 m_ops script'i `open_role_scoped_session("m_ops")` kullanıyor
- [ ] Bilinçli rol ihlali testi (yanlış modülden yazma denemesi) `permission denied` üretiyor (`test_role_isolation_enforcement.py`)
- [ ] Tam regresyon + triyaj turu (yeni `permission denied` hataları teker teker: eksik grant mi, gerçek sınır ihlali mi)
