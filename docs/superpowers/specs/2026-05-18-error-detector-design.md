# LojiNext Kapsamlı Hata Dedektörü — Tasarım Spesifikasyonu

**Tarih:** 2026-05-18
**Durum:** Onaylandı
**Kapsam:** Backend, Frontend, DB, Celery, External API, Security, ML — sıfır körnokta

---

## 1. Motivasyon ve Mevcut Durum

### Zaten Var Olanlar
- `main.py`: HTTPException, ValidationError, DomainError, SAOperationalError, catchall handler
- Sentry entegrasyonu (4xx drop, before_send filtresi)
- `ErrorBoundary` (iki versiyon: common + ui)
- `error-tracker.ts`: window.onerror, unhandledrejection, LCP/TTFB → `/system/error-report`
- Telegram notifier (kritik olaylarda fire-and-forget)
- Prometheus `/metrics`, OTEL (opsiyonel)
- JSON structured logging + correlation ID

### Tespit Edilen Körnoktalr
| Katman | Körnokta |
|---|---|
| DB | Yavaş sorgu (sorgu bazında), IntegrityError/DataError/deadlock, N+1, lock wait, long TX, pool baskı |
| Celery | Task failure/retry, beat schedule watchdog, queue backlog, worker memory leak |
| Service | Sessiz swallow, business invariant ihlali, async context leak |
| Frontend | Axios 4xx/5xx sistematik yakalanmıyor, console.error, Zustand/React Query hataları, resource 404 |
| External | ORS/Groq/Telegram — yavaşlık, 5xx, ulaşılamazlık izlenmiyor |
| Security | Brute force, JWT anomali, RBAC ihlali aggregasyonu yok |
| ML | Physics fallback oranı, model drift sessiz |
| Alarm | Her hata anında Telegram → spam; aggregation/rate-limit yok |

---

## 2. Hedefler

1. Her katmanda mikroskobik hata dahil sıfır körnokta
2. Redis (geçici buffer) + PostgreSQL (kalıcı) depolama
3. `critical` → anında Telegram + Sentry; `error` → 5dk digest; `warning` → log + sayaç
4. Z-score anomali tespiti ile istatistiksel spike alarm
5. `SistemSaglikPage`'e SSE destekli real-time dashboard
6. Frontend-backend trace_id korelasyonu

---

## 3. Genel Mimari

```
┌─────────────────────────────────────────────────────────────────┐
│                     KATMAN PROBEları                            │
│                                                                 │
│  [DB]  [Celery]  [Service]  [Frontend]  [External]  [Security] [ML] │
│    │       │         │          │            │           │       │  │
│    └───────┴─────────┴──────────┴────────────┴───────────┴───────┘  │
│                            │                                    │
│                    [ErrorEventBus]                              │
│                (app/infrastructure/monitoring/)                 │
│                            │                                    │
│             ┌──────────────┼──────────────┐                     │
│             │              │              │                     │
│        [Redis]       [PostgreSQL]    [Telegram/Sentry]          │
│       (dedup+buf)    (error_events)   (alarm routing)           │
│                            │                                    │
│              [SistemSaglikPage — SSE Dashboard]                 │
└─────────────────────────────────────────────────────────────────┘
```

### Yeni Dosya Yapısı
```
app/infrastructure/monitoring/
    __init__.py
    event_bus.py          ← ErrorEventBus merkez motoru
    db_probe.py           ← SQLAlchemy event listeners
    celery_probe.py       ← Celery signals
    service_probe.py      ← @monitor_errors, @intentional_fallback, assert_invariant
    external_api_probe.py ← httpx event_hooks
    security_probe.py     ← BruteForceDetector, JWT anomali
    ml_probe.py           ← Fallback oranı, drift
    alarm_router.py       ← AnomalyDetector (Z-score), severity matrix

app/workers/tasks/
    error_digest.py       ← Celery beat: 5dk digest + flush + beat watchdog

alembic/versions/
    xxxx_add_error_events.py

app/api/v1/endpoints/system.py   ← yeni endpoint'ler

frontend/src/services/
    error-tracker.ts             ← trace_id korelasyonu, sendBeacon, captureApiError
    api/axios-instance.ts        ← response interceptor genişletme

frontend/src/hooks/
    use-render-guard.ts          ← aşırı re-render dedektörü
    use-event-source.ts          ← SSE hook

frontend/src/pages/admin/
    SistemSaglikPage.tsx         ← yeni Hata Analizi sekmesi
```

