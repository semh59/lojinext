# Modül: platform_infra

## Doğa farkı (bu bir iş modülü DEĞİL — ama shared_kernel'den de farklı)

`shared_kernel` gibi bu da bir iş modülü değil — hiçbir domain kavramı
(sefer, araç, sürücü, ...) taşımıyor. Ama **shared_kernel'den kategorik
olarak farklı**:

- **shared_kernel** = domain-PATTERN kodu. Diğer modüllerin kodu bunu
  doğrudan miras alır/kompoze eder (`BaseRepository`, `UnitOfWork`,
  `BaseEntity`). "Mimarinin kendisinin bir parçası" — bu yüzden kendi
  `public-surface-only-shared_kernel` kontratı YOK (amaç zaten herkesin
  serbestçe erişebilmesi).
- **platform_infra** = RUNTIME SERVİS'leri. Diğer modüllerin kodu bunu
  ÇAĞIRIR (Redis client, ASGI middleware, DB engine, logging/audit/metrics
  altyapısı) — hiçbir yerde miras alınmaz/kompoze edilmez. Bu farkın
  sonucu: platform_infra **application katmanı için** kendi
  `public-surface-only-platform_infra` kontratına sahip (aşağıya bkz.) —
  shared_kernel'in aksine.

Kullanıcıyla (2026-07-22) varılan mimari karar: bu kod `app/`'de sonsuza
dek kalamazdı (proje hedefi `app/`'in boşalması), `shared_kernel`'e de
eklenemezdi (kendi "yalnız küçülebilir" ilkesi), bir "iş modülü" gibi de
davranamazdı (domain kavramı yok). Çözüm: `v2/modules/` altında ama
`shared_kernel`'inkine benzer ÖZEL bir iç yapıyla (standart
`api/application/infrastructure/domain` DEĞİL) yaşıyor.

## İçerik envanteri (dalga 17, 10 commit — `TASKS/modules/platform-infra.md`)

```
v2/modules/platform_infra/
├── public.py                     # kasıtlı dış-yüzey — application katmani icin ZORUNLU giris kapisi
├── container.py                  # DI composition root (event_bus + 8 lazy-singleton property)
├── metrics.py                    # Prometheus custom sayaclar (graceful no-op)
├── cache/                        # Redis cache/pub-sub (5 dosya)
│   ├── cache_manager.py          # CacheManager, get_cache_manager
│   ├── redis_cache.py            # RedisCache, get_redis_cache
│   ├── redis_client_factory.py   # get_async_redis_client, get_sync_redis_client, Celery broker URL'leri
│   ├── redis_pubsub.py           # RedisPubSubManager, get_pubsub_manager, get/set_redis_val
│   └── cache_invalidation.py     # setup_cache_invalidation, trigger_dashboard_update
├── events/                       # domain event bus (2 dosya)
│   ├── event_bus.py              # Event, EventBus, EventType, get_event_bus, @publishes
│   └── event_types.py            # EventType enum
├── monitoring/                   # ErrorEvent tabanli gozlemlenebilirlik/alarm alt sistemi (11 dosya)
│   ├── event_bus.py               # ErrorEventBus, get_event_bus (ISIM CAKISMASI — asagiya bkz.)
│   ├── models.py                  # ErrorEvent, ErrorLayer, ErrorSeverity, make_fingerprint
│   ├── activate.py                # activate_all_probes
│   ├── alarm_router.py            # AlarmRouter, get_alarm_router, drain_bg_tasks
│   ├── celery_probe.py            # check_beat_health, setup_celery_probe
│   ├── db_probe.py                # N+1/slow-query tespiti, setup_db_probe
│   ├── external_api_probe.py      # dis API cagrilarinin izlenmesi
│   ├── security_probe.py          # BruteForceDetector, RBACViolationTracker
│   ├── service_probe.py           # monitor_errors decorator, assert_invariant
│   └── silent_fallback_probe.py   # record_silent_fallback (sessiz fallback oranlarini izler)
├── resilience/                    # Circuit breaker + rate limiter + graceful shutdown (3 dosya)
│   ├── circuit_breaker.py         # CircuitBreaker, CircuitBreakerRegistry
│   ├── rate_limiter.py            # AsyncRateLimiter, RateLimiterDependency, RateLimiterRegistry
│   └── shutdown.py                # register_shutdown_handlers, is_stopping
├── middleware/                    # ASGI middleware (4 dosya, main.py'nin zincirinde kayitli)
│   ├── body_size_middleware.py    # MaxBodySizeMiddleware (413 DoS backstop)
│   ├── logging_middleware.py      # RequestLoggingMiddleware
│   ├── rate_limit_middleware.py   # RateLimitMiddleware, get_real_client_ip (Redis-backed, custom)
│   └── slowapi_limiter.py         # slowapi Limiter adaptori — main.py'nin app.state.limiter +
│                                   # 5 modulun @limiter.limit(...) decorator'lari (TAMAMEN AYRI
│                                   # bir mekanizma, rate_limit_middleware.py ile karistirilmasin)
├── database/                      # DB engine/session bootstrap (4 dosya)
│   ├── connection.py              # engine, AsyncSessionLocal, get_db, session_scope
│   ├── db_session.py              # _session_ctx, get_async_session_context
│   ├── init_db.py                 # init_primary_data (elle-calistirilan dev-bootstrap script'i)
│   └── backup_manager.py          # DatabaseBackupManager (pg_dump wrapper)
├── security/                      # PII sifreleme (2 dosya)
│   ├── pii_encryption.py          # encrypt_pii, decrypt_pii, blind_index, trigram_blind_indexes
│   └── pii_scrubber.py            # scrub_pii (log/serialize oncesi PII maskeleme)
├── context/                       # Request-scoped context (2 dosya)
│   ├── request_context.py         # get/set_correlation_id, get/set_request_path
│   └── correlation_middleware.py  # CorrelationMiddleware
├── logging/
│   └── logger.py                  # get_logger, setup_logging, get_audit_logger (17+ cagiran — en yogun dosya)
├── audit/
│   └── audit_logger.py            # audit_log decorator, log_audit_event, admin_audit_log cift-yazim
├── background/                    # Celery + async job manager (4 dosya)
│   ├── celery_app.py              # celery_app, beat_schedule (12 modulun task'ini register eder)
│   ├── job_manager.py             # BackgroundJobManager, AsyncJobStatus (Redis-backed job durumu)
│   ├── backup_tasks.py            # tum PostgreSQL DB'yi yedekler (gunluk beat) — genuinely platform-genel
│   └── error_digest.py            # 5-dk error digest + monthly partition + db health check task'lari
├── websocket/                     # admin_platform+notification arasinda paylasilan WS altyapisi (2 dosya)
│   ├── connection_manager.py      # ConnectionManager (per-user WS registry)
│   └── ws_auth.py                 # verify_ws_token, resolve_ws_identity, is_admin_email
└── api_utils.py                   # parse_date_param — fuel+reports'un paylastigi generic tarih-parse helper'i
```

