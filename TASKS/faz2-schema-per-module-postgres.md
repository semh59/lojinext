# FAZ2 — Şema-Başına-Modül (PostgreSQL)

> ✅ **TAMAMLANDI (2026-07-23)** — `import_excel` pilotundan sonra kalan 13
> şema/42 tablo aynı oturumda (kullanıcının "session hijyeni"ni bilinçli
> aşma kararıyla — bkz. STATUS.md) taşındı:
> `alembic/versions/0048_auth_rbac_schema_move.py` … `0060_platform_schema_move.py`.
> Toplam 14 şema (import_excel dahil), 43 tablo. Gerçek Postgres 16'ya karşı
> tam zincir doğrulandı: `alembic upgrade head` → `alembic check` (temiz)
> → `downgrade`/`upgrade` round-trip (temiz). Aşağıdaki "Pilot sonrası
> bulgular" bölümü hâlâ geçerli — özellikle **search_path tasarım kararı**
> ve **index yeniden adlandırma** gerekliliği; ayrıca aşağıdaki "13 şema
> dalgası bulguları" bölümüne bakın (partition/MV/trigger/alembic_version
> özel durumları + gerçek Postgres'te bulunan 2 model-transkripsiyon hatası).

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Amaç:** 43 tabloyu 13 PostgreSQL şemasına dağıtmak (kod sınırından AYRI, Sert Kısıt 5). `SET SCHEMA` metadata-only ama kısa ACCESS EXCLUSIVE gerektirir.

**Giriş kriteri:** FAZ1 çıkışı — import-linter gate 5 ardışık gün yeşil, tüm 15 modül + shared_kernel/platform-infra taşınmış (models.py modül-başına bölünmüş, `TASKS/modules/shared-kernel.md`).
**Çıkış kriteri:** 43 tablo modül şemalarında; `e2e_pilot_smoke.py` + `p51_real_world_validation.py` PASS.

---

## Şema→tablo dağılımı (MEMORY/PROGRESS.md §2.2'den, toplam=43)

```
trip: seferler, seferler_log, sefer_belgeler
fleet: araclar, dorseler, arac_bakimlari, vehicle_event_log, vehicle_spec_timeline
driver: soforler, sofor_ad_soyad_trigram, sofor_adaptasyon, coaching_deliveries
fuel: yakit_alimlari, yakit_periyotlari, yakit_formul
location: lokasyonlar, lokasyon_segments
route_simulation: route_paths, route_simulations, route_segments, guzergah_kalibrasyonlari
anomaly: anomalies, fuel_investigations
prediction_ml: egitim_kuyrugu, model_versiyonlar, prediction_results
import_excel: iceri_aktarim_gecmisi
reports: page_views
notification: bildirim_kurallari, bildirim_gecmisi, push_subscriptions
auth_rbac: kullanicilar, roller, kullanici_oturumlari, kullanici_ayarlari
admin_platform: admin_audit_log, entegrasyon_ayarlari
platform: sistem_konfig, konfig_gecmis, outbox_events, error_events, error_occurrences (+ aylık partition'lar), idempotency_keys
```
(`ai_assistant` ve `analytics_executive` şema İÇERMEZ — sırasıyla FAISS dosya-tabanlı ve saf read-model.)

## Migration deseni (her tablo için)

```python
"""FAZ2: seferler tablosunu trip şemasına taşı.

Geri alınabilir: SET SCHEMA metadata-only, ACCESS EXCLUSIVE kısa süreli.
"""
def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS trip")
    op.execute("ALTER TABLE seferler SET SCHEMA trip")

def downgrade():
    op.execute("ALTER TABLE trip.seferler SET SCHEMA public")
```
Uygulama sırası: **tablo tablo, düşük trafik penceresinde** (görevin üretim-güvenliği kısıtı — Sert Kısıt 9d'nin veri-taşıma versiyonu). Her tablo için ayrı migration dosyası — toplu `SET SCHEMA` YOK (tek migration'da 43 tablo = tek uzun kilit penceresi, kabul edilemez).