---

## 4. ErrorEventBus — Merkez Motor

### ErrorEvent Veri Modeli
```python
@dataclass
class ErrorEvent:
    layer: ErrorLayer          # Enum: db|celery|api|service|frontend|external|security|ml
    category: str              # "slow_query", "task_failure", "brute_force" ...
    severity: ErrorSeverity    # Enum: critical|error|warning|info
    message: str
    fingerprint: str           # Blake2b-128, normalized message hash
    stack_hash: str            # İlk 5 frame hash'i
    trace_id: str = ""
    metadata: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
```

### Fingerprint Algoritması
```python
# Değişken kısımları normalize et → aynı hatanın farklı parametreleri aynı fingerprint alır
normalized = re.sub(r'\b\d+\b', 'N', message)        # sayılar → N
normalized = re.sub(r"'[^']*'", "'S'", normalized)   # string literal → S
fingerprint = blake2b(
    f"{layer}:{category}:{normalized}".encode(),
    digest_size=8
).hexdigest()
```

### Redis Pipeline (Atomic)
```
MULTI
  HINCRBY  error:count:{fingerprint}  count  1
  HSET     error:count:{fingerprint}  last_seen {now}
  EXPIRE   error:count:{fingerprint}  86400
  ZADD     error:stream:{severity}    {timestamp}  {event_json}
  LPUSH    error:flush_queue          {event_json}
EXEC
```

### Async Batch Writer
- `asyncio.Queue(maxsize=10_000)` — 5 saniye veya 200 event → tek `INSERT ... ON CONFLICT DO UPDATE`
- **Circuit breaker:** 3 ardışık DB write hatası → Redis-only moda geç + critical alarm
- Kuyruk dolunca (10k) → oldest drop + critical alarm ("event bus overflowing")

---

## 5. DB Probe

### 5.1 Sorgu Timing (SQLAlchemy Events)
```python
@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before(conn, cursor, statement, params, context, executemany):
    conn.info["query_start"] = time.monotonic()

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after(conn, cursor, statement, params, context, executemany):
    elapsed_ms = (time.monotonic() - conn.info.pop("query_start", 0)) * 1000
    if elapsed_ms > 500:
        severity = "error" if elapsed_ms > 2000 else "warning"
        emit(ErrorEvent(layer="db", category="slow_query", severity=severity,
            metadata={"query_ms": elapsed_ms,
                      "statement_fingerprint": _sql_fingerprint(statement)}))
```

### 5.2 Otomatik EXPLAIN ANALYZE
- Sorgu > 2000ms → ayrı bağlantıyla `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` çalıştırılır
- Sequential Scan on büyük tablo → index önerisi metadata'ya eklenir

### 5.3 SQL Fingerprint
```python
def _sql_fingerprint(stmt: str) -> str:
    normalized = sqlparse.format(stmt, strip_whitespace=True, keyword_case="upper")
    normalized = re.sub(r"\b\d+\b", "?", normalized)
    normalized = re.sub(r"'[^']*'", "?", normalized)
    return blake2b(normalized.encode(), digest_size=6).hexdigest()
```

### 5.4 PostgreSQL Error Code Mapping
```python
_PG_CODE_MAP = {
    "40001": "deadlock", "40P01": "deadlock",
    "23505": "unique_violation", "23503": "fk_violation",
    "23502": "not_null_violation", "23514": "check_violation",
    "53300": "too_many_connections", "57P03": "db_unavailable",
    "55P03": "lock_not_available",
}
_CRITICAL_PG_CODES = {"53300", "57P03", "40P01"}
```

### 5.5 Connection Pool Monitörü
- `checkout` event: `checkedout / pool.size > 0.85` → error

### 5.6 N+1 Sorgu Tespiti
- `ContextVar[Counter]` ile her request için sorgu sayacı
- 20+ sorgu / request → warning (`category="n_plus_one_suspect"`)

### 5.7 Celery Beat Görevleri (5dk'da bir)
```sql
-- Long-running transaction (>30s)
SELECT pid, now() - xact_start AS duration, query, state, wait_event_type
FROM pg_stat_activity
WHERE xact_start IS NOT NULL AND now() - xact_start > interval '30 seconds'
AND state != 'idle';

-- Lock wait zinciri
SELECT blocking.pid, blocked.pid, blocked.query, blocking.query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE blocked.wait_event_type = 'Lock';

-- Dead tuple oranı >%20
SELECT relname, n_dead_tup, n_live_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup+n_dead_tup,0)*100, 1) AS dead_pct
FROM pg_stat_user_tables WHERE n_dead_tup > 1000 ORDER BY dead_pct DESC;
```

