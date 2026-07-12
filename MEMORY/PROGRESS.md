# LOJINEXT — Modüler Monolit Refaktör: İlerleme ve Bulgular

**Tarih:** 2026-07-11/12. **Durum:** FAZ 0 öncesi — plan onaylandı, TASKS/ görev dosyaları oluşturuluyor. Kod tabanına henüz hiçbir değişiklik yapılmadı.

**Kanıt metodolojisi:** 2 dalga × 7 paralel bağımsız tarama ajanı (Explore tipi, salt-okunur) + AST-tabanlı import-graph script'i (2 koşum) + `radon` cyclomatic-complexity ölçümü + canlı Docker DB sorgusu + web araştırması (mimari test araçları) + sıfır-context adversarial plan denetimi (2 tur; ilk turda 5, ikinci turda 4 sayısal hata bulundu ve düzeltildi). Hiçbir mevcut dokümana (CLAUDE.md dahil) güvenilmedi — CLAUDE.md'nin "frontend/src/services/api tek-dosya-per-domain" iddiası SAHTE çıktı (gerçek: 5 dosya); `@publishes` decorator'ının hiçbir yerde tüketilmeyen süs metadata olduğu ölçüldü.

---

## 1. Bulgular Özeti (ölçülmüş sayılar)

- **327** non-test `.py` dosyası, **71.858 LOC** (`app/`; `__pycache__`/archive hariç). Test kütlesi: **541** `test_*.py`/`*_test.py` dosyası (app/ 481 + tests/ 60; `app/tests` altındaki tüm .py = 494).
- **232 route**, 46 endpoint dosyası (en büyükler: trips 22, locations 17, drivers 14, vehicles 13, predictions 11, fuel 11).
- **43 ORM tablosu**, tamamı `app/database/models.py` (1.988 satır, 561 `mapped_column`, 45 `relationship()` — 27'si modül sınırı kesiyor).
- **49 Alembic migration**, tek head (`0046`). `env.py`'de şema desteği YOK (`include_schemas`/`version_table_schema` yok), `naming_convention` VAR. 2 materialized view (`sefer_istatistik_mv`, `error_hourly_stats`), 1 trigger+fonksiyon (`error_events_notify`/`notify_error_event`), aylık `error_occurrences_YYYY_MM` partition'ları. PostGIS Geometry kolonları yalnız yorum satırında — canlı geometry verisi yok.
- Dosya boyu dağılımı: median 138, p90 507, max 1988 satır — **33 dosya >500, 7 dosya >1000 satır**.
- Kompleksite (radon, 2.094 fonksiyon/metot bloğu): median CC=3, p90=9 — **CC>10: 156 blok, CC>30: 8 blok** (max: `ensemble_core.fit` CC=61, `bulk_add_sefer` CC=58).
- Mimari enforcement aracı YOK (import-linter/pytest-archon/xenon hiçbiri requirements'ta değil; root `pyproject.toml` yok — `ruff.toml`+`pytest.ini`). CI'daki tek "mimari" kontrol 2 ad-hoc `git grep` gate'i.

---

## 2. Modül Sınır Haritası — Üç Ayrı Tablo

### 2.1 KOD haritası (dosya/LOC/route + 181 çapraz-modül import kenarı)

| Modül | Dosya | LOC | Route |
|---|---|---|---|
| trip | 10 | 5.336 | 22 |
| fleet | 15 | 3.632 | 31 |
| driver | 14 | 4.477 | 17 |
| fuel | 13 | 2.756 | 12 |
| location | 5 | 1.695 | 17 |
| route_simulation | 21 | 4.787 | 8 |
| anomaly | 12 | 2.210 | 14 |
| prediction_ml | 35 | 10.375 | 16 |
| ai_assistant | 15 | 3.610 | 5 |
| import_excel | 11 | 3.498 | 4 |
| reports | 12 | 2.404 | 15 |
| analytics_executive | 20 | 4.883 | 10 |
| notification | 13 | 1.330 | 11 |
| auth_rbac | 21 | 2.331 | 25 |
| admin_platform | 26 | 3.718 | 25 |
| shared_kernel | 22 | 5.162 | — |
| platform-infra | 62 | 9.654 | — |
| **TOPLAM** | **327** | **71.858** | **232** |

Route toplam sağlaması: 22+31+17+12+17+8+14+16+5+4+15+10+11+25+25 = 232 ✓ (ölçülen `grep -cE "@(router|admin_router)\.(get|post|put|patch|delete|websocket)"` toplamıyla birebir).

**Çapraz-modül import bağlaşıklığı (AST script, nihai eşlemeyle):** 181 import statement, 90 yönlü çift. En yoğun çiftler: admin→auth 7, location→route 7, ml→fleet 7, trip→ml 6, reports→driver 5. Modül profilleri: `auth_rbac out=1/in=17` ve `fleet out=4/in=19` (sağlıklı sağlayıcı — çok tüketilir, az tüketir); `prediction_ml out=27` (en dolaşık tüketici); `trip out=20/in=18` (iki yönlü yoğun). Kompozisyon kökünden modüllere ayrıca **109 yukarı import** (container.py 32 property + deps.py + celery_app.py + `database/repositories/__init__.py` re-export hunisi). İki gerçek katman ihlali tespit edildi: `core/services/notification_service.py` → `api/v1/endpoints/admin_ws.py` (servis katmanından endpoint katmanına import) ve `core/entities/models.py` (shared_kernel) → `core/utils/sefer_status.py` (trip).

**DI bağlaşıklığı** (`app/core/container.py`, 569 satır, 32 lazy-singleton `@property`): cross-module constructor kablolaması ölçüldü — `import_service` 8 cross-module bağımlılık (sefer_service, yakit_service, arac_repo+service, sofor_repo+service, dorse_repo, lokasyon_repo), `report_service` 4, `analiz_service` 3, `degerlendirme_service` 1. CRUD servisleri hem container'da hem `deps.py`'de İKİ KEZ kablolanıyor. `api.py` 46 endpoint modülü import edip 47 `include_router` çağrısı yapıyor (`analytics.py` hem `router` hem `admin_router` veriyor). `main.py` lifespan'ı (satır 284-364) tüm start/stop hook'larını hard-code ediyor — ML warm-up (300-338) dahil.

### 2.2 VERİ haritası (tablo sahipliği + 42 çapraz-şema FK)

| Modül | Tablolar | Tablo sayısı |
|---|---|---|
| trip | seferler, seferler_log, sefer_belgeler | 3 |
| fleet | araclar, dorseler, arac_bakimlari, vehicle_event_log, vehicle_spec_timeline | 5 |
| driver | soforler, sofor_ad_soyad_trigram, sofor_adaptasyon, coaching_deliveries | 4 |
| fuel | yakit_alimlari, yakit_periyotlari, yakit_formul | 3 |
| location | lokasyonlar, lokasyon_segments | 2 |
| route_simulation | route_paths, route_simulations, route_segments, guzergah_kalibrasyonlari | 4 |
| anomaly | anomalies, fuel_investigations | 2 |
| prediction_ml | egitim_kuyrugu, model_versiyonlar, prediction_results | 3 |
| ai_assistant | — (FAISS dosya-tabanlı, DB tablosu yok) | 0 |
| import_excel | iceri_aktarim_gecmisi (FAZ0 kararı, bkz. §4.3) | 1 |
| reports | page_views | 1 |
| analytics_executive | — (read-model; kendi tablosu yok, çok-kaynaklı SELECT) | 0 |
| notification | bildirim_kurallari, bildirim_gecmisi, push_subscriptions | 3 |
| auth_rbac | kullanicilar, roller, kullanici_oturumlari, kullanici_ayarlari | 4 |
| admin_platform | admin_audit_log, entegrasyon_ayarlari | 2 |
| platform (şema) | sistem_konfig, konfig_gecmis, outbox_events, error_events, error_occurrences, idempotency_keys | 6 |
| **TOPLAM** | | **43** |

Sahiplik ilkesi: **yazan modül sahiptir**. `guzergah_kalibrasyonlari` → route_simulation (yazar `route_calibration_service`, FK'sı `lokasyonlar`'a kesiyor ama location değil). `fuel_investigations` → anomaly (anomalinin 1:1 çocuğu; `lock_investigation_for_update` FOR-UPDATE yazma yolu anomaly'de kalmalı — analiz_repo'dan bölünürken bu küme BÜTÜN taşınmalı).

**42 çapraz-modül FK kenarı** (models.py'deki 60 `ForeignKey(` kolonunun 42'si; 18'i modül-içi). Mıknatıslar: `kullanicilar` ~28 inbound (audit/creator/updater kolonları her yerde), `araclar` 7 inbound. `seferler` tek başına 9 outbound FK ile 6 farklı modüle bağlanıyor (guzergah_id→location, route_simulation_id→route, arac_id→fleet, dorse_id→fleet, sofor_id→driver, periyot_id→fuel, created_by/updated_by/onaylayan_id→auth). **Politika: 42 kenar KORUNUR** (FK düşürmek dağıtık-monolit refleksidir); her kenar `arch/fk_registry.yml`'de kayıtlı olacak, yeni kenar eklemek registry PR'ı gerektirecek.

**Raw-SQL sitelerinde görünmez DB bağlaşıklığı** (import grafiğinde YOK): 32 site, en ağırı `analiz_repo.py` — 7 modül tablosuna 56 `text()`/`.execute()` çağrısıyla erişiyor (dosya bazında açık ara birinci; ikinci `sefer_repo` 33). `theft_tasks`, `cross_feature_aggregator`, `fleet_efficiency_index`, `admin_pilot` her biri 5 modül tablosu join'liyor. 34 multi-repo servis (max 5 repo: `ai_service`, `report_service`, `import_service`). ORM: `sefer_repo`'da byte-aynı `joinedload(arac,sofor,dorse,guzergah)` zinciri 3 kopya (satır 83-86, 287-290, 844-847). `base_repository.py:135-139` dinamik joinedload + `:449` jenerik `execute_query` — iki kaçış kapısı.

### 2.3 İLETİŞİM haritası (senkron/asenkron pairwise kararları)

**SENKRON (in-process `public.py`; anlık tutarlılık gerekçesi):**

| Çift | Gerekçe |
|---|---|
| trip→fleet, trip→driver, trip→location | sefer create anında varlık doğrulama + FK; `net_kg` CHECK'i `arac.bos_agirlik_kg`'a bağlı (`sefer_write_service.py:1479-1487` ↔ prefetch `:1305-1311`) |
| trip→fuel | periyot bağlama aynı transaction'da; **EN SIKI çift**, FAZ2 sonunda yeniden değerlendirme işaretli |
| trip→route_simulation, trip→prediction_ml | mevcut 2.5s timeout'lu senkron tahmin hattı; degraded-mode tanımlı (tahminisiz kayıt) |
| import_excel→{trip,fleet,driver,fuel,location} | orkestratör: satır-bazlı doğrulama geri bildirimi senkron; yalnız `public.py` üzerinden (bugünkü 8 cross-module DI kablosu bu tek yüzeye iner) |
| *→auth_rbac | kimlik/permission çözümü senkron; audit-actor id'leri değer olarak taşınır (join gerektirmez) |
| güvenlik sayaçları (rate-limit/brute-force/RBAC-ihlal) | cross-worker ANLIK tutarlılık ŞART (4 worker'da eşik 4× seyreliyor) → pairwise çağrı DEĞİL, merkezi Redis |

**ASENKRON (event/beat; gecikmeli tutarlılık kabul):** ai_assistant←CRUD event'leri (rag_sync zaten böyle) · prediction_ml retrain←YAKIT_ADDED/SEFER_ADDED · notification←SEFER_UPDATED/SLA_DELAY · anomaly←günlük beat taraması · fuel-coverage←beat. Güvenilir teslim = mevcut outbox pattern (60s relay).

**ÇOK-KAYNAKLI OKUYUCULAR (pairwise karara zorlanmadı — özel durum):** anomaly, analytics_executive, reports, ai_assistant(context_builder). **Karar: event-beslemeli projeksiyon ŞİMDİ DEĞİL.** Gerekçe: tek DB instance, 43 tablo — ölçek problemi yok; bu okuyucuların hepsi batch/istek-anı raporu (anomaly beat=günlük, real-time değil); projeksiyon altyapısı bu ölçekte "dağıtık monolit" tuzağının ta kendisi olurdu. Yerine FAZ2'de **read-model PG rolü**: bu 4 modülün rolü diğer şemalara yalnız explicit SELECT grant alır — yazma fiziken imkânsız, sınır DB'de zorlanır. Yazılı yeniden-değerlendirme tetikleyicisi: anomaly'de real-time gereksinim doğarsa event-projeksiyon görevi açılır. `analiz_repo`'nun çok-CTE'li çapraz sorguları (`get_bulk_cost_stats` 72L, `get_month_over_month_trends` 102L) BİLEREK analytics_executive read-model'inde kalır — servis-çağrısına çevirmek N+1 üretirdi.

---

## 3. Bağlaşıklık — Celery + Event Katmanı (import grafiğinde tamamen görünmez)

17 beat entry; 20 task tanımı (19 `@celery_app.task` + 1 `@shared_task`). Sadece **2 explicit dispatch sitesi**: `internal.py:188` `.delay()` + `predictions.py:68` `celery_app.send_task()` (string-isimli — grafikte hiç görünmez) + 4 `job_manager.submit` sitesi. Event bus: 29 `EventType`, 14 publisher-işaretli metod, 26 subscriber (`cache_invalidation.py` 15, `rag_sync_service.py` 6). **Bulgu:** `@publishes` decorator'ı yalnız `setattr(fn, "_publishes", event_type)` yapar — kod tabanında hiçbir yerde okunmaz, saf süs metadata. Gerçek publish `Event(type, data=dict(...))` şeklinde dict payload taşıyor (typed `contracts.BaseEvent` yolu var ama az kullanılıyor). Publish-sitesi başına ORM nesnesi kaçıp kaçmadığı **henüz ölçülmedi** — FAZ1 modül görevlerinde her modül kendi publish sitelerini doğrulayacak (dürüst: bu plan turunda varsayılmadı).

---

## 4. Açık Sorunlar × Modül Sınırı Kesişimi

### 4.1 Multi-worker güvenlik state'i (Sert Kısıt 7)
`app/infrastructure/monitoring/security_probe.py`: `BruteForceDetector` (satır 39) + `RBACViolationTracker` (satır 97) **in-memory per-process** (`OrderedDict`+`Lock`, modül singleton satır 176-177). `.env.prod:97` → `UVICORN_WORKERS=4` → eşikler fiilen 4× seyreliyor (10×401/60s → aslında ~40×401/60s toplam sistem genelinde tespit edilmeden geçebilir). `rate_limit_middleware.py` Redis-backed AMA Redis düşünce in-memory'e sessizce düşer; `resilience/rate_limiter.py` + slowapi adaptörü tamamen in-memory. `EnsemblePredictorService` 20-slot LRU model cache × ~50-100MB × 4 worker (container dışı kendi modül-singleton'ı; `main.py:300-338` warm-up hook'u her worker'da ayrı yükler). **Modülerleşme bu sorunu KENDİLİĞİNDEN çözmez** — ayrı FAZ2 görevi (`faz2-guvenlik-state-redis.md`) şart; modül sınırı bu sayaçları asla modül-içi state'e geri getirmemeli.

### 4.2 model_versions ↔ model_versiyonlar tutarsızlığı — ✅ ÇÖZÜLDÜ (FAZ0)
`app/core/ml/model_manager.py` raw SQL'i (9 site: satır 85, 102, 159, 174, 199, 214, 226, 237, 253) `model_versions` tablosuna erişiyor; ORM tablosu `model_versiyonlar` (models.py:1147). **Canlı DB doğrulaması (2026-07-12, `docker compose exec db psql \dt`):** public şemada 50 tablo var, `model_versiyonlar` MEVCUT, `model_versions` YOK. Sonuç: `model_manager.py`'deki 9 raw-SQL sitesi **gerçekten kırık/ölü kod** — çalıştırılsalar `relation "model_versions" does not exist` hatası verirler. Bu, modüler-monolit planının kapsamı dışında bir bug — prediction_ml modül görev dosyasına (`TASKS/modules/prediction-ml.md` §3) işlendi; taşıma sırasında bu 9 site ya `model_versiyonlar`'a düzeltilir ya da (kullanılmıyorlarsa) temizlenir. Ayrı bug-fix issue olarak takip edilmeli, bu FAZ'da KOD DEĞİŞTİRİLMEDİ.

### 4.3 iceri_aktarim_gecmisi sahiplik kararı — ✅ ÇÖZÜLDÜ (FAZ0)
**Karar: (B) sahiplik import_excel'e taşınır → 14 şema.** Kanıt (`grep -rn iceri_aktarim_gecmisi app --include="*.py"`, tests/__pycache__ hariç): tablonun repository'si (`app/database/repositories/import_repo.py::ImportHistoryRepository`) VE tek okuyucu endpoint'i (`app/api/v1/endpoints/admin_imports.py`) **zaten import_excel modülünün dosya envanterinde**. admin_platform'da (admin_config/admin_audit_service/audit_repo vb.) HİÇBİR kullanım sitesi yok — "audit niteliği" gerekçesiyle admin_platform'a atanmış olması yalnız isimlendirme sezgisiydi, gerçek kod kullanımıyla desteklenmiyordu. Şema sayısı planın her yerinde **14** olarak güncellendi.

---

## 5. Dış Yazarlar (FAZ2 rol izolasyonunu kısıtlar)

`telegram_bot/` ve `ocr_service/`: **yalnız HTTP** (httpx; sıfır DB/app importu) → FAZ2'den etkilenmez. `scripts/` klasöründe 36 dosyanın **16'sı doğrudan DB'ye bağlanıyor** (app `DATABASE_URL`/`AsyncSessionLocal`/UoW ile). En kritikleri: `reset_business_data.py` (21 tabloya TEK session'da DELETE + `SET session_replication_role=replica` → superuser gerektirir), `seed_demo_data.py`, `init_ml_db.py`+`fix_partitions.py` (DDL), `create_db.py` (asyncpg direkt bağlantı, app'i bypass eder), p51/train/calibrate okuyucuları. `alembic/env.py` tüm tablolara DDL uygulayan tek dış yazar (geniş CREATE grant'ı korunmalı). `postgres-exporter` compose servisi DB'yi doğrudan okuyor (monitoring rolü yeterli, salt-okunur).

Canlı dev DB ölçümü (2026-07-11, Docker `db` container'ı): iş tabloları BOŞ (`seferler`=0, `araclar`=0 — TRUNCATE'li pilot ortamı; en dolu tablo `error_occurrences_2026_07`=3681, `admin_audit_log`=1345). **Prod satır sayıları buradan ölçülemez → FAZ3 giriş gate'i** olarak işaretli, varsayılmadı.

---

## 6. Mimari Test Aracı Seçimi (Sert Kısıt 8, web-kanıtlı 2026-07-11)

| Araç | Sürüm | Tarih | Bakım | Statik-ötesi yetenek |
|---|---|---|---|---|
| import-linter | 2.13 | 2026-07-03 | AKTİF (aylık kadans) | yok — Grimp AST; baseline = `ignore_imports` + `unmatched_ignore_imports_alerting=error` |
| pytest-archon | 0.0.7 | 2025-09-19 | DURGUN (~10 ay sessiz, pre-1.0) | **VAR** — predicate'ler importlib ile gerçek modül objelerinde çalışır |
| PyTestArch | 4.0.1 | 2025-08-08 | YAVAŞ (dep-bump'lar sürüyor) | yok — import-linter'ın alanını pytest cümlesiyle tekrarlar → **ELENDİ** |
| ArchUnitPython | 1.3.0 | 2026-07-05 | AKTİF (en taze release, genç) | statik ama geniş (naming/LCOM/circular-dep/PlantUML) |

**Karar:** import-linter (gate) + **pytest-archon** (davranışsal katman). Gerekçe: komplemanın var olma sebebi tam da statik grafiğin köre kaldığı dinamik-import/runtime davranışı — bu sette yalnız pytest-archon'un importlib-tabanlı predicate'leri buna yaklaşıyor. Bakım riski mitigasyonu: dev-only bağımlılık + sürüm pinli + **adlandırılmış fallback tetikleyicisi**: Python yükseltmesinde kırılırsa veya 2 sprint içinde bloklayan bug çıkarsa ArchUnitPython 1.3.0'a geçilir (~1 gün kural çevirisi tahmini). **Dürüst not:** ORM-nesne sızıntısını hiçbir araç purpose-built yakalamıyor — bu boşluk el yazması pytest testleriyle kapatılıyor (bkz. `TASKS/faz1-davranissal-mimari-testler.md`).

---

## 7. Risk Listesi (dürüst)

1. **models.py bölünmesi en riskli mekanik adım.** 27 çapraz `relationship()` kaldırılınca lazy-load'a dayanan okuma yolları kırılabilir (sefer_repo'nun 3 kopyalı joinedload zinciri ölçüldü). Mitigasyon: modül-başına bölme + her adımda `alembic check` boş-diff kanıtı + 0-mock entegrasyon koşusu.
2. **Dağıtık-monolit tuzak noktaları:** her-şey-event hevesi (bölüm 2.3 pairwise kararları bunu keser) · shared_kernel'in çöp kutusuna dönmesi (onay kuralı + FAZ-sonu boyut raporu) · FK düşürme refleksi (fk_registry.yml ile korunur) · gereksiz adapter/köprü enflasyonu (kod kısalığı kuralı keser — bkz. `faz1-dosya-kalite-ve-kisalik-gate.md`).
3. **Canlı kesintisizlik:** `SET SCHEMA` metadata-only ama kısa ACCESS EXCLUSIVE alır → düşük trafik penceresi + tablo-tablo uygulama; rename'ler expand-migrate-contract; geri alınamayan TEK adım contract/drop → en sona, ölçüm-gate'li. Dev DB boş ölçüldü; prod satır sayısı FAZ3 giriş gate'i.
4. **Test kütlesi:** 541 test dosyası eski import yollarına bağlı → shim'siz büyük patlama YASAK. Geçmiş ders: "de-mock" kampanyası ~70 test dosyasını CI hiç koşmadan stale bırakmıştı (bkz. proje hafızası `fullcode_audit_campaign`) — bu kampanyada aynı hata tekrarlanmayacak, her dalga sonunda gerçek CI koşumu şart.
5. **Frontend kırılganlığı:** merkezi API katmanı yok (`frontend/src/services/api/` = 5 dosya, CLAUDE.md'nin "domain başına dosya" iddiası sahte çıktı) → FAZ3 rename öncesi typed client katmanı şart; 370/760 dosya Türkçe field tüketiyor.
6. **4-worker in-memory güvenlik state'i** — bkz. bölüm 4.1, ayrı görev.
7. **pytest-archon bakım riski** — adlandırılmış fallback (bölüm 6). **scripts/ bağımlılığı** — 16 DB-script'i FAZ2'de `m_ops` bakım rolüne geçer, `reset_business_data.py` superuser istisnası ayrıca dokümante edilir.
8. **Oturum-limit dersi (bu planlama sürecinde bizzat yaşandı):** ikinci tarama dalgasında 3/7 ajan oturum limitine takıldı; eksik analizler ana oturumda grep/AST ile birebir tamamlandı. Uygulama FAZ'larında da uzun koşular gün-içi limitlere bölünmeli, tek seferde bitirilmeye çalışılmamalı.

---

## 8. Karar Kayıtları (özet — gerekçeler ilgili bölümlerde)

| Karar | Özet | Bölüm |
|---|---|---|
| Mimari test aracı | import-linter + pytest-archon (adlandırılmış ArchUnitPython fallback'li) | 6 |
| Çok-kaynaklı okuyucular | Event-projeksiyon ŞİMDİ DEĞİL; read-model PG rolü (SELECT-only) | 2.3 |
| Çapraz-şema FK politikası | 42 kenar KORUNUR + fk_registry.yml zorunluluğu | 2.2 |
| Modül klasör adları | İngilizce, FAZ1'de (P0 rename riski yok — DB/JSON kontratı değil); içerik Türkçe kimlikleri FAZ3'ü bekler | TASKS/faz1-registry-iskelet-ve-shim.md |
| Dil geçişi kapsamı | UI = i18next TR/EN kalır; kod/DB/API/docstring/log = İngilizce | TASKS/faz3-dil-gecisi-kod-db-api-ingilizce.md |
| iceri_aktarim_gecmisi sahipliği | ✅ Karar: import_excel'e taşınır (14 şema) — repository+tek okuyucu zaten import_excel'de | 4.3 |

---

## 9. Görevin 11 KALİTE KONTROL Sorusuna Cevap Tablosu

| # | Soru | Cevap | Kanıt/bölüm |
|---|---|---|---|
| 1 | Her iddia kod tabanından mı geldi? | Evet — 40+ sayı bu oturumda grep/AST/radon ile ölçüldü, sıfır-context adversarial denetimle 2 turda çapraz doğrulandı (ilk turda 5, ikinci turda 4 küçük hata bulunup düzeltildi) | Üst bölüm "Kanıt metodolojisi" |
| 2 | Pairwise sync/async gerekçeli mi? Çok-kaynaklılar özel mi? | Evet — 6 senkron çift + gerekçe, 4 çok-kaynaklı okuyucu ayrı ele alındı (event-projeksiyon reddi + read-model rolü kararı) | 2.3 |
| 3 | Baseline→gate sıralaması var mı? | Evet — FAZ0 rapor modu (non-blocking) → FAZ1 baseline dondurma → gate; hiçbir metrik gün-1 hard-fail değil | TASKS/faz0-*, faz1-import-linter-* |
| 4 | Vertical Slice aşırıya kaçmış mı? shared_kernel sıkı mı? | Hayır aşırı değil — eşik: ≥2 use-case paylaşımı; shared_kernel yalnız KÜÇÜLEBİLİR, cross-module girişi CODEOWNERS+kontrat şartlı | Karar Kayıtları + faz1-registry-* |
| 5 | DURMA NOKTASI net mi? | Evet — bu doküman + her TASK dosyası "onay olmadan uygulanmaz" ile başlıyor | TASKS/README.md |
| 6 | Test stratejisi 3 katmanı + import-ötesi bağlaşıklığı kapsıyor mu? | Evet — slice/entegrasyon/davranışsal 3 katman; bağlaşıklık ölçümü import+DI+DB(raw-SQL/FK)+Celery/event 4 katmanlı | Bölüm 2.1-3 |
| 7 | Davranışsal test aracı seçimi gerekçeli mi? | Evet — 4 araç sürüm/bakım/yetenek karşılaştırması, PyTestArch elendi (komplemanlık yok), adlandırılmış fallback | Bölüm 6 |
| 8 | Dosya-başı kalite standardı somut mu? | Evet — ≤400 satır, CC≤10, tek public callable, + kod kısalığı 4 ölçülebilir kural (≥2 tüketici, tek-satır shim, net-LOC≈0, split=ölçülü üye toplamı) | faz1-dosya-kalite-ve-kisalik-gate.md |
| 9 | Her sınır için gerçek stop var mı (yoksa TODO)? | Evet — sınır-başına mekanizma matrisi; zorlanamayan tek şey (ORM lazy-load çapraz-modül gezinme) açık TODO işaretli | faz1-import-linter-*, modül dosyaları |
| 10 | Dil geçişi ayrı FAZ mı + üretim güvenliği + isimlendirme varsayımı var mı? | Evet — FAZ3 bağımsız, ASLA aynı PR'da değil; expand-migrate-contract+batch backfill+prod-ölçüm gate'i; klasör-adı kararı açık (Karar Kayıtları) | faz3-dil-gecisi-kod-db-api-ingilizce.md |
| 11 | FAZ'lar arası giriş/çıkış kriteri tanımlı mı? | Evet — 5 FAZ'ın her biri için ayrı giriş/çıkış satırı, FAZ1 çıkışı "5 ardışık gün yeşil" somut eşiği | TASKS/README.md FAZ tablosu |

---

## DURMA NOKTASI

Bu doküman ve `TASKS/` altındaki görev dosyaları YALNIZCA plandır. Hiçbir kod, migration veya config değişikliği bu turda yapılmamıştır (`git status` ile doğrulanabilir: yalnız `MEMORY/` + `TASKS/` eklendi). Her `TASKS/*.md` dosyası **ayrı onay** almadan uygulanmayacaktır.