## alembic/env.py değişikliği
```python
context.configure(
    ...,
    include_schemas=True,
    version_table_schema="platform",  # alembic_version tablosu platform şemasına taşınır
)
```
`naming_convention` (mevcut, korunur) şema-bağımsız çalışır — değişiklik gerekmez.

## MV/trigger/partition kararları
- `sefer_istatistik_mv` → `analytics_executive` şemasına (analytics_executive'in kendi tablosu yok ama bu MV'yi okuyor — MEMORY §2.2 notu).
- `error_hourly_stats` MV + `error_events_notify` trigger/fonksiyon + `error_occurrences_YYYY_MM` partition'ları → `platform` şemasında kalır.

## Dış yazar rolü (`m_ops`)
16 DB-script'i (MEMORY §5) için `m_ops` bakım rolü: tüm şemalara CREATE+ALL grant (superuser DEĞİL, ama geniş). `reset_business_data.py`'nin `SET session_replication_role=replica` ihtiyacı hâlâ superuser gerektirir — bu script'in çalıştırılması ayrı, elle onaylı bir operasyon olarak dokümante edilir (script değişmez, yalnız kim çalıştırabileceği netleşir). `alembic/env.py` geniş DDL grant'ını korur (migration yazarı zaten trusted).

## Geri alma
Her migration dosyası bağımsız `downgrade()` içerir (`SET SCHEMA public`). Bir tablo taşındıktan sonra sorun çıkarsa, o TEK tabloyu geri almak yeterli — toplu rollback gerekmez (tablo-tablo taşımanın avantajı).