## İsim çakışması: iki `get_event_bus`

`events.event_bus.get_event_bus()` (domain **EventBus** — `@publishes`
decorator'ıyla business modüllerin yayınladığı olaylar, ör. `TripCreated`)
ile `monitoring.event_bus.get_event_bus()` (**ErrorEventBus** —
main.py'nin lifespan'ı + Sentry hook'unun kullandığı hata/alarm bus'ı) aynı
isimde ama TAMAMEN farklı iki sınıf/dosya. `public.py`'de ikinci biri
`get_error_event_bus` diye yeniden adlandırılarak import edilir:

```python
from v2.modules.platform_infra.events.event_bus import get_event_bus
from v2.modules.platform_infra.monitoring.event_bus import get_event_bus as get_error_event_bus
```

Pratikte application-katmanı kodu `get_error_event_bus`'ı neredeyse hiç
doğrudan çağırmaz — bunun yerine `monitoring.emit`/`aemit` (senkron/async
sarmalayıcılar, kendi içlerinde `get_event_bus()`'ı — yani ErrorEventBus'ı
— çağırır) kullanılır; bu iki fonksiyon da `public.py`'den export edilir.

## Public API (public.py'nin gerçekte export ettiği — özet)

Tam liste `public.py`'nin `__all__`'ında; kategoriler: cache (13 sembol),
domain event bus (5), DI composition root (3), request context (6),
database (8), structured logging (3), metrics (3), ASGI middleware (4),
error/alarm monitoring (~25), resilience (10), security/PII (6), audit (3),
background jobs (3). **`background.celery_app` ve `websocket.*` public.py'de
YOK** — aşağıdaki "circular-import notu"na bakın.

## `public-surface-only-platform_infra` kontratı — kritik uygulama notu

`.importlinter`'daki kontrat `type = forbidden` + **`allow_indirect_imports
= true`**. Bu ikinci ayar ZORUNLU: import-linter'ın normal "forbidden"
davranışı TÜM transitif zinciri tarar, ama `platform_infra.public`'in
KENDİSİ zaten `monitoring`/`events`/`cache`/... alt modüllerini import
ediyor (o, sanctioned gateway) VE hemen hemen her iş modülünün application
katmanı (dolaylı olarak) başka bir modülün `public.py`'sine, o da kendi
`api`/`infrastructure` katmanına (platform_infra'yı zaten meşru şekilde
DOĞRUDAN kullanan) uzanıyor. Normal transitif taramayla bu kontrat 179
"sahte" ihlal üretti (hepsi meşru api/infrastructure/domain katmanı
kullanımıydı — kontratın kapsamı SADECE `.application` katmanı).
`allow_indirect_imports=true`, grimp'in kontrolünü yalnızca DOĞRUDAN
import kenarlarına indirger (`find_modules_directly_imported_by`) — artık
kontrat gerçekten "application katmanı platform_infra alt modüllerini
DOĞRUDAN import ediyor mu" sorusuna cevap veriyor, transitif gürültü yok.

`middleware`/`background`/`websocket` forbidden_modules'te var ama hiçbir
application dosyası bunları zaten import ETMİYOR (main.py'nin kendi
middleware zinciri + admin_platform/notification'ın kendi api/infrastructure
katmanları kullanıyor, ikisi de bu kontratın kapsamı dışı) — bu üç kalem
listede sadece gelecekte biri yanlışlıkla application katmanından bunlara
uzanırsa yakalansın diye duruyor.

## `public.py`'de KASITLI OLARAK export EDİLMEYEN iki şey

`background.celery_app.{celery_app,get_celery_app}` ve
`websocket.{connection_manager,ws_auth}` — ikisi de kendi modül
gövdelerinde eager (module-level) olarak business-modül zincirlerine
giriyor:

- `celery_app.py` 12 iş modülünün task dosyasını `import
  v2.modules.<X>.infrastructure.*_tasks` ile module-level import ediyor
  (Celery task-registrasyonu için gerekli).
- `websocket/ws_auth.py` `from v2.modules.auth_rbac.public import (...)`
  yapıyor module-level.

`public.py` KENDİSİ application-katmanı dosyalarının EN ÜSTÜNDE import
edildiği için (module-level `from v2.modules.platform_infra.public import
X`), bu ikisini `public.py`'ye eklemek gerçek bir circular-import'a yol
açtı — canlı olarak pytest koşumunda yakalandı
(`ImportError: cannot import name 'get_logger' from partially initialized
module 'v2.modules.platform_infra.public'`): `public.py` → `celery_app.py`
→ `app.workers.tasks.backup_tasks` → ... → `ai_assistant.public` →
`knowledge_base.py` (application katmanı) → `platform_infra.public`
(henüz tamamlanmamış, kendi kendine dönen import). Hiçbir application
dosyası zaten bu ikisini kullanmıyor (yalnız main.py + admin_platform/
notification'ın kendi api/infrastructure katmanları) — o tüketiciler kendi
doğrudan yollarından import etmeye devam eder.

## Ölü kod / bilinçli olarak taşınmayanlar

- `app/database/migrations/*.sql` (2 dosya) — bu dalganın kapsamı dışı
  bırakıldı, muhtemelen dead `model_versions` referansı taşıyor, ayrı
  inceleme gerektiriyor.
- `database/init_db.py::init_primary_data` — sıfır gerçek prod çağıranı
  var ama elle-çalıştırılan bir dev-bootstrap script'i (production-guard'ı
  var) — silme kararı ayrı bir onay gerektirir, mekanik olarak taşındı.

## Sonradan bulunan 2. tur (2026-07-22, "V2 dışında kalan var mı" denetimi)

Dalga 17'nin 10-commit taşıması bittikten sonra yapılan ek bir kalıntı
taramasında bulunup taşınan/silinen 4 kalem:

- `app/api/middleware/rate_limiter.py` → `middleware/slowapi_limiter.py`
  — 6+ modül + main.py kullanıyordu, orijinal taramada kaçmıştı.
- `app/api/v1/utils.py` → `api_utils.py` — yalnız 2 modül (fuel, reports)
  kullanıyor, "3+ modül" eşiğinin altında ama küçük/generic olduğu için
  yine de taşındı.
- `app/core/services/ai_service.py` — **silindi** (ölü kod). `app/core/ai/*`
  ve diğer "FAZ4'te silinir" shim'lerinden farklı olarak bunun hiçbir
  gerçek çağıranı (test dahi) yoktu — dokümante edilmemiş, sessizce
  orphan kalmış bir shim'di.
- `app/workers/tasks/{backup_tasks,error_digest}.py` →
  `background/{backup_tasks,error_digest}.py` — ikisi de "monitoring henüz
  taşınmadı, tek başına taşımak tutarsız olur" gerekçesiyle dalga 17'nin
  başında `app/`'de bırakılmıştı; monitoring artık taşındığı için (commit 5)
  bu gerekçe geçersiz oldu. `app/workers/` paketi (yalnız ölü bir
  `run_prediction_task` re-export'u kalmıştı, gerçek çağıranı yoktu)
  tamamen silindi.

## Test stratejisi

Her alt-paketin kendi doğrudan test dosyası var (`app/tests/unit/
test_infrastructure/`, `app/tests/unit/test_monitoring/`,
`app/tests/unit/test_repositories/test_base_repository_more.py` vb.).
Inline (fonksiyon-içi) import kullanan application-katmanı çağrı
noktalarının testleri — dalga 17 commit 10'da `public.py`'ye yönlendirme
sırasında keşfedildi — artık kaynak olarak `v2.modules.platform_infra.
public.<sembol>` patch ediyor (ör. `test_anomaly_detector_more.py`,
`test_auth_service_coverage.py`, `test_sefer_fuel_estimator.py`,
`test_sefer_service_coverage.py`, `test_import_service*.py`,
`test_prediction_service_coverage.py`, `test_sefer_write_more.py`,
`test_trip_planner_weather.py`) — kök CLAUDE.md'nin "test patch-target
convention"ı (module-level import → tüketici modülü patch et; inline
import → kaynak modülü patch et) burada da geçerli, kaynak artık
`public.py`.
