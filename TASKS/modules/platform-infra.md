# Modül Görevi: platform-infra (dalga 17/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Doğa farkı:** shared_kernel gibi bu da iş modülü değil — gerçekten cross-cutting altyapı (cache/events/monitoring/resilience/middleware/DI/bootstrap).

**Giriş kriteri:** shared-kernel dalgası (16) tamamlandı, main'de yeşil.

---

## 0. ÖN-DENETİM DÜZELTMELERİ (2026-07-21, dalga 16 bittikten sonra yapıldı, kullanıcı onayıyla)

Bu planın orijinal hâli (aşağıdaki madde 1-5, tarihsel olarak korunuyor)
`app/modules/registry.py` + `ModuleSpec` + tek-satır-shim'li bir mimariye
dayanıyordu. Dalga 1-16'nın GERÇEK yürütülüşü bambaşka bir yoldan gitti —
bu bölüm o planı gerçek koda karşı doğrulayıp düzeltiyor (shared-kernel.md'nin
madde 0'ıyla aynı disiplin).

1. **`app/modules/registry.py`/`ModuleSpec`/`app/platform/` HİÇ VAR OLMADI.**
   `faz1-registry-iskelet-ve-shim.md`'nin öngördüğü `ModuleSpec`/registry
   deseni, 15 modülün taşınması sırasında hiç inşa edilmedi — her modül
   doğrudan `v2/modules/<isim>/`'e taşındı (`app/modules/<isim>/` DEĞİL),
   `main.py`/`container.py`/`api.py` her taşımada ELLE güncellendi (o
   modülün import/route'ları eklendi/çıkarıldı). Taşınan hiçbir dosyanın
   eski yerinde shim BIRAKILMADI — kullanıcının tekrarlanan "varsayımla iş
   yapmak yasak"/"shim bırakma" talimatları eski planın "tek-satır shim"
   stratejisini baştan geçersiz kıldı (istisna: `app/api/v1/endpoints/
   {ai,feedback}.py` + `app/schemas/trip_planner.py` — bunlar GERÇEKTEN
   var, ama ai_assistant modülünün KENDİ, "FAZ4'te silinir" diye
   dokümante edilmiş bilinçli shim'leri, bu dalganın kapsamı dışı).
   **Düzeltme**: aşağıdaki madde 1-5'teki registry/ModuleSpec/shim
   çerçevesi TAMAMEN TERK EDİLDİ — bu dalganın gerçek işi doğrudan
   `container.py`/`api.py`/`main.py`'nin kalan kalıntısını (varsa) ilgili
   modüllere taşımak/silmek, registry soyutlaması KURMADAN.

2. **`app/api/v1/api.py`: 55 `include_router`, ama sadece 2 tanesi gerçek
   platform_infra kalıntısı.** Dosya (218 satır) zaten neredeyse tamamen
   `v2.modules.*.api.*` import'larından oluşuyor (`grep -c include_router`
   → 55). `app/api/v1/endpoints/`'te kalan 4 dosyadan yalnız 2'si GERÇEK
   (mekanik olarak taşınmamış) kod: `admin_calibration.py` (53 satır),
   `weather.py` (193 satır) — ikisi de **route_simulation modülünün kendi**
   dokümante edilmiş eksik-taşıması (kök CLAUDE.md'nin route_simulation
   satırı: "weather_service.py/route_validator.py/openroute_service.py/
   route_calibration_service.py/admin_calibration.py endpoint hâlâ eski
   app/ yollarında"). **Bu iki dosya platform_infra'nın kapsamı DEĞİL** —
   route_simulation'ın kendi bitmemiş işi, ayrı bir onay/görev.
   `app/api/v1/endpoints/ai.py`/`feedback.py` zaten `v2.modules.ai_assistant.
   api.*`'ye yönlendiren 1 satırlık, "FAZ4'te silinir" diye işaretli bilinçli
   shim'ler — dokunulmadı.

3. **`app/core/container.py`: 19 property vardı (32 değil), taşıma sırasında
   8'i sıfır-çağıran bulunup silindi.** Her property için gerçek kod tabanı
   (`grep -rn "get_container()\.<prop>"` + `grep -rn "container\.<prop>"`,
   test dosyaları dahil) taranarak GERÇEK çağıran sayısı doğrulandı —
   varsayılmadı:
   - **Sıfır çağıran, silindi** (2026-07-21): `arac_repo`, `sofor_repo`,
     `yakit_repo`, `lokasyon_repo`, `dorse_repo`, `analiz_repo`,
     `health_service`, `external_service`. Gerçek prod kod bu repo'ları hep
     `uow.<repo>` (UnitOfWork) veya modül-seviyeli singleton getter'lar
     (`get_arac_repo()` vb.) veya `ReportRepos` bundle'ı üzerinden okuyordu
     — container'daki AYRI kopyaları hiçbir yerden okunmuyordu (yalnız
     `test_container.py`/`test_container_comprehensive.py`'nin kendi
     testleri + `test_detailed_scenarios.py`'nin artık işlevsiz bir
     session-enjeksiyon bloğu tarafından egzersiz ediliyordu — o test
     bloğu da provasız/no-op olduğu doğrulanıp kaldırıldı).
   - **Kaldı, gerçek çağıranı var**: `event_bus`, `sefer_repo` (yalnız
     `sefer_service`'in kendi DI wire-up'ı için — `sefer_service` gerçekten
     çağrılıyor: `import_excel`'in `process_sefer_import`/
     `import_sefer_excel_upload`'ı `get_container().sefer_service.
     bulk_add_sefer(...)` kullanıyor), `prediction_service`,
     `anomaly_detector`, `time_series_service`, `license_service`,
     `ai_service`, `smart_ai_service`, `export_service`, `weather_service`
     — hepsi `get_container().<prop>` ile gerçekten çağrılıyor
     (`v2/modules/*/application/*.py` içinden, çoğunlukla döngüsel-import
     kırma amaçlı bir lazy-factory deseni).
   - **Not**: `container.py`'nin kendi docstring'i "BURAYA GİRMEZ:
     transaction-scoped domain servisleri, bunlar app/api/deps.py'de
     Depends()+UoW ile oluşturulur" diyor — ama `sefer_service` tam olarak
     bu kategoriye giriyor ve yine de container'da yaşıyor (tarihsel
     tutarsızlık, bu turda dokunulmadı, ayrı bir karar gerektirir: gerçek
     trip route'ları zaten `app/api/deps.py`'nin AYRI, per-request
     `get_sefer_service(uow)` fonksiyonunu kullanıyor — container'ınki
     yalnız import_excel'in container-üzerinden-erişimi için yaşıyor).
   - **Kalan 10 property (2026-07-22'de modül-modül incelendi)**: 9'u sağlam
     (`event_bus`, `sefer_service`, `anomaly_detector`, `time_series_service`,
     `license_service`, `ai_service`, `smart_ai_service`, `export_service`,
     `weather_service` — her birinin modülün kendi `get_X()` fonksiyonu
     zaten `get_container().X`'e delege ediyor, kasıtlı circular-import-kırma
     lazy-factory deseni; `event_bus`/`weather_service` ayrıca kendi
     kaynaklarında da gerçek tekil singleton). **`prediction_service` gerçek
     bir tutarsızlıktı**: `prediction_service.py`'nin kendi
     `get_prediction_service()`'ı (7 gerçek çağıranı) container'a delege
     ETMİYORDU, bağımsız kendi `PredictionService()` instance'ını
     yaratıyordu — dosyanın kendi docstring'i ("CREATED_BY: app/core/
     container.py") bunun yanlış olduğunu doğruluyordu. Sonuç:
     `get_container().prediction_service` (yalnız `admin_platform/
     health_service.py`'nin 1 çağırdığı yer) ile gerçek serving instance'ı
     FARKLI iki `PredictionService()` nesnesiydi (pratikte zararsız — ikisi
     de aynı `get_ensemble_service()` singleton'ına sarılıyordu — ama
     tutarsız/israf). ✅ **DÜZELTİLDİ (2026-07-22, kullanıcı onayıyla)**:
     `get_prediction_service()` artık diğer 6 property ile aynı `get_container().
     prediction_service` delegasyon desenine çevrildi; `_prediction_service`
     modül-seviyesi global silindi. Kendi test dosyası
     (`test_prediction_service_coverage.py::test_get_prediction_service_singleton`)
     güncellendi.

4. ✅ **`app/main.py`'nin ML warm-up hook'u taşındı (2026-07-22, kullanıcı
   onayıyla) — projenin İLK modül-startup hook'u emsali.** Yeni
   `v2/modules/prediction_ml/application/model_warmup.py`
   (`schedule_predictor_warmup() -> asyncio.Task`, `public.py`'den export
   edilir) — asıl warm-up mantığı (`_warmup_all_predictors`, aktif araç
   ID'lerini DB'den çekip `get_ensemble_service().get_predictor(...)`'ı
   thread'de çağırma) mekanik olarak taşındı. `main.py`'nin lifespan'ı
   artık yalnız `schedule_predictor_warmup()`'ı çağırıp döndürülen task'ı
   kendi `_bg_tasks` GC-koruma setine ekliyor — task'ın izlenmesi/shutdown'da
   drain edilmesi main.py'de KALDI (modül yalnız task'ı yaratıp döndürüyor,
   `_bg_tasks`'i kendi içine almadı — main.py'nin kendi bookkeeping'ini
   modüle sızdırmamak için). Diğer hiçbir modül henüz bu deseni
   kullanmıyor; bu, gelecekteki modüllerin izleyebileceği ilk somut örnek.

5. **Gerçek platform_infra envanteri (registry'siz, doğrudan)**: cache/
   events/monitoring/resilience/middleware (`app/infrastructure/*`),
   Sentry/Prometheus/OTEL/exception-handler'lar (`main.py` 206-282,
   375-748), `app/services/external_service.py`, `app/database/
   {connection,db_session,init_db}.py`.

   ✅ **`app/infrastructure/{cache,events,monitoring,resilience,middleware}`,
   `app/database/*`, `app/services/external_service.py` — İNCELENDİ
   (2026-07-21/22, madde 1'deki gibi dosya-başına `grep -rln` ile gerçek
   çağıran sayımı yapıldı, container.py denetimiyle aynı disiplin).**
   Sonuç: büyük çoğunluğu (cache/ 5 dosya, events/event_bus.py+event_types.py,
   monitoring/ 11/13 dosya, resilience/circuit_breaker.py+rate_limiter.py+
   shutdown.py, middleware/ 3 dosya, database/connection.py+db_session.py+
   init_db.py) 3+ bağımsız modül tarafından kullanılıyor — gerçekten
   cross-cutting, platform_infra'da KALACAK. Ama 5 kalem tek-modül kalıntısı
   veya ölü kod olarak bulundu (dlq_tasks.py/outbox_tasks.py'yle AYNI desen
   — isim/kullanım tek modüle kenetli ama "platform-genel" klasörde
   yaşıyor):
   - **`app/infrastructure/monitoring/container_health.py`** → tek çağıran
     `v2/modules/admin_platform/api/admin_integrations_routes.py` (Telegram
     bot Docker durumu, admin Integrations paneli). Taşınacak yer:
     `v2/modules/admin_platform/infrastructure/container_health.py`.
   - **`app/infrastructure/monitoring/ml_probe.py`** → tek çağıran modül
     prediction_ml (`application/ensemble_service.py`,
     `domain/ensemble_core.py`). Taşınacak yer:
     `v2/modules/prediction_ml/infrastructure/ml_probe.py`.
   - **`app/infrastructure/resilience/retry.py`** → tek çağıran modül
     route_simulation (`mapbox_client.py`, `open_meteo_client.py` — kök
     CLAUDE.md'nin Open-Meteo gotcha'sının bahsettiği `with_async_retry`
     deseni). Taşınacak yer:
     `v2/modules/route_simulation/infrastructure/retry.py`.
   - **`app/services/external_service.py`** → 2 çağıran, ikisi de
     route_simulation domain'i (`app/core/services/weather_service.py` +
     `v2/modules/route_simulation/application/get_route_details.py`).
     Tamamen Open-Meteo'ya özgü (`get_weather_forecast`/
     `get_weather_current_batch`/`get_weather_archive`), route_simulation'ın
     kendi `infrastructure/open_meteo_client.py`'siyle olası çakışma/
     birleştirme fırsatı var. Taşınacak yer:
     `v2/modules/route_simulation/infrastructure/` (birleştirme kararı ayrı).
   - **`app/infrastructure/resilience/idempotency.py`** — **ölü kod**,
     sıfır gerçek prod çağıran (yalnız kendi test dosyası). Gerçek/aktif
     idempotency-key altyapısı zaten `v2/modules/admin_platform/
     application/idempotency_service.py`'de yaşıyor (kök CLAUDE.md'de
     dokümante) — bu eski `IdempotencyGuard`/`IdempotencyKeyDependency`
     hiçbir router'a wire edilmemiş, terk edilmiş bir öncül implementasyon.
     Silinmeli, taşınmayacak.
   - **`app/infrastructure/events/contracts.py`** — **ölü kod adayı**:
     tek kullanıcısı `event_bus.py`'nin `publish_typed()` metodu, ama
     `publish_typed`'ın kendisinin sıfır prod çağıranı var (yalnız 2 test
     dosyası). `TripCreatedEvent`/`FuelUpdatedEvent`/
     `ModelRetrainRequestedEvent` tipli event-contract deneyi hiç adopte
     edilmemiş — gerçek kod hep untyped `Event`/`EventType`+`publish()`
     kullanıyor. Silinmeli (veya platform_infra'ya "kullanılmıyor"
     notuyla taşınmalı — karar bekliyor).
   - **`app/database/repositories/`** — klasörün içinde artık yalnız
     `__pycache__` kalıntısı var, hiçbir gerçek `.py` dosyası yok (ilgili
     repo'lar zaten ilgili v2 modüllerine taşınmış). Klasör + pyc
     kalıntısı silinmeli.

   ✅ **Yukarıdaki 7 kalem UYGULANDI (2026-07-22, kullanıcı onayıyla)**:
   `container_health.py`/`ml_probe.py`/`retry.py`/`external_service.py`
   `git mv` ile taşındı (tüketiciler + inline-import test patch hedefleri
   güncellendi, dlq_tasks.py/outbox_tasks.py'deki gibi taşıma-notu
   docstring'i eklendi); `idempotency.py` (+ kendi 2 test dosyası:
   `app/tests/unit/test_coverage_boost.py`'nin `TestIdempotencyGuard`
   sınıfı + kök `tests/unit/test_idempotency.py` bütünüyle) ve
   `events/contracts.py` (+ `event_bus.py`'nin `publish_typed()` metodu,
   sıfır gerçek çağıranı olduğu için — + 2 test dosyasının ilgili
   testleri) silindi; `app/database/repositories/` (yalnız `__pycache__`
   kalıntısı) temizlendi. `ml_probe.py`'nin prediction_ml'e taşınması
   `domain/ensemble_core.py`'nin kendi modülünün `infrastructure/`'ına
   erişmesini gerektirdiği için `module-cross-domain-infra-independence`
   + `module-internal-layers` kontratlarına 1 yeni `ignore_imports` satırı
   eklendi (`ensemble_core.py -> ml_probe.py`, telemetri side-effect'i,
   gerçek domain iş kuralı değil). `external_service.py`'nin taşınması
   `app/core/services/weather_service.py` (route_simulation'ın henüz
   taşınmamış eski dosyası) üzerinden GEÇİŞLİ bir zincir açığa çıkardı
   (`prediction_ml.application`/`trip.application` → `weather_service` →
   `route_simulation.infrastructure.external_service`) —
   `public-surface-only-prediction_ml`/`public-surface-only-trip`
   kontratlarına `app.core.services.weather_service ->
   v2.modules.route_simulation.infrastructure.external_service` ignore
   satırı eklendi (zincirin YENİ ucu, `weather_service`'in kendisi zaten
   container.py üzerinden ignore edilmiş bir bağımlılıktı). Tam doğrulama
   (ruff/mypy/lint-imports/pytest) ile onaylandı.

   ✅ **`app/workers/tasks/{dlq_tasks,outbox_tasks}.py` — İNCELENDİ ve
   DÜZELTİLDİ (2026-07-21)**: ikisi de aslında platform-genel DEĞİLDİ.
   `dlq_tasks.py`'nin task adı (`prediction.drain_dlq`) ve Redis anahtarları
   (`pred:dlq`/`pred:retry`) tamamen prediction_ml'e özgüydü
   (`infrastructure/prediction_tasks.py` zaten `pred:dlq`'ya yazıyor) —
   `v2/modules/prediction_ml/infrastructure/dlq_tasks.py`'ye taşındı.
   `outbox_tasks.py`'nin tek işi shared_kernel'in `OutboxEvent`'ini relay
   etmekti — `v2/modules/shared_kernel/infrastructure/outbox_tasks.py`'ye
   taşındı. `celery_app.py`'nin task-registrasyon import'ları + 2 test
   dosyası (`test_worker_tasks.py`, `test_workers/test_celery_tasks.py`)
   güncellendi; Celery task adları (`beat_schedule`'daki string'ler)
   DEĞİŞMEDİ, yalnız Python import yolu değişti. `app/workers/tasks/`'ta
   kalan `backup_tasks.py` (tüm PostgreSQL DB'yi yedekler, gerçekten
   platform-genel) ve `error_digest.py` (dalga 16'da bilinçli olarak
   `app/infrastructure/monitoring/`'de bırakılan ~2300 satırlık alt
   sistemin bir parçası, o taşınmadan tek başına taşınması tutarsız olurdu)
   dokunulmadan kaldı.

---

## Aşağıdaki madde 1-5 — TARİHSEL, TERK EDİLDİ (yukarıdaki madde 0'a bakın)

## 1. Mevcut envanter (62 dosya, 9.654 LOC — değişmez, bu dalga TAŞIMIYOR, YENİDEN BAĞLIYOR)
Ana kalemler (tam liste MEMORY/PROGRESS.md kaynak taramasından): `main.py`, `config.py`, `api/deps.py`, `api/v1/api.py`, `core/container.py`, `database/{connection,db_session,init_db}.py`, `infrastructure/{audit,background,cache,context,database,events,logging,middleware,monitoring,resilience,security/pii_*}/*`, `services/external_service.py`, `workers/tasks/{dlq_tasks,outbox_tasks}.py`.

✅ **Çözüldü (2026-07-14):** connection-pool leak'in kök nedeni bulundu ve
düzeltildi — `app/api/deps.py::get_db`/`app/database/connection.py`'nin
kendisinde DEĞİL, `AuthService`/`MLService`/`AttributionService`'in zaten
FastAPI dependency'si tarafından açılmış (`get_uow()`) bir `UnitOfWork`
instance'ını ikinci kez `async with self.uow:` ile yeniden açmasıydı —
bu, `_owns` bayrağını bozup dış `__aexit__`'in `session.close()`'u atlamasına
yol açıyordu. Ayrıca `AuthService.authenticate()`'teki senkron
`bcrypt.checkpw()` çağrısı event loop'u bloklayıp eşzamanlı yük altında
pool tükenmesini şiddetlendiriyordu (`asyncio.to_thread`'e taşındı). Gerçek
30-kullanıcılı Locust koşumunda leak uyarısı 52→0, p99 latency 4900ms→500ms
oldu. Detay: `TASKS/bug-connection-pool-leak-under-load.md` (kabul kriterleri
işaretli). Bu dalga (17) başladığında ayrıca ele alınacak bir şey kalmadı.

## 2. Bu dalganın gerçek işi: main.py/container.py/api.py'yi BOŞALTMAK
Faz1-registry-iskelet-ve-shim.md'de tanımlanan taşıma tablosu bu dalgada TAMAMLANIR:
- `api.py:53-153`'teki 47 `include_router` çağrısının HEPSİ artık `app/modules/registry.py` üzerinden geliyor olmalı — `api.py`'de yalnız `APIRouter()` toplama iskeleti kalır.
- `container.py`'nin 32 property'sinin HEPSİ modül `wire()` fonksiyonlarına taşınmış olmalı — `container.py`'de yalnız `event_bus` (satır 136-144, gerçek cross-cutting) ve registry-iterasyon mantığı kalır.
- `main.py` lifespan'ı (284-364) `for m in MODULES: ...` döngüsüne indirgenir; ML warm-up (300-338) `prediction_ml.startup`'a taşınmış olmalı (prediction-ml.md'de işaretlendi, burada doğrulanır).
- Sentry/Prometheus/OTEL/middleware/exception-handler'lar (206-282, 375-748) BURADA KALIR — gerçek platform-infra.

## 3. Doğrulama testi (bu dalganın çıkış kanıtı)
```python
# app/tests/architecture/test_registry_completeness.py
def test_all_15_modules_registered():
    from app.modules.registry import MODULES
    names = {m.name for m in MODULES}
    assert names == {
        "trip", "fleet", "driver", "fuel", "location", "route_simulation",
        "anomaly", "prediction_ml", "ai_assistant", "import_excel", "reports",
        "analytics_executive", "notification", "auth_rbac", "admin_platform",
    }

def test_api_py_has_no_hardcoded_include_router():
    import ast
    tree = ast.parse(open("app/api/v1/api.py", encoding="utf-8").read())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "include_router"]
    assert len(calls) == 0  # hepsi registry üzerinden
```

## 4. Kalan cross-cutting envanterin modül-içi izlenebilirliği
`cache_invalidation.py`'nin 15 subscriber'ı (MEMORY §3) burada kalır AMA hangi modülün event'ini dinlediği `events.py` DTO tipleriyle artık statik olarak izlenebilir (FAZ1 davranışsal testler bunu doğruluyor — `faz1-davranissal-mimari-testler.md` madde 3). `security_probe.py`'deki BruteForceDetector/RBACViolationTracker BURADA kalır, Redis-backed hale gelmesi FAZ2 işi (`faz2-guvenlik-state-redis.md`).

## 5. Kabul kriterleri
- [ ] `test_all_15_modules_registered` yeşil
- [ ] `test_api_py_has_no_hardcoded_include_router` yeşil
- [ ] `container.py` yalnız event_bus + registry-iterasyon içeriyor (32 property → 0)
- [ ] `main.py` lifespan'ı registry döngüsüne indirgendi
- [ ] **FAZ1'in genel çıkış kriteri burada test edilir:** import-linter gate 5 ardışık gün main'de yeşil (TASKS/README.md FAZ tablosu)