## Kabul Kriterleri
- [x] 14 şemanın hepsi oluşturuldu (`import_excel` pilot + 13 şema bu dalgada)
- [x] 43 tablonun hepsi dağıtıldı, her biri ayrı migration + ayrı downgrade — gerçek Postgres'te upgrade→downgrade→upgrade döngüsü doğrulandı (13 migration tek zincirde, `alembic downgrade 0047_import_excel_schema_move` → tekrar `upgrade head` → `alembic check` temiz)
- [x] `include_schemas=True` aktif; `version_table_schema="platform"` EKLENDİ (`alembic/env.py`, hem offline hem online `context.configure()`) — bkz. aşağıdaki "alembic_version taşıma" notu (chicken-egg sınırı nedeniyle migration-zinciri-dışı bir cutover script gerektiriyor)
- [x] MV/trigger/partition'lar doğru şemada: `error_hourly_stats` MV → `platform` (`ALTER MATERIALIZED VIEW ... SET SCHEMA`), `error_occurrences_YYYY_MM` partition çocukları → `pg_inherits`'ten dinamik bulunup tek tek `platform`'a taşındı (gerçek Postgres'te doğrulandı: parent'ın `SET SCHEMA`'sı çocukları OTOMATİK taşımıyor — ayrı bir ALTER gerekiyor), `error_events_notify` trigger'ı OTOMATİK taşındı (trigger'lar tabloya OID üzerinden bağlı, ayrı ALTER gerekmiyor — bu da gerçek Postgres'te doğrulandı).
- [ ] `e2e_pilot_smoke.py` + `p51_real_world_validation.py` — bu oturumun sandbox'ında gerçek Docker/docker-compose yok, CI'da doğrulanmalı (pilotla aynı sınırlama)
- [ ] `m_ops` rolü — bu dalgada OLUŞTURULMADI (kullanıcı onayı gerektiren, ayrı bir DB-rol tasarım kararı; bkz. aşağıdaki not). `reset_business_data.py`/`seed_demo_data.py` spot-check EDİLDİ: ikisi de bare tablo adı + `AsyncSessionLocal`/paylaşılan `engine` kullanıyor, ALTER ROLE'ün genişlettiği search_path'i otomatik miras alıyor (gerçek Postgres'te taze bir `lojinext_user` bağlantısıyla doğrulandı) — kod değişikliği GEREKMEDİ.

## Pilot sonrası bulgular (2026-07-23) — sıradaki dalgalar için ZORUNLU okuma

**1. `MEMORY/PROGRESS.md`'nin raw-SQL sayısı BAYAT:** "32 site / analiz_repo.py'de
56 çağrı" ölçümü v2/ taşımasından ÖNCEKİ hale ait. İki araştırma ajanıyla
yapılan güncel tarama: `analytics_executive/infrastructure/
executive_read_models.py` = 17 çağrı (56 değil); ama toplamda
**~75 dosyada ~200 raw-SQL/`execute_query()` çağrı sitesi** var (32 değil) —
`BaseRepository.execute_query()` helper'ı (kendisi `text()` sarıyor) her
modüle yayıldığı için naif `text(` grep'i bunu kaçırıyor.

**2. Bu doküman "her siteyi şema-nitele" varsayıyordu — bunun yerine
`search_path` kullanıldı ve gerçek Postgres'te uçtan uca doğrulandı:**
Her taşınan şema, migration içinde `ALTER ROLE CURRENT_USER SET search_path
= public, <şema>, ...`'a eklenir. Bare sorgular (`FROM seferler`) hiç
değiştirilmeden çalışmaya devam eder. **Kritik gotcha (gerçek Postgres'te
bulundu, `alembic/env.py`'de düzeltildi):** rolün search_path'i genişleyince
Postgres'in `schema=None` ("varsayılan şema") tablo numaralandırması da
search_path'teki TÜM şemaları tarar — bu, alembic'in autogenerate/`check`
karşılaştırmasında taşınan tabloyu hem "varsayılan şema" hem "kendi şeması"
geçişinde bulup hayalet bir "kaldırılacak tablo" farkı üretiyordu. Çözüm:
`alembic/env.py`'nin KENDİ migration bağlantısı, migration'lar zaten açıkça
şema-nitelikli olduğu için (`CREATE SCHEMA`/`ALTER TABLE SET SCHEMA`/`ALTER
INDEX <şema>.<isim>`), search_path'i `public`'e sabitliyor — yalnız
alembic'in kendi reflection/check'i için, uygulamanın çalışma-zamanı
rolünün search_path'ini ETKİLEMEDEN. `connection.execute()`'un SQLAlchemy
2.0'da örtük transaction başlattığını ve `commit()` edilmezse `with`
bloğu çıkışında SESSİZCE rollback olduğunu (tüm migration'ı geri alarak,
hatasız görünüp) unutmayın — bu satırı hemen `connection.commit()` ile
kapatın.

**3. İndeks yeniden adlandırma gerekli (gerçek `alembic check` koşumunda
bulundu):** `alembic/env.py`'nin naming_convention'ı (`"ix":
"ix_%(column_0_label)s"`) `__table_args__`'a `schema=` eklenince
`column_0_label`'ı şema-önekli üretmeye başlıyor (`ix_<tablo>_<kolon>` →
`ix_<şema>_<tablo>_<kolon>`) — PK/FK isimleri (`%(table_name)s` tabanlı,
şema-bağımsız) ETKİLENMİYOR, yalnız index'ler. Her migration'ın `upgrade()`'i
DB'deki eski-isimli index'leri `ALTER INDEX <şema>.<eski> RENAME TO <yeni>`
ile yeniden adlandırmalı (metadata-only, yeniden inşa gerektirmez),
`downgrade()` tersini yapmalı — yoksa `alembic check` drift raporlar.

**4. `app/tests/conftest.py` + kök `tests/conftest.py` genelleştirildi
(bir daha dokunulmasına gerek yok):** her ikisi de artık `Base.metadata.
tables`'tan dinamik olarak toplanan şema kümesini kullanıyor (CREATE
SCHEMA + search_path/connect_args) — yeni bir şema taşındığında bu
dosyalara TEKRAR dokunmak gerekmiyor, model'e `schema=` eklemek yeterli.