---

## 6. Celery Probe

### 6.1 Signals
```python
@task_failure.connect
def on_failure(task_id, exception, sender, **_):
    is_final = sender.request.retries >= sender.max_retries
    emit(ErrorEvent(layer="celery",
        category="task_failure_final" if is_final else "task_failure",
        severity="critical" if is_final else "error",
        metadata={"task": sender.name, "retries": sender.request.retries,
                  "exception_type": type(exception).__name__}))

@task_retry.connect
def on_retry(request, reason, **_):
    emit(ErrorEvent(layer="celery", category="task_retry", severity="warning",
        metadata={"task": request.task, "retry_count": request.retries}))
```

### 6.2 Beat Schedule Watchdog (Heartbeat Pattern)
```python
# Her task çalışınca Redis'e son çalışma zamanını yaz
@task_postrun.connect
def _record_heartbeat(sender, **_):
    redis.set(f"beat:last_run:{sender.name}", time.time(), ex=7200)

# check_beat_health Celery task (5dk'da bir)
EXPECTED_TASKS = {
    "relay-outbox-events-every-60s": 120,
    "check-ml-drift-every-1h": 3900,
    "error-digest-every-5m": 600,
}
```

### 6.3 Task Süresi + Worker Memory
- Prerun/postrun hook ile elapsed tracking
- Task > 30s → warning; `resource.getrusage` ile RSS > 800MB → error

### 6.4 Queue Depth
- `celery_app.control.inspect().reserved()` → toplam bekleyen > 100 → warning, > 500 → error

---

## 7. Service Probe

### 7.1 @monitor_errors Dekoratör
```python
def monitor_errors(category="service_error", severity="error",
                   reraise=True, capture_result=False):
    # Tüm exception'ları yakalar, DomainError'u pass eder (zaten handler'da)
    # reraise=True: hata devam eder (swallow değil)
    # capture_result=True: None dönen method'ları izler
```

### 7.2 @intentional_fallback Dekoratör
```python
def intentional_fallback(reason: str):
    # Kasıtlı sessiz fallback — monitor_errors'dan ayırt edilir
    # WARNING seviyesi + reason string ile loglanır
    # Örnek: @intentional_fallback("ORS API down, cached route kullan")
```

### 7.3 assert_invariant
```python
def assert_invariant(condition: bool, message: str, severity="error"):
    # Exception değil yanlış değer (fuel < 0, mesafe > 10000 km)
    if not condition:
        emit(ErrorEvent(layer="service", category="invariant_violation", ...))
```

### 7.4 Call Chain Tracking
- `ContextVar[list]` ile servis çağrı zinciri izlenir
- Hata anında metadata'ya `{"call_chain": ["SeferService.create", "RouteService.calc"]}` eklenir

### 7.5 Async Context Leak Dedektörü
```python
# asyncio.get_event_loop().set_exception_handler(...)
# Dangling coroutine ve unhandled asyncio exception'ları yakalanır
```

---

## 8. Frontend Probe (4 + 5 Katman)

### 8.1 Axios Interceptor
- Tüm 4xx/5xx response'ları otomatik yakalanır
- `X-Correlation-ID` header'ı `backend_trace_id` olarak error report'a eklenir
- Network error (status yok) → `severity: "fatal"`

### 8.2 console.error Monkey-Patch
```typescript
// Kütüphane hatalarını yakalar
// Bilinen noise pattern'ları (React DevTools vs.) filtrelenir
const _originalConsoleError = console.error.bind(console);
console.error = (...args) => { _originalConsoleError(...args); /* capture */ };
```

### 8.3 Web Vitals (INP dahil)
- `web-vitals` paketi: LCP, FID, CLS, INP, TTFB
- INP > 200ms → warning; > 500ms → error (Google Core Web Vitals eşikleri)
- LCP > 4s → warning (mevcut); TTFB > 2s → warning (mevcut)

### 8.4 navigator.sendBeacon
- `pagehide` event → normal axios/fetch çalışmaz
- `sendBeacon('/api/v1/system/error-report-batch', pending)` — tarayıcı garantili gönderim