**Doğrulama notu:** Bu pilot gerçek bir Postgres 16 kurulumuna karşı uçtan
uca doğrulandı (upgrade/downgrade/re-upgrade + `alembic check` + gerçek
`app/tests/` suite'inden 53+ test, import_excel'in execute_import/
rollback_import akışı dahil) — ama gerçek Docker/docker-compose (bu oturumun
sandbox'ında yok) + `e2e_pilot_smoke.py`/`p51_real_world_validation.py`
koşulmadı, CI'da doğrulanmalı.

## 13 şema dalgası bulguları (2026-07-23, aynı gün, pilotun hemen ardından)

Kullanıcı kararıyla (bilinçli "1 oturum = 1 dalga" hijyen istisnası —
"13 şemayı derin planla ve bitir") kalan 13 şema tek oturumda tamamlandı:
`auth_rbac`, `fleet`, `driver`, `fuel`, `location`, `route_simulation`,
`anomaly`, `prediction_ml`, `trip`, `reports`, `notification`,
`admin_platform`, `platform` (migration'lar `0048`…`0060`). Her modülün
`infrastructure/models.py`'sine `__table_args__` schema eklendi + TÜM
`ForeignKey()` string'leri hedef tabloya göre şema-nitelendi (58 site) —
**kritik bulgu (pilotta da not düşülmüştü, burada tekrar doğrulandı):**
hedef tablo `schema=` alınca, KENDİ ŞEMASI İÇİNDEKİ self-reference FK'ler
dahil TÜM referanslar (`trip.seferler.id` gibi) nitelenmeli, yoksa
`NoReferencedTableError`.

**1. Gerçek Postgres'te bulunan 2 model-transkripsiyon hatası (elle
enumerasyonun neden yeterli olmadığının kanıtı):**
   - `reports.PageView.user_id`'nin `index=True` OLDUĞU yanlış varsayılmıştı
     (yalnız `route`/`created_at`'te var) — migration'ın rename listesi bunu
     içeriyordu, `ALTER INDEX ... RENAME` "relation does not exist" ile
     patladı. Düzeltme: rename listesinden çıkarıldı.
   - `fleet.Dorse.is_deleted`'in `index=True` OLDUĞU gözden kaçmıştı —
     `alembic check` "removed/added index" drift'i olarak yakaladı.
     Düzeltme: rename listesine eklendi (`ix_dorseler_is_deleted` →
     `ix_fleet_dorseler_is_deleted`).

   Her iki hata da yalnızca gerçek `alembic upgrade head` + `alembic check`
   koşumuyla (statik grep/model-okuma DEĞİL) yakalandı — bu, bundan
   sonraki her şema-taşıma dalgasının neden mutlaka gerçek bir Postgres'e
   karşı doğrulanması gerektiğinin somut kanıtı.

**2. `platform` şeması iki AYRI kaynaktan tablo devraldı:**
   `admin_platform/infrastructure/models.py`'nin `sistem_konfig`/
   `konfig_gecmis`/`idempotency_keys`'i (admin_platform'un KENDİ 2 tablosu
   — `entegrasyon_ayarlari`/`admin_audit_log` — ayrı, `admin_platform`
   şemasına gitti, migration `0059`) VE `shared_kernel/infrastructure/
   {outbox.py,error_monitoring_models.py}`'nin `outbox_events`/
   `error_events`/`error_occurrences`'ı (migration `0060`) — ikinci
   grubun modeline de `{"schema": "platform"}` eklendi, `error_events`'in
   `user_id`/`resolved_by` FK'leri `auth_rbac.kullanicilar.id`'ye
   nitelendi (eskiden bare `kullanicilar.id`).

**3. RANGE partition + MV + trigger özel durumları (gerçek Postgres'te
ampirik olarak doğrulandı, `0060_platform_schema_move.py`'nin docstring'i):**
   - `ALTER TABLE <partition-parent> SET SCHEMA` parent'ı taşır ama
     partition ÇOCUKLARINI taşımaz (izole bir scratch DB'de test edilip
     doğrulandı) — migration `pg_inherits`'ten çocukları DİNAMİK olarak
     bulup (aylık partition sayısı hardcode edilmedi, `error_digest.py`'nin
     Celery task'ı her ay yeni bir tane ekliyor) tek tek taşıyor.
   - Trigger'lar (`error_events_notify`) tabloya OID üzerinden bağlı —
     tablo taşınınca trigger OTOMATİK yeni şemaya "taşınıyor" (ayrı ALTER
     gerekmiyor, bu da izole test edildi).
   - Materialized view (`error_hourly_stats`) `ALTER MATERIALIZED VIEW ...
     SET SCHEMA` ile taşınıyor (parent tablo gibi, partition'ı yok).

**4. `alembic_version`'ın platform şemasına taşınması — migration
zincirinin İÇİNDE YAPILAMAZ (Alembic'in kendi mimari sınırı):**
   Alembic kendi versiyon-takip tablosunun konumunu `env.py`'deki
   `context.configure(version_table_schema=...)` ile SÜREÇ BAŞINDA
   sabitler. `alembic_version`'ı bir migration'ın KENDİSİ İÇİNDE taşırsak,
   alembic o migration'ın revision'ını yazmaya çalıştığında (hâlâ AYNI
   çalıştırma/transaction içinde) hâlâ ESKİ konumu arar — "relation does
   not exist" ile patlar (gerçek Postgres'te doğrulandı). Çözüm iki parça:
   - **Taze/boş bir veritabanı için**: `alembic/env.py`'nin
     `run_migrations_online()`'ı artık `context.configure()`'dan ÖNCE
     kayıtsız-şartsız `CREATE SCHEMA IF NOT EXISTS platform` çalıştırıyor
     — bu sayede `version_table_schema="platform"` en baştan (migration
     `0001`'den itibaren) sorunsuz çalışıyor (gerçek bir taze DB'de
     `alembic upgrade head` uçtan uca doğrulandı, `alembic_version`
     otomatik olarak `platform` şemasında oluştu).
   - **Zaten kısmen migrate edilmiş (ör. üretim) bir veritabanı için**:
     migration zincirinin DIŞINDA, tek-seferlik bir cutover script'i —
     `scripts/faz2_move_alembic_version_to_platform.py` (idempotent,
     `ALTER TABLE alembic_version SET SCHEMA platform` yapar) — env.py'nin
     `version_table_schema="platform"` satırı canlıya alınmadan HEMEN
     ÖNCE, `0060_platform_schema_move`'un `alembic upgrade head`'i
     tamamlandıktan SONRA çalıştırılmalı. Script'in kendi docstring'i tam
     sıralamayı adım adım anlatıyor.

**5. Loose end — `sefer_istatistik_mv` → `analytics_executive` şeması
(bu dalgada YAPILMADI, bilinçli olarak açık bırakıldı):** bu dosyanın
orijinal planı (§"MV/trigger/partition kararları") `sefer_istatistik_mv`'nin
`analytics_executive` şemasına taşınmasını öngörüyor, ama o modülün HİÇ
ORM tablosu yok (`ai_assistant` ile birlikte "şema İÇERMEZ" olarak
işaretli — kök CLAUDE.md'nin modül tablosunda ikisi de FAISS/read-model
kategorisinde). Bu MV bugün hiçbir prod endpoint tarafından
SELECT edilmiyor gibi görünüyor (yalnız `trip/infrastructure/
repository.py`'de REFRESH ediliyor, grep ile doğrulandı) — sıfırdan yeni
bir "yalnızca bu MV için" şema açmak mı, yoksa `platform`'a mı (diğer
MV'yle aynı yere) taşımak mı doğru karar, bu dosyanın kendisi net değil.
Kullanıcı onayı gerektiren küçük, ayrı bir karar olarak burada dokümante
ediliyor — 43 tablo/14 şema kapsamının (bu dalganın asıl çıkış kriteri)
DIŞINDA.

**Doğrulama (13 şema dalgası, gerçek Postgres 16, bu oturumda koşuldu):**
`alembic upgrade head` (0001→0060, taze DB) → `alembic check` (temiz) →
`alembic downgrade 0047_import_excel_schema_move` (13 migration geri
alındı) → `alembic upgrade head` tekrar → `alembic check` (temiz) —
tam round-trip doğrulandı. `ruff check --select E,F,W,I` temiz. `mypy`
temiz (mevcut 4 hata `trip/infrastructure/repository.py`'de pre-existing,
bu dalganın dokunmadığı bir dosyada).

**Pytest regresyon koşumu — ilk denemede yanıltıcı 1706 failed/183 error,
kök neden ortam eksikliği (bu şema taşımasıyla ilgisiz):** bu doğrulama
venv'inde Redis çalışmıyordu (`faz2-guvenlik-state-redis.md`'nin fail-closed
rate limiter'ı Redis yoksa yazma endpoint'lerini 503'e düşürüyor) — Redis
başlatılınca (`service redis-server start`) sayı 133 passed/50 error'a
düştü, kalan 50'si de zaten bilinen pytest-asyncio teardown/event-loop
gürültüsüydü (gerçek assertion'lar hepsi geçti). **Ayrıca bu triyaj sırasında
GERÇEK bir bug bulunup düzeltildi**: `app/tests/conftest.py`/kök
`tests/conftest.py`'nin şema-reset fixture'ı yalnız `public` şemasını
`DROP...CASCADE`+`CREATE` yapıyordu, diğer 13 modül şemasını yalnız `CREATE
SCHEMA IF NOT EXISTS` ile "varsa dokunma" mantığıyla bırakıyordu —
`Base.metadata.create_all()`'un `checkfirst=True` varsayılanı zaten var olan
bir tabloyu ATLADIĞI için, aynı fiziksel test DB'sinde art arda farklı kod
sürümleriyle koşulan oturumlar arasında STALE (eski yapılı) tablolar
sessizce kalıcı oluyordu (gerçek örnek: `platform.error_occurrences`'ın
önceki bir iterasyondan kalma hâli `error_hourly_stats` MV'sinin
`CREATE`'ini "column layer does not exist" ile patlatıyordu). Düzeltme: her
iki fixture artık TÜM modül şemalarını (yalnız `public`'i değil) her oturum
başında `DROP SCHEMA ... CASCADE` + `CREATE SCHEMA` ile tam sıfırlıyor —
CI'da zaten ephemeral DB kullanıldığı için bu asla tetiklenmiyordu, yalnız
bu oturumun aynı Postgres'e karşı tekrar tekrar koşulan ad-hoc doğrulama
akışında ortaya çıktı. Temiz bir test DB ile (`lojinext_test`'i tamamen
DROP+CREATE ettikten sonra) hedefli alt küme (`test_trips_coverage.py`,
`test_vehicles_coverage.py`, `test_system_coverage.py`) **133 passed, 0 gerçek
failure** verdi.

**Tam suite (~6500+ test) — iteratif triyaj, son durum:** İlk tam koşum
(conftest fix'inden sonra) 1645 failed/189 error verdi — ikinci bir ortam
bulgusu: doğrulama venv'indeki `pytest-asyncio` sürümü (0.23.8) projenin
`pytest.ini`'sinin beklediği `asyncio_default_fixture_loop_scope=session`
config'ini TANIMIYOR ("Unknown config option" uyarısı) — bu, session-scoped
async fixture'ların her testte yeniden açılıp kapanan function-scoped bir
event loop'a çarpmasına, dolayısıyla suite genelinde kademeli "event loop
kapalı" hatalarına yol açıyordu (şema taşımasıyla hiç ilgisi yok).
`pip install -U "pytest-asyncio>=0.24"` (1.4.0'a yükseltti) sonrası aynı
koşum **90 failed**'e düştü. Kalan 90'ın çoğu iki eksik pip paketinden
(`xlsxwriter`, `scikit-learn` — bu ad-hoc venv'de hiç kurulmamıştı) ve
erişilemez dış servislerden (Mapbox/ORS/api-stub bu sandbox'ta yok, RAG/FAISS
init hatası) kaynaklanıyordu; ikisi kurulunca **24 failed**'e düştü.

Bu 24'ün triyajında **2 GERÇEK regresyon** bulunup düzeltildi (commit
`ed05f30`): `app/tests/unit/test_push_broadcast.py` ve
`test_send_push_to_user.py`'nin sahte (`_FakeSession`) mock'ları,
`PushSubscription` artık `notification` şemasında olduğu için üretilen
`"DELETE FROM notification.push_subscriptions ..."` SQL'ini eski
şema-siz literal string'le (`"delete from push_subscriptions"`) arıyordu —
düzeltme substring eşleşmesine çevrildi (`"delete from" in text and
"push_subscriptions" in text`). Ayrıca 4 test dosyasında (`test_lokasyon_
segments_model.py`, `test_route_simulation_models.py`,
`test_phase4_sefer_integration_helpers.py` — commit `c5e9891`)
`Base.metadata.tables["lokasyonlar"]` gibi şema-öncesi bare-key varsayımları
vardı — SQLAlchemy artık bunları `"location.lokasyonlar"` gibi şema-nitelenmiş
anahtarla kaydediyor; testler güncellendi.

Kalan ~22 failure'ın tamamı şema taşımasıyla ilgisiz, bu sandbox'a özgü
ortam kısıtları (Mapbox/ORS/api-stub yok, FAISS/RAG init'i eksik bağımlılık,
FastAPI/Starlette sürüm farkı `_IncludedRouter.path` AttributeError'ı,
rate-limiter/Redis contention 503'ü, `error_events` sayısının test-sırası
pollution'ı) — CI'da (doğru pinned bağımlılıklar + ephemeral DB + gerçek
`api-stub`) bunların hiçbiri beklenmez.

**Kesin son koşum (tüm düzeltmeler commit'lendikten sonra, temiz
`lojinext_test` + hem Postgres hem Redis ayakta, tek kesintisiz koşum):**
`5108 passed, 21 failed, 90 skipped` (489s). 21 failure'ın tamamı yukarıdaki
aynı sandbox-ortamı kategorilerine düşüyor (birebir aynı test isimleri) —
sıfır yeni/beklenmeyen failure. Bu, 13-şema taşımasının gerçek bir
regresyon üretmediğinin nihai kanıtı.

**Takip turu**: kullanıcı kalan 21 failure + 90 skip'in de sıfıra
indirilmesini istedi. Eksik pip paketleri kuruldu (torch/lightgbm/
faiss-cpu/sentence-transformers/shapely/uvicorn), fastapi pin'e
(`0.136.0`) dönüldü, `api_stub` Docker'sız `uvicorn` ile ayağa kaldırıldı.
Triyajda 2 gerçek test-izolasyonu bug'ı bulunup düzeltildi (commit
`488c282` — detaylar `TASKS/STATUS.md`'de): rate-limiter'ın Redis
sayaçlarını flush etmeyen fixture, ve `error_events.py`'nin modül-
seviyesinde import ettiği `AsyncSessionLocal`'ın `db_session`
fixture'ının monkeypatch'i tarafından hiç yakalanmaması (endpoint gerçek
DB'yi okuyordu). Bunlar şema taşımasının kendisiyle ilgili değil, ama
tam-suite pytest koşumlarını etkiliyorlardı. **Kesin, tamamen temiz
(eşzamanlı başka pytest süreci olmadan) son koşum: `5202 passed, 0
failed, 0 error, 17 skipped`.** Kalan 17 skip meşru/dokümante (FAISS/
PyTorch "guard testi kasıtlı skip" — paket kuruluyken o path zaten
test edilmiyor —, kayıtlı Mapbox sample JSON eksikliği, ve gerçek canlı
sunucu gerektiren 1 güvenlik testi) — hiçbiri kod bug'ı değil.