### 8.5 Resource Loading Failure (PerformanceObserver)
- `transferSize=0 && decodedBodySize=0 && duration>0` → 404'lenen script/CSS/image

### 8.6 React Aşırı Re-render
```typescript
export function useRenderGuard(componentName: string, threshold = 3) {
    // 3+ render / 100ms → warning
}
```

### 8.7 Zustand Store Middleware
```typescript
// State mutasyonu exception → errorTracker.capture()
const errorMiddleware = (config) => (set, get, api) => config((...args) => {
    try { set(...args); } catch (err) { errorTracker.capture(err); throw err; }
}, get, api);
```

### 8.8 React Query Global Error Handler
```typescript
const queryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (error, query) => { /* capture */ } }),
    mutationCache: new MutationCache({ onError: (error) => { /* capture */ } }),
});
```

### 8.9 Frontend-Backend Trace Korelasyonu
```typescript
interface ErrorReport {
    // ...mevcut alanlar
    backend_trace_id?: string;   // X-Correlation-ID header'dan
    frontend_session_id: string; // tab/session bazlı UUID
}
```

---

## 9. External API Probe

httpx `event_hooks` ile ORS, Groq, Telegram izlenir:

```python
THRESHOLDS_MS = {"ors": 3000, "groq": 10000, "telegram": 2000}

# on_response: status >= 500 → error; elapsed > threshold → warning
# on_error: ulaşılamazlık → critical
```

Mevcut `httpx.AsyncClient` çağrıları probe instance'ı üzerinden yapılır.

---

## 10. Security Probe

### 10.1 Brute Force Dedektörü
```python
class BruteForceDetector:
    # Aynı IP'den 60s içinde 10+ 401 → critical alarm
    _window: dict[str, deque] = defaultdict(deque)
```

### 10.2 JWT Anomali
- `ExpiredSignatureError` → warning (normal expiry)
- `ImmatureSignatureError` → error (clock skew, saldırı olabilir)
- `DecodeError` → error (manipülasyon)

### 10.3 RBAC İhlali Aggregasyonu
- 403 response'ları `user_id + endpoint` bazlı sayılır
- 5dk içinde aynı kullanıcıdan 20+ 403 → error (permission scraping)

---

## 11. ML Probe

```python
class MLProbe:
    # Her 100 tahmin sonra fallback oranı kontrol edilir
    # fallback_rate > 0.80 → error ("model çalışmıyor, physics'e düştük")
    # Model load failure → critical (uygulama başlangıcında)
```

---

## 12. Alarm Router

### 12.1 Z-Score Anomali Tespiti
```python
class AnomalyDetector:
    WINDOW_SIZE = 12  # 12 × 5dk = 1 saat rolling window

    def check_spike(self, layer, category) -> bool:
        # Son 12 periyodun hata sayılarını al
        # Z-score = (current - mean) / stdev
        # Z > 3.0 → istatistiksel anomali → severity'yi critical'a çık
```

### 12.2 Severity Matrix
| Severity | İlk Tetiklenme | Tekrar | Digest |
|---|---|---|---|
| critical | Anında Telegram + Sentry | 15dk sonra tekrar | — |
| error | Redis'e yaz | — | 5dk özet |
| warning | Log + sayaç | — | 1 saatlik |
| anomaly (Z>3) | critical'a çık → anında | — | — |

### 12.3 Digest Format (Telegram)
```
📊 5dk Özet — 14:35-14:40
  🔴 DB: 3 hata (2× unique_violation, 1× slow_query)
  🟡 Frontend: 7 uyarı (4× api_4xx, 3× console_error)
  📈 Service: normal
```

---

## 13. PostgreSQL Şeması

```sql
CREATE TYPE error_layer AS ENUM
  ('db','celery','api','service','frontend','external','security','ml');
CREATE TYPE error_severity AS ENUM ('critical','error','warning','info');

-- Ana tablo: fingerprint başına 1 aktif satır (upsert ile güncellenir)
CREATE TABLE error_events (
    id              BIGSERIAL PRIMARY KEY,
    fingerprint     CHAR(16)         NOT NULL,
    layer           error_layer      NOT NULL,
    category        VARCHAR(60)      NOT NULL,
    severity        error_severity   NOT NULL,
    message         TEXT             NOT NULL,
    count           INTEGER          NOT NULL DEFAULT 1,
    first_seen      TIMESTAMPTZ      NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ      NOT NULL DEFAULT now(),
    trace_id        VARCHAR(64),
    user_id         INTEGER          REFERENCES kullanici(id) ON DELETE SET NULL,
    path            VARCHAR(500),
    stack_trace     TEXT,
    metadata        JSONB            NOT NULL DEFAULT '{}',
    resolved_at     TIMESTAMPTZ,
    resolved_by     INTEGER          REFERENCES kullanici(id) ON DELETE SET NULL
);

-- Ham zaman serisi log (günlük partition)
CREATE TABLE error_occurrences (
    id              BIGSERIAL,
    fingerprint     CHAR(16)         NOT NULL,
    layer           error_layer      NOT NULL,
    severity        error_severity   NOT NULL,
    trace_id        VARCHAR(64),
    metadata        JSONB            NOT NULL DEFAULT '{}',
    occurred_at     TIMESTAMPTZ      NOT NULL DEFAULT now()
) PARTITION BY RANGE (occurred_at);

-- İndeksler
CREATE UNIQUE INDEX idx_error_events_fingerprint_active
    ON error_events(fingerprint) WHERE resolved_at IS NULL;
CREATE INDEX idx_error_events_layer_sev
    ON error_events(layer, severity, last_seen DESC);
CREATE INDEX idx_error_occurrences_time
    ON error_occurrences(occurred_at DESC, layer);
CREATE INDEX idx_error_events_trace_id
    ON error_events(trace_id) WHERE trace_id IS NOT NULL;

-- Dashboard için materialized view (5dk'da bir Celery beat ile refresh)
CREATE MATERIALIZED VIEW error_hourly_stats AS
SELECT
    date_trunc('hour', occurred_at) AS hour,
    layer, severity,
    COUNT(*) AS event_count
FROM error_occurrences
WHERE occurred_at > now() - INTERVAL '24 hours'
GROUP BY 1, 2, 3;
CREATE UNIQUE INDEX ON error_hourly_stats(hour, layer, severity);
```

---

## 14. Backend API Endpoint'leri

```
GET  /api/v1/system/error-events          paginated, filter: layer/severity/hours
GET  /api/v1/system/error-stats           saatlik aggregation (mat. view)
GET  /api/v1/system/error-stream          SSE — PostgreSQL LISTEN/NOTIFY
POST /api/v1/system/error-events/{id}/resolve
POST /api/v1/system/error-report          mevcut (tek hata, frontend)
POST /api/v1/system/error-report-batch    YENİ (sendBeacon, array)
```

---

## 15. Dashboard (SistemSaglikPage)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ● CANLI  │ Son 24 Saat: N hata  │ Çözümsüz: N kritik             │
├──────────┬──────────┬────────────┬──────────────────────────────   │
│  DB      │ Celery   │ Frontend   │ Service  External  Security  ML  │
├──────────┴──────────┴────────────┴──────────────────────────────   │
│  [Saatlik hata grafiği — recharts — layer renk kodlamalı]          │
├─────────────────────────────────────────────────────────────────────┤
│ Fingerprint │ Layer │ Severity │ Count │ Son görülme │ Trace ID     │
│ a3f8b2c1.. │ 🔴 db │ critical │  23x  │ 2dk önce   │ abc123 🔗    │
└─────────────────────────────────────────────────────────────────────┘
```

- `useEventSource` hook ile SSE → yeni hata gelince satır otomatik eklenir
- Trace ID → backend log linkine tıklanabilir
- "Çözüldü" butonu → `POST /error-events/{id}/resolve`
- PostgreSQL `NOTIFY error_events_channel` → SSE stream

---

## 16. Entegrasyon Noktaları

### Probe Aktivasyonu (app/main.py lifespan)
```python
async def lifespan(app):
    from app.infrastructure.monitoring import activate_all_probes
    activate_all_probes(engine, celery_app)
    yield
    ...
```

### Service Probe Entegrasyonu
Mevcut `app/core/services/` ve `app/services/` altındaki tüm public methodlara `@monitor_errors` eklenir.

### httpx Client Entegrasyonu
External API çağrıları `ExternalAPIProbe` instance'ının `event_hooks` parametresiyle wrap edilir.

---

## 17. Kapsam Dışı

- Tam ELK/Loki stack kurulumu (mevcut JSON log dosyası korunur)
- Multi-tenant hata izolasyonu (sistem single-tenant)
- Mobil uygulama hata takibi
- Distributed tracing (OTEL zaten opsiyonel olarak mevcut)
