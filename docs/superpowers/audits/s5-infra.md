# S5 — Infrastructure + Workers Bulguları

Kapsam: app/infrastructure/** + app/workers/**. Plan S5.

## S5-1 — security(4) + middleware(3) + context(3) — 5 bulgu

Temiz/örnek: `jwt_handler` (aud/iss/iat/exp/jti/typ, refresh ayrı audience+typ kontrolü, alg-pinned decode,
hash_token sabit-zaman compare); `permission_checker` (SecurityService delege, OR-list); `body_size_middleware`
(Content-Length cap→413, chunked passthrough doğru); `logging_middleware` (query-param maskeleme, güvenlik
header'ları nosniff/DENY/XSS, correlation propagation); `correlation_middleware` (gelen X-Correlation-ID UUID4
regex doğrulaması → log-injection önler, truncate log, finally clear_context); `request_context` (ContextVar,
clear). `token_blacklist` fail-secure (Redis down→revoked say, SEC-004).

### AUDIT-136 — token_blacklist Redis anahtarı olarak HAM JWT'yi saklıyor (`blacklist:{token}`); hash_token mevcutken kullanılmıyor
- Şiddet: low
- Sınıf: security
- Konum: token_blacklist.py:33,52
- Durum: confirmed
- Kanıt:
    ```python
    key = f"blacklist:{token}"          # ham JWT keyspace'e yazılıyor
    await set_redis_val(key, "1", expire=ttl)
    ```
  Aynı modülün çağırdığı `jwt_handler.hash_token` (SHA-256) tam bu amaç için var ("Tokens exceed bcrypt's
  72-byte limit"); ama blacklist ham token'ı anahtar yapıyor → Redis keyspace okuyabilen herkes iptal
  edilmiş (ve hâlâ süresi dolmamış) JWT'leri görür + gereksiz büyük anahtarlar. `jti` veya `hash_token(token)`
  ile anahtarlanmalı.
- Önerilen düzeltme: `key = f"blacklist:{hash_token(token)}"` (add+is_blacklisted ikisinde); ideali jti bazlı.
- Bağımlılık: AUDIT-140 (jti tutarsızlığı — jti bazlı blacklist için jti her token'da olmalı).

### AUDIT-137 — pii_scrubber: telefon regex `\d{10,13}` 11-haneli TCKN'yi önce yakalıyor → TCKN pattern erişilemez + aşırı maskeleme
- Şiddet: low
- Sınıf: bug
- Konum: pii_scrubber.py:28-32,48-50
- Durum: confirmed
- Kanıt:
    ```python
    PII_PATTERNS = [
        (r"[\w\.-]+@[\w\.-]+\.\w+", "<EMAIL_MASKED>"),
        (r"\+?\d{10,13}", "<PHONE_MASKED>"),   # 11 hane dahil → TCKN'yi yer
        (r"\b\d{11}\b", "<TCKN_MASKED>"),       # 11-hane bu noktaya hiç ulaşmaz
    ]
    for pattern, mask in PII_PATTERNS:
        processed = re.sub(pattern, mask, processed)
    ```
  Telefon kalıbı 10-13 haneyi yakalar; 11-haneli TCKN buna dahil → sırayla önce telefon uygulanır, TCKN
  `<PHONE_MASKED>` etiketiyle maskelenir, gerçek TCKN kalıbı ölü kod. Ayrıca word-boundary'siz `\d{10,13}`
  rastgele 10-13 haneli sayı dizilerini (sipariş ID, epoch-ms timestamp) de maskeler → aşırı maskeleme
  (güvenli yön ama log'da gürültü). Etiket yanlışlığı düzeltilmeli, TCKN kalıbı telefondan önce gelmeli.
- Önerilen düzeltme: TCKN (`\b\d{11}\b`) kalıbını telefon'dan **önce** koy; telefona word-boundary ekle.
- Bağımlılık: yok.

### AUDIT-138 — rate-limit middleware login endpoint'ini (`/api/v1/auth/token`) ATLIYOR → credential brute-force/stuffing middleware katmanında sınırsız
- Şiddet: medium
- Sınıf: security
- Konum: rate_limit_middleware.py:20-27,49-55
- Durum: needs-verification
- Kanıt:
    ```python
    _SKIP_PATHS = frozenset(["/docs","/openapi.json","/","/api/v1/auth/token"])
    if request.url.path in _SKIP_PATHS or ...: return await call_next(request)
    ```
  En çok brute-force çekICI endpoint (login/token) açıkça rate-limit dışı bırakılmış. `logging_middleware`
  içindeki brute-force detektörü yalnız **kaydeder** (bloklamaz). Hesap-kilitleme telafi ediyorsa kabul
  edilebilir; etmiyorsa IP başına parola deneme sınırı yok. Telafi mekanizması doğrulanmalı.
- Önerilen düzeltme: login için ayrı, daha sıkı bir rate-limit bucket'ı uygula (IP+username, dakika başına
  birkaç deneme) ya da brute-force detektörünü bloklayıcı hale getir.
- Bağımlılık: security_probe brute-force detector; auth_service hesap-kilitleme (S2b).

### AUDIT-139 — rate-limit anahtarı spoof'lanabilir `X-Forwarded-For` ilk değerine dayanıyor → per-IP limit atlanabilir
- Şiddet: medium
- Sınıf: security
- Konum: rate_limit_middleware.py:114-118,61
- Durum: needs-verification
- Kanıt:
    ```python
    def _get_client_ip(self, request):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded: return forwarded.split(",")[0].strip()   # istemci-kontrollü
        ...
    bucket = f"{client_ip}:{user_id or 'anon'}:{request.url.path}"
    ```
  XFF'i koşulsuz güveniyor; uygulama XFF'i ezen güvenilir proxy ardında değilse, istemci her istekte sahte
  bir `X-Forwarded-For` göndererek her seferinde yeni bucket üretir → per-IP limit hiç dolmaz (anonim DoS/
  brute-force bypass). Güvenilir-proxy/`TrustedHost`/XFF-strip yapılandırması doğrulanmalı.
- Önerilen düzeltme: yalnız bilinen proxy sayısı kadar sağdaki XFF entry'sine güven (ör. `X-Forwarded-For`'un
  sondan n. değeri) ya da proxy yoksa `request.client.host`'a düş; güvenilir proxy CIDR listesi tut.
- Bağımlılık: deployment topolojisi (S7 docker/nginx), AUDIT-138.

### AUDIT-140 — İKİ ayrı access-token fabrikası: `core.security.create_access_token` (jti YOK) vs `jwt_handler.create_access_token` (jti VAR) → claim drift
- Şiddet: medium
- Sınıf: maintainability
- Konum: app/core/security.py:41-70 vs app/infrastructure/security/jwt_handler.py:47-69
- Durum: confirmed
- Kanıt:
    ```python
    # core/security.py
    to_encode.update({"exp":expire,"iat":now,"aud":...,"iss":...,"typ":"access"})  # jti YOK
    # jwt_handler.py
    to_encode.update({"exp":expire,"iat":now,"jti":str(uuid.uuid4()),"aud":...,"iss":...,"typ":"access"})
    ```
  Aynı sorumluluğu taşıyan iki token üretici drift etmiş: jwt_handler `jti` ekliyor, core.security eklemiyor.
  CLAUDE.md "token logic app/core/security.py'de" diyor → canlı yol jti'siz token üretiyor olabilir; jti'ye
  dayanan herhangi bir mekanizma (per-token revocation, audit korelasyonu) bu tokenlarda None bulur. Hangi
  fabrikanın `/auth/token`'a bağlı olduğu + jti tüketen kod doğrulanmalı; tek implementasyona indirilmeli.
- Önerilen düzeltme: tek canonical token fabrikası bırak (jti dahil tüm claim'lerle); diğerini ona delege et
  (password fonksiyonlarının zaten delege edildiği gibi).
- Bağımlılık: AUDIT-136 (jti bazlı blacklist), AUDIT-011 (S1 UoW carry değil — JWT carry burada kapandı).

## S5-2 — events(5) + audit(2) — 5 bulgu

Temiz/örnek: `outbox_service.save_event/relay` (FOR UPDATE SKIP LOCKED, retry<5 cap, shutdown-aware,
flush-for-id); `audit_logger._persist_audit_to_db` (parametrize SQL CAST AS JSONB, user_id<=0→NULL FK
guard, shared session begin_nested SAVEPOINT, alan truncate, asla raise etmez); `event_types` enum;
`contracts` Pydantic (iz: `datetime.utcnow()` naive+deprecated — event_bus publish_typed `.replace(utc)`
ile telafi ediyor, low). __init__'ler trivial re-export.

### AUDIT-141 — EventBus.publish() async handler'ları çıplak `asyncio.create_task` ile çağırıyor: loop yoksa yutulur, referans tutulmaz (GC), coroutine içi exception try/except dışında → DLQ'ya hiç düşmez
- Şiddet: medium
- Sınıf: reliability
- Konum: event_bus.py:216-225
- Durum: confirmed
- Kanıt:
    ```python
    for cb in callbacks:
        try:
            if inspect.iscoroutinefunction(cb):
                asyncio.create_task(cb(event))   # (1) loop yoksa RuntimeError (2) ref yok→GC
            else:
                cb(event)
        except Exception as exc:                 # SADECE create_task çağrısını sarar,
            self._handle_failure(event, cb.__name__, str(exc))  # coroutine'in KENDİ hatasını DEĞİL
    ```
  (1) `publish()` senkron context'ten (çalışan loop yok) çağrılırsa `asyncio.create_task` `RuntimeError: no
  running event loop` atar → except onu DLQ'ya yazar (handler hiç çalışmadı). (2) Task referansı saklanmadığı
  için CPython task'ı çalışırken çöp toplayabilir. (3) En önemlisi: try/except yalnız `create_task` **çağrısını**
  sarıyor; başlatılan coroutine içinde oluşan exception buraya gelmez → async handler hataları sessizce
  kaybolur, DLQ'ya **asla** yazılmaz. Sync handler'larda (else dalı) hata yakalanıp DLQ'ya gider — asimetri.
- Önerilen düzeltme: async publish için `publish_async`'i kullan; sync `publish`'te async handler varsa task
  referansını sakla + `add_done_callback` ile exception'ı `_handle_failure`'a yönlendir; loop yoksa açık logla.
- Bağımlılık: AUDIT-130 (aynı create_task GC tuzağı), AUDIT-142.

### AUDIT-142 — Outbox relay handler hatasında bile event'i processed=True işaretliyor (publish_async handler exception'ını yutar) + DLQ asla yeniden işlenmez → "reliable delivery" garantisi kırık
- Şiddet: high
- Sınıf: reliability
- Konum: outbox_service.py:98-103 + event_bus.py:236-245
- Durum: confirmed
- Kanıt:
    ```python
    # event_bus.publish_async — handler exception YAKALANIR, RE-RAISE EDİLMEZ:
    except Exception as exc:
        self._handle_failure(event, cb.__name__, str(exc))    # DLQ'ya yaz, ama yukarı fırlatma
    # outbox.relay_pending_events:
    await bus.publish_async(event)        # handler patlasa bile normal döner
    db_event.processed = True             # → işlenmiş say
    db_event.processed_at = ...
    ```
  `publish_async` handler exception'larını yutup DLQ'ya yazar ama **re-raise etmez**; dolayısıyla outbox relay
  `await bus.publish_async(event)`'ten normal döner ve event'i `processed=True` işaretler — bir abone (cache
  invalidation, RAG sync, ML retrain tetik) başarısız olsa dahi. retry_count yalnız publish_async'in kendisi
  (validation/EventType hatası) fırlatırsa artar. DLQ (bellek listesi + Redis list) hiçbir yerde otomatik
  yeniden işlenmiyor. Sonuç: transactional-outbox'ın tüm amacı (en-az-bir-kez handler teslimi) handler-tarafı
  yan etkiler için sağlanmıyor; başarısız yan etkiler sessizce kalıcı kayıp.
- Önerilen düzeltme: publish_async başarısız handler sayısını dönsün/raise etsin; relay yalnız tüm kritik
  handler'lar başarılıysa processed=True yapsın (yoksa retry_count++). DLQ için periyodik yeniden-işleme job'u ekle.
- Bağımlılık: AUDIT-141, relay-outbox-events-every-60s (celery beat).

### AUDIT-143 — bellek-fallback dedup eviction'ı `list(set)[-500:]` ile rastgele 500 tutuyor (set sırasız), en-yeni değil
- Şiddet: low
- Sınıf: bug
- Konum: event_bus.py:160-163
- Durum: confirmed
- Kanıt:
    ```python
    self._processed_events.add(event_id)
    if len(self._processed_events) > self._max_processed_cache:
        self._processed_events = set(list(self._processed_events)[-500:])  # set sırasız!
    ```
  Python set'i ekleme sırasını korumaz; `list(set)[-500:]` "son 500" değil **rastgele 500** tutar → yakın
  zamanda işlenmiş event_id'ler atılıp eskiler kalabilir → bellek-fallback modunda yeni event'ler yanlışlıkla
  duplicate sayılabilir veya gerçek duplicate'ler kaçabilir. Redis birincil yol olduğunda etki sınırlı.
- Önerilen düzeltme: `collections.OrderedDict`/`deque` ya da insertion-ordered bir yapı kullan; FIFO evict.
- Bağımlılık: yok.

### AUDIT-144 — `log_audit_event` old/new_value'yu yalnız `_mask_sensitive_data` ile maskeliyor (telefon/tc_no/email/adres KAPSANMIYOR) → PII admin_audit_log'a maskesiz yazılıyor
- Şiddet: medium
- Sınıf: security
- Konum: audit_logger.py:143-165,285-313 (pii_scrubber.py:5-25 ile karşılaştır)
- Durum: confirmed
- Kanıt:
    ```python
    # audit_logger._mask_sensitive_data sensitive_keys:
    {"password","token","api_key","secret","credit_card","sifre","auth"}   # PII alanı YOK
    # log_audit_event:
    masked_new = _mask_sensitive_data(new_value) if new_value else None     # scrub_pii ÇAĞRILMIYOR
    await _persist_audit_to_db(..., new_value=masked_new, ...)              # DB'ye yazılır
    ```
  `pii_scrubber.SENSITIVE_KEYS` telefon/phone/tc_no/tckn/email/adres'i kapsarken `audit_logger`'ın kendi
  `_mask_sensitive_data` seti yalnız kimlik-bilgisi anahtarlarını maskeler. `log_audit_event` (endpoint'lerin
  entity değişikliklerini denetlerken kullandığı imperative helper) old/new_value'ya yalnız bunu uygular →
  bir kullanıcı/şoför kaydı denetlenirken telefon/TCKN/email/adres `admin_audit_log` tablosuna **maskesiz**
  düşer (PII-at-rest). Decorator'ın `log_params` yolu scrub_pii+mask ikisini de uyguluyor; bu helper uygulamıyor.
- Önerilen düzeltme: `log_audit_event`'te old/new_value'ya `scrub_pii` de uygula (decorator gibi
  `_mask_sensitive_data(scrub_pii(value))`); ideali tek ortak maskeleme fonksiyonuna indir.
- Bağımlılık: AUDIT-121, AUDIT-122, AUDIT-127 (PII ailesi), AUDIT-137 (pii_scrubber regex).

### AUDIT-145 — Outbox poison event'leri (retry_count>=5) sonsuza dek processed=False kalır; temizlik/DLQ yok → tablo şişer, sessiz birikim
- Şiddet: low
- Sınıf: reliability
- Konum: outbox_service.py:62-67,105-108
- Durum: confirmed
- Kanıt:
    ```python
    .where(OutboxEvent.processed.is_(False), OutboxEvent.retry_count < 5)
    ...
    except Exception as e:
        db_event.retry_count += 1; db_event.error_message = str(e)
    ```
  Geçersiz `EventType` (enum drift / eski event) veya kalıcı hata 5 denemede retry_count=5'e ulaşır; sorgu
  filtresi bunları artık seçmez → `processed=False, retry_count=5` satırlar tabloda sonsuza dek kalır, ne
  işlenir ne temizlenir ne DLQ'ya taşınır. Zamanla outbox tablosu poison satırlarla şişer; operasyonel
  görünürlük yok.
- Önerilen düzeltme: retry tükenince ayrı bir `processed='dead'`/DLQ tablosuna taşı + metrik/uyarı; periyodik
  temizlik job'u.
- Bağımlılık: AUDIT-142 (DLQ yeniden-işleme), event_types enum genişlemeleri.

## S5-3 — cache(5): redis_cache + redis_pubsub + cache_manager + cache_invalidation + __init__ — 5 bulgu

Temiz yönler: tüm cache backend'lerinde key validation (uzunluk + char pattern + `../` traversal guard);
`cache_manager.delete_pattern/clear` SCAN-tabanlı + `cm:` namespace izole (flushdb DEĞİL); pubsub SSL
default full-verify (insecure yalnız env ile); stat sayaçları thread-safe. `cache_invalidation` event→cache
temizleme eşlemeleri makul. __init__ trivial.

### AUDIT-146 — RedisCache.clear_all() `flushdb()` çağırıyor → TÜM Redis DB'sini siler (token blacklist, rate-limit, outbox dedup, celery), yalnız cache'i değil
- Şiddet: medium
- Sınıf: security
- Konum: redis_cache.py:211-222
- Durum: needs-verification
- Kanıt:
    ```python
    def clear_all(self):
        if self._redis_client:
            self._redis_client.flushdb()   # TÜM DB — namespace yok
    ```
  `cache_manager.clear()` `cm:*` namespace'iyle sınırlı SCAN yaparken `RedisCache.clear_all` `flushdb()` ile
  bağlı Redis DB'sindeki HER anahtarı siler. Aynı DB index'i token_blacklist (`blacklist:*`), rate-limit
  (`rl:*`), event dedup (`events:processed:*`), outbox DLQ ve (CELERY_BROKER_URL aynı DB ise) Celery kuyruğu
  paylaşıyorsa, bir "cache temizle" işlemi auth blacklist + rate-limit + kuyruk durumunu da uçurur. Cache'in
  ayrı bir DB index'inde olup olmadığı doğrulanmalı; admin endpoint'inin clear_all'ı çağırıp çağırmadığı.
- Önerilen düzeltme: `flushdb` yerine namespace'li SCAN-delete (cache_manager.clear gibi) kullan; cache'i
  ayrı Redis DB index'ine al.
- Bağımlılık: token_blacklist (136), rate_limit (138/139), event_bus dedup, celery_app (S5).

### AUDIT-147 — `cached` decorator key'i `{args!s}` içeriyor (self/obje repr'i bellek adresi taşır) + `json.dumps(default=str)` round-trip tip kaybı
- Şiddet: medium
- Sınıf: bug
- Konum: redis_cache.py:265-302,184,156-158
- Durum: confirmed
- Kanıt:
    ```python
    key_data = f"{func.__name__}:{args!s}:{kwargs!s}"   # method'ta args[0]=self → "<X object at 0x..>"
    key = cache._generate_key(key_data, prefix)
    ...
    serialized = json.dumps(value, ensure_ascii=False, default=str)   # datetime/Decimal → str
    ```
  (1) Decorator method'a uygulanırsa `args!s` `self`'in default repr'ini (bellek adresi) içerir → key her
  instance/process'te farklı → method'lar için cache hiç hit etmez (method kullanımı verify gerek). (2)
  `set` `json.dumps(default=str)` ile datetime/Decimal/ORM'i string'e çevirir; `get` `json.loads` ile geri
  döner → cache-miss'te gerçek tip, cache-hit'te string/dict döner → tip drift'i (çağıran datetime beklerken
  str alır). Ayrıca `get`'te `if cached:` falsy değerleri (0/""/[]) miss sayar → falsy sonuçlar hiç cache'lenmez.
- Önerilen düzeltme: key'i deterministik argümanlardan üret (self hariç, named args sıralı); değerleri tip-
  korumalı serialize et (pickle yerine tip-bilgili JSON şeması) veya decorator'ı yalnız JSON-native dönüşlü
  saf fonksiyonlara sınırla; miss'i `is None` ile ayırt et (zaten decorator öyle yapıyor, `get` da yapmalı).
- Bağımlılık: AUDIT-150 (serialization), AUDIT-148.

### AUDIT-148 — Senkron (bloklayan) Redis I/O async context içinde: async `cached` wrapper + `cache_invalidation` event handler'ları event loop'u bloklar
- Şiddet: medium
- Sınıf: performance
- Konum: redis_cache.py:274-285 (async wrapper sync get/set) + cache_invalidation.py:34-116 (async handler→sync delete_pattern/clear)
- Durum: confirmed
- Kanıt:
    ```python
    async def wrapper(*args, **kwargs):
        cached_result = cache.get(key)        # senkron, bloklayan redis-py I/O
        ...
        cache.set(key, result, ttl)           # senkron
    # cache_invalidation:
    async def on_sefer_change(event):
        cache.delete_pattern("stats:*")       # senkron SCAN döngüsü, async handler içinde
        cache.delete_pattern("report:*"); ... # 4 ardışık bloklayan SCAN
    ```
  `RedisCache`/`CacheManager` senkron redis-py kullanır; bunlar async `cached` wrapper'ında ve async cache-
  invalidation handler'larında doğrudan çağrılıyor → her cache op event loop'u Redis I/O süresince (socket_
  timeout=2s'e kadar) bloklar; `on_sefer_change` 4 ardışık SCAN döngüsü çalıştırır. AUDIT-063/126/130 ailesi.
- Önerilen düzeltme: async context'te async client (`redis.asyncio`, pubsub_manager) kullan ya da
  `asyncio.to_thread` ile sar.
- Bağımlılık: AUDIT-063, AUDIT-126, AUDIT-141 (handler'lar event_bus üzerinden).

### AUDIT-149 — RedisPubSubManager bellek-fallback `set`/`incr` `expire`'ı yok sayıyor (TTL yok) + thread-unsafe singleton
- Şiddet: low
- Sınıf: bug
- Konum: redis_pubsub.py:27-31,145-158,187-198
- Durum: confirmed
- Kanıt:
    ```python
    def __new__(cls):
        if cls._instance is None:            # RedisCache'teki gibi lock YOK
            cls._instance = super().__new__(cls); cls._instance._initialized = False
    async def set(self, key, value, expire=None):
        ...
        self._memory_store[key] = payload     # expire YOK SAYILIR (yorum kabul ediyor)
    ```
  Memory-fallback modunda `set`/`incr` TTL uygulamaz → `_memory_store` sınırsız büyür + semantik drift:
  `set_redis_val(blacklist..., expire=ttl)` bellek modunda hiç dolmaz (token kalıcı blacklist; fail-secure
  yönde ama yanlış), sayaçlar resetlenmez. `__new__` lock'suz → to_thread worker'larından ilk-erişimde çoklu
  instance riski (RedisCache'in double-checked lock'una karşı asimetri).
- Önerilen düzeltme: bellek store için TTL'li bir yapı (timestamp + lazy-expire) kullan; `__new__`'a
  RedisCache'teki gibi `threading.Lock` ekle.
- Bağımlılık: AUDIT-136 (blacklist set_redis_val), AUDIT-139 (rate-limit).

### AUDIT-150 — CacheManager değerleri `pickle.dumps/loads` ile saklıyor → Redis yazılabilir/paylaşılırsa pickle-deserialization RCE yüzeyi
- Şiddet: medium
- Sınıf: security
- Konum: cache_manager.py:67,80
- Durum: needs-verification
- Kanıt:
    ```python
    self._redis.psetex(f"{_KEY_PREFIX}{key}", ttl_ms, pickle.dumps(value))
    ...
    return pickle.loads(cast("bytes", raw))  # noqa: S301   # güvenmeyen veride RCE
    ```
  `cm:` namespace değerleri pickle ile serialize ediliyor; `get` Redis'ten gelen byte'ları `pickle.loads`
  eder. Redis'e yazabilen biri (paylaşılan/zayıf-korumalı Redis, başka servis, container ağı sızıntısı)
  zararlı pickle payload'ı yerleştirip o anahtar okunduğunda backend'de **keyfi kod çalıştırabilir**. `noqa:
  S301` riski kabul ediyor ama azaltma yok. Redis ağ-izolasyonu doğrulanmalı; izole olsa bile defense-in-depth
  için pickle bırakılmalı.
- Önerilen düzeltme: JSON/msgpack ile değiştir (RedisCache zaten JSON kullanıyor — tutarsızlık); pickle
  zorunluysa HMAC-imzalı payload + yalnız güvenilir yazıcı.
- Bağımlılık: AUDIT-147 (RedisCache JSON kullanıyor — serialization tutarsızlığı), AUDIT-146.

## S5-4 — resilience(6) + background(2) — 4 bulgu

Temiz/örnek: `retry.with_async_retry` (expo backoff, 4xx instant-fail, retryable set net); `shutdown`
(SIGTERM/SIGINT flag, non-main-thread no-op); `circuit_breaker` Redis-distributed + sync/async + registry;
`celery_app` (acks_late + visibility_timeout=120 > time_limit=90 hizalı, prefetch=1, worker fork sonrası
engine.dispose, kapsamlı beat schedule). __init__ trivial. İz: `rate_limiter` AsyncRateLimiter süreç-içi
(çok-worker'da efektif limit = rate×worker, dış-API nezaket limiti — low).

### AUDIT-151 — CircuitBreaker HALF_OPEN'da tek-probe kapısı yok: lock func çağrısından önce bırakılıyor → iyileşen servise eşzamanlı probe sürüsü
- Şiddet: medium
- Sınıf: reliability
- Konum: circuit_breaker.py:104-131,248-268
- Durum: confirmed
- Kanıt:
    ```python
    async with self._async_lock:
        ...; current_state = self.state
        if current_state == CircuitState.HALF_OPEN:
            logger.info(...)            # sadece logla, sayaç/kapı YOK
    # lock BURADA bırakılır
    try:
        result = await func(*args, **kwargs)   # tüm eşzamanlı HALF_OPEN istekleri buraya girer
    ```
  HALF_OPEN'da klasik CB yalnız **tek** deneme isteğine izin verir; burada lock `func` çağrısından önce
  bırakıldığı ve HALF_OPEN için bir "probe alındı" işareti olmadığı için, reset_timeout dolduğu anda gelen
  TÜM eşzamanlı istekler HALF_OPEN görüp aynı anda alt-servise gider → henüz iyileşmemiş servise sürü
  (thundering herd), CB'nin koruma amacını zayıflatır.
- Önerilen düzeltme: HALF_OPEN'da Redis'te atomik bir "probe token" (SET NX) al; yalnız token'ı alan istek
  geçsin, diğerleri OPEN gibi reddedilsin/fallback'e düşsün.
- Bağımlılık: AUDIT-132 (route_service CB yok), external_service CB.

### AUDIT-152 — BackgroundJobManager durumu süreç-içi bellekte → çok-worker'da status poll "unknown", restart'ta iş kaybı, cleanup zamanlanmazsa bellek sızıntısı
- Şiddet: medium
- Sınıf: reliability
- Konum: job_manager.py:28-70,88-116
- Durum: needs-verification
- Kanıt:
    ```python
    cls._instance._results: Dict[str, Any] = {}   # süreç-yerel dict'ler
    ...
    self._tasks[job_id] = asyncio.create_task(_wrapper())   # ref tutuluyor (iyi, AUDIT-130 değil)
    ```
  Job durumu/sonucu süreç-yerel dict'lerde. CLAUDE.md'deki "202 + `GET /trips/tasks/{id}/status` poll"
  deseni: (a) backend birden çok uvicorn/gunicorn worker'ı ile koşuyorsa job worker-A'da, poll worker-B'ye
  düşerse status `unknown` → frontend işi kayıp sanır; (b) restart'ta tüm in-flight job'lar kaybolur, poll
  sonsuza dek `unknown`; (c) `cleanup()` bir yerde zamanlanmadıysa completed/failed kayıtları + result
  dict'leri sonsuza dek birikir → bellek sızıntısı. Worker sayısı + cleanup zamanlaması doğrulanmalı.
- Önerilen düzeltme: job durumunu Redis/DB'de tut (worker-agnostik); cleanup'ı periyodik task'a bağla;
  ya da bu pattern'i Celery result backend'e taşı.
- Bağımlılık: cost-analysis/import async pattern (trips endpoint), celery result backend.

### AUDIT-153 — IdempotencyGuard get-sonra-set atomik değil (TOCTOU) → eşzamanlı tekrar istekler ikisi de geçer; başarısız istek key'i 5 dk "processing" kilitler
- Şiddet: medium
- Sınıf: concurrency
- Konum: idempotency.py:48-57
- Durum: confirmed
- Kanıt:
    ```python
    existing = await redis.get(cache_key)
    if existing: raise HTTPException(409, ...)
    await redis.set(cache_key, "processing", expire=IDEMPOTENCY_TTL)   # get ile set arası yarış
    ```
  İki eşzamanlı istek (aynı X-Idempotency-Key) ikisi de `get`'te None görüp `set`'ten önce devam eder →
  idempotency tam da önlemesi gereken çift-işlemeye izin verir; atomik `SET key val NX EX=ttl` kullanılmalı.
  Ayrıca handler başarısız olursa key "processing" olarak 5 dk kalır (completed/sil yok) → kullanıcının
  meşru retry'ı 5 dk boyunca 409 alır. Docstring "önceki response'u döner" diyor ama response saklanmıyor
  (sadece 409 ile bloklar) — davranış/doküman uyumsuzluğu.
- Önerilen düzeltme: `SET NX EX` ile atomik al; başarıda response'u kısa TTL ile sakla ve dön; başarısızlıkta
  key'i sil (retry serbest kalsın).
- Bağımlılık: redis_pubsub.set (AUDIT-149 memory-fallback TTL yok → bellek modunda idempotency hiç dolmaz).

### AUDIT-154 — Celery global task_time_limit=90s ağır beat task'larını (weekly retrain-all, backfill) kesebilir → sessiz kısmi tamamlanma
- Şiddet: low
- Sınıf: reliability
- Konum: celery_app.py:29-30,71-80
- Durum: needs-verification
- Kanıt:
    ```python
    task_soft_time_limit=70, task_time_limit=90,
    ...
    "ml-weekly-retrain-all-vehicles": {... crontab(sun 03:00)},
    "prediction-backfill-missing-nightly": {... crontab(01:00)},
    ```
  Global hard limit 90s. `ml.weekly_retrain_all_vehicles` / `prediction.backfill_missing` tüm filoyu inline
  işliyorsa 90s'te SIGKILL → haftalık retrain/backfill sessizce yarım kalır. Sub-task'lara fan-out ediyorsa
  sorun yok. Task gövdeleri (app/workers/tasks/) okunduğunda doğrulanmalı.
- Önerilen düzeltme: ağır task'lara per-task `time_limit` override ver veya per-entity sub-task'lara fan-out et.
- Bağımlılık: app/workers/tasks/* (S5 devam), prediction_backfill (AUDIT carry).

## S5-5 — routing(3) + elevation(2) — 2 bulgu

Temiz/örnek: `open_meteo_client` (batch+dedup+Redis cache 30g, 429 Retry-After tek retry, with_async_retry
3x, non-200'de silent_fallback_probe kaydı, miss→None FABRİKASYON YOK); `mapbox_client` (intersections'tan
road_class reconcile, segment extraction, 24h cache, retry, SecretStr→plain key fix); `openroute_client`
DÜRÜST degradasyon (CB-open/hata→None, AUDIT-067 fabrikasyonu orkestrasyon katmanındaydı bu client'ta değil).
İz (low): mapbox `get_route` retry+cache'siz (get_segments'te ikisi de var — asimetri); her çağrı yeni
httpx client (pool yok); openroute paylaşılan `self._client` hiç kapanmıyor; Türkiye-sınır validasyonu sınır
geçişlerini reddedebilir; `_rate_limit_lock` lazy-init TOCTOU. Tümü low/ihmal edilebilir.

### AUDIT-155 — API anahtarları URL query param'ında: Mapbox `access_token` + ORS geocode `api_key` → monitored-client/exception/access log sızıntı riski
- Şiddet: low
- Sınıf: security
- Konum: mapbox_client.py:90,499 + openroute_client.py:174
- Durum: needs-verification
- Kanıt:
    ```python
    # mapbox_client get_route / _fetch_segments
    params = {"access_token": self.api_key, ...}            # URL query
    # openroute_client _call_geocode_api
    params = {"api_key": self.api_key, "text": text, ...}    # URL query (directions ise Authorization header)
    ```
  Mapbox token ve ORS geocode anahtarı URL query string'inde gidiyor. `get_monitored_client` istek URL'ini
  loglar/probe ederse veya `logger.exception` httpx request URL'ini içerirse anahtar log'lara sızar. ORS
  directions `Authorization` header kullanıyor (doğru) ama geocode query param — tutarsız. logging_middleware
  `token|key|api_key` query maskesi uyguluyor ama bu yalnız uygulama-katmanı access log'unu kapsar;
  external_api_probe/exception yolları doğrulanmalı.
- Önerilen düzeltme: mümkün olan her yerde anahtarı header'a taşı (ORS geocode `Authorization`); monitored
  client'ın URL log'unda query string'i maskele.
- Bağımlılık: external_api_probe (S5 monitoring), logging_middleware (AUDIT yok, query mask var).

### AUDIT-156 — openroute_client `_save_to_cache` yalnız mevcut lokasyonlar satırını UPDATE eder (yeni koord için INSERT yok) → ad-hoc rotalar hiç cache'lenmez, her seferinde ORS API + kota yakımı; lookup ABS() seq-scan
- Şiddet: medium
- Sınıf: performance
- Konum: openroute_client.py:393-453,337-391
- Durum: confirmed
- Kanıt:
    ```python
    if existing:
        await session.execute(text("UPDATE lokasyonlar SET ... WHERE id = :id"), ...)
    else:
        logger.debug("Yeni güzergah için cache kaydedilecek (güzergah henüz yok)")   # INSERT YOK
    # lookup:
    WHERE ABS(cikis_lat - :lat1) < :tol AND ABS(cikis_lon - :lon1) < :tol ...          # index kullanılamaz
    ```
  `get_distance` cache→API→save akışında `_save_to_cache` yalnız önceden kayıtlı bir `lokasyonlar` satırı
  varsa UPDATE eder; eşleşen satır yoksa INSERT etmeyip sadece debug log atar → kayıtlı güzergah dışındaki
  her (origin,dest) çifti **hiç cache'lenmez**, tekrarlayan aynı sorgu her defasında ORS API'ye gider (free
  tier kota + latency). Ayrıca cache lookup `ABS(col - :v) < tol` ile index kullanamayan tam tarama yapar →
  lokasyonlar büyüdükçe yavaşlar.
- Önerilen düzeltme: eşleşme yoksa ayrı bir route-cache tablosuna (ya da CacheManager Redis'ine) INSERT et;
  koordinatları grid-quantize edip indexlenebilir bir anahtara çevir.
- Bağımlılık: route_service cache (route_repo farklı yol kullanıyor — tutarsızlık), lokasyon tablosu.

## S5-6 — logging(2) + notifications(2) + database(1) + metrics + infra/__init__ — 1 bulgu

Temiz/örnek: `logger.py` (PIIFilter scrub_pii + log-injection \n/\r sanitize, JSONFormatter correlation_id,
rotating 10MB×7, ayrı audit.log×30); `metrics.py` (prometheus graceful no-op); `logging/audit_logger.py`
(canonical audit shim); `telegram_notifier` (3 retry + Redis sync_fallback; çağrı yerleri arka-plan: celery
digest task + alarm_router — request path'te inline-await YOK, latency endişesi gerçekleşmiyor → düşürüldü).
İz: `infrastructure/__init__` import'unda cache_manager(Redis)+event_bus init yan etkisi (low); logger
scrub_pii AUDIT-137 TCKN/telefon sıra hatasını miras alır (cross-ref).

### AUDIT-157 — DatabaseBackupManager şifrelenmemiş düz-metin `.sql` dump üretir (tüm PII içerir); cleanup `.sqlite3` yedeklerini atlar
- Şiddet: low
- Sınıf: security
- Konum: backup_manager.py:57-84,92-109
- Durum: needs-verification
- Kanıt:
    ```python
    cmd = ["pg_dump", ..., "-F", "p",  # Plain text format
           "-f", filepath, self.db_name]              # storage/backups/*.sql, şifresiz
    ...
    for filename in os.listdir(self.backup_dir):
        if not filename.endswith(".sql"): continue     # .sqlite3 yedekleri hiç silinmez
    ```
  pg_dump düz-metin (`-F p`) `.sql` dosyası üretiyor: tüm tablo verisi (kullanıcı telefon/tc_no/email/adres,
  parola hash'leri, audit) `storage/backups/` altında **şifresiz** durur. Dizin erişim-kontrolü/volume
  şifrelemesi yoksa tam veri sızıntısı (PII-at-rest). Ayrıca `cleanup_old_backups` yalnız `.sql` uzantısını
  süzer → SQLite modunda üretilen `.sqlite3` yedekleri retention dışı kalır, sınırsız birikir. Komut list-arg
  (shell yok) → injection yok; PGPASSWORD env ile (ps'te görünmez) — bunlar iyi.
- Önerilen düzeltme: dump'ı şifrele (gpg/age) veya şifreli volume'da tut + erişim kısıtla; cleanup'ı tüm
  yedek uzantılarını (`.sql`,`.sqlite3`) kapsayacak şekilde genişlet.
- Bağımlılık: volume/secret yönetimi (S7 docker), PII ailesi (122/127/144).

## S5-7 — monitoring(12) — 2 bulgu — S5 INFRA TAMAM

Yüksek-kalite gözlemlenebilirlik altsistemi. Örnek: `db_probe` (PG-code map, N+1/slow-query/pool probe,
güvenli-gated auto-EXPLAIN ANALYZE-FALSE, doğru bg-task ref); `alarm_router` (Z-score anomali, dedup,
**doğru** _bg_tasks create_task pattern — AUDIT-130/141 hatası YOK, Sentry feedback-loop guard);
`external_api_probe` (`_sanitize_url` query'yi siler → AUDIT-155 probe yolunu azaltır, object-id timing);
`security_probe`/`service_probe`/`celery_probe`/`silent_fallback_probe`/`ml_probe` LRU/Counter-bounded,
DomainError skip, intentional_fallback ayrımı; `event_bus` (ErrorEventBus) bulk-insert + ON CONFLICT +
partition + circuit-breaker + Redis fallback. `models`/`activate`/`__init__` temiz.

### AUDIT-158 — BruteForceDetector `request.client.host`'a dayanıyor + docker-bridge prefix'lerini güveniyor → reverse proxy ardında brute-force tespiti tamamen devre dışı
- Şiddet: medium
- Sınıf: security
- Konum: security_probe.py:23-36,45-50 + logging_middleware.py:88-89
- Durum: needs-verification
- Kanıt:
    ```python
    _TRUSTED_BRUTE_FORCE_PREFIXES = ("127.","::1","172.17.","172.18.","172.19.","172.20.")
    def record(self, ip, status_code):
        if _is_trusted_local_ip(ip): return    # docker-bridge IP'leri brute-force tetiklemez
    # logging_middleware:
    client_ip = request.client.host           # proxy ardında = PROXY IP (172.x docker bridge)
    get_brute_force_detector().record(client_ip, response.status_code)
    ```
  Brute-force detektörü IP'yi `request.client.host`'tan alıyor (XFF değil); tipik docker dağıtımında
  (nginx/traefik → backend 172.x bridge) bu, gerçek istemcinin değil **proxy'nin** IP'sidir ve 172.17-20
  güvenilir-prefix listesindedir → tüm 401'ler güvenilir-yerel sayılıp `record()` erkenden döner → brute-force
  production'da hiç tespit edilmez. Üstelik AUDIT-138 (login rate-limit yok) ile birleşince login'e karşı tek
  savunma katmanı da etkisiz. Dağıtım topolojisi (proxy + XFF) doğrulanmalı.
- Önerilen düzeltme: gerçek istemci IP'sini güvenilir-proxy-aware XFF çözümünden al (AUDIT-139 ile aynı
  çözüm); docker-bridge trust'ı yalnız XFF yoksa uygula.
- Bağımlılık: AUDIT-138, AUDIT-139 (XFF güveni), logging_middleware client_ip.

### AUDIT-159 — ErrorEventBus batch dedup'ı severity'yi STRING değeriyle karşılaştırıyor → "critical" alfabetik en küçük → batch'te warning/error'a yenilir, severity düşer
- Şiddet: medium
- Sınıf: bug
- Konum: event_bus.py:216-226 + models.py:22-26
- Durum: confirmed
- Kanıt:
    ```python
    # ErrorSeverity: CRITICAL="critical", ERROR="error", WARNING="warning", INFO="info"
    if ev.severity.value > existing.severity.value:   # STRING karşılaştırma
        aggregated[ev.fingerprint] = ev               # "warning">"critical" (w>c) → True
    ```
  `severity.value` string'leri leksikografik sıralanır: "critical"(c) < "error"(e) < "info"(i) < "warning"(w).
  Dolayısıyla batch'te aynı fingerprint için critical + warning varsa, "en yüksek" diye **warning** seçilir
  (kritik temsilci kaybolur). Bulk INSERT yeni bir fingerprint için bu seçilen ev'in severity'siyle satır
  yazar → kritik bir olay **warning** olarak kalıcılaşabilir; ON CONFLICT CASE yalnız `EXCLUDED.severity =
  'critical'` ise yükseltir, seçilen warning olduğundan o da devreye girmez. message/metadata da yanlış
  ev'den alınır.
- Önerilen düzeltme: severity'yi açık bir rank haritasıyla karşılaştır
  (`{critical:3,error:2,warning:1,info:0}`), string ile değil.
- Bağımlılık: models.ErrorSeverity, alarm_router severity routing.

> **S5 INFRA TAMAMLANDI: 54 dosya (security/middleware/context/events/audit/cache/resilience/background/
> routing/elevation/logging/notifications/database/metrics/monitoring). Bulgular AUDIT-136..159 (24 bulgu,
> high 1=AUDIT-142). Gözlemlenebilirlik + audit + retry/CB altsistemleri yüksek kalitede; ana temalar:
> session'sız singleton, sync-in-async Redis, PII maskeleme boşlukları, çok-worker bellek-yerel durum.**

## S5-8 — workers/tasks(15) — 3 bulgu — S5 TAMAM

Temiz/örnek: `error_digest` (5dk digest + sync_fallback drain + materialized view refresh + db_health_check
long-tx/lock-wait/bloat); `coaching_tasks` (özel soft_time_limit=3600/hard=3900 → AUDIT-154 deseni doğru
çözülmüş, SoftTimeLimitExceeded partial; html.escape Telegram); `theft_tasks` (KVKK: yalnız ID loglar, PII
yok); `outbox_tasks` (engine.dispose + asyncio.run — DOĞRU fork deseni); `notification/driver/analytics/
anomaly_cluster/compliance` new-loop + finally close (doğru). **AUDIT-154 güncelleme:** backfill limit=50
bounded, coaching özel limitli → 90s sorunu yalnız `core/ml/training/scheduler_task` retrain'i için
geçerli olabilir (S4 dışı; doğrulanmalı).

### AUDIT-160 — Celery task'larında tutarsız event-loop/engine yönetimi: prediction_tasks loop'u kapatmıyor (sızıntı) + çoğu task asyncio.run/new-loop'u engine.dispose'suz çağırıyor (fork-inherited pool cross-loop riski)
- Şiddet: medium
- Sınıf: reliability
- Konum: prediction_tasks.py:28-29 (close yok) vs outbox_tasks.py:36-39 (dispose var) vs error_digest.py:244-254 (defansif catch)
- Durum: confirmed
- Kanıt:
    ```python
    # prediction_tasks: loop yaratılır, ASLA kapatılmaz (backfill/coaching finally:loop.close() yapar)
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    ...  # finally: loop.close() YOK → her invoke'ta loop+self-pipe fd sızıntısı
    # outbox_tasks (DOĞRU): engine.sync_engine.dispose(); asyncio.run(...)
    # db_health_check (KANIT): except RuntimeError if "different loop" in str(e): skip  ← takım bu hatayı yaşamış
    ```
  prediction_tasks `new_event_loop()` yaratıp hiç `close()` etmiyor → her tahmin task'ında event loop + self-pipe
  fd sızıntısı. Daha genel: outbox_tasks fork-inherited asyncpg pool sorununu `engine.dispose()` ile çözerken,
  db_health_check aynı hatayı (`"different loop"`) defansif yakalarken, prediction/error_digest/coaching/ocr ve
  diğer beat task'ları ne dispose ne guard yapıyor → tekrarlayan invoke'larda kapalı-loop'a bağlı pooled
  connection cross-loop hatası riski (async engine pool'u NullPool değilse). db_health_check'in açık catch'i
  takımın bu hatayı yaşadığının kanıtı.
- Önerilen düzeltme: tüm task'ları tek ortak helper'a indir (engine.dispose() + asyncio.run() + loop close);
  prediction_tasks'a `finally: loop.close()` ekle; async engine pool'unu doğrula (NullPool ise dispose gereksiz).
- Bağımlılık: celery_app init_worker dispose (tek seferlik), database/connection pool config.

### AUDIT-161 — drain_prediction_dlq DLQ girdilerini siler + yalnız loglar; `requeue=True` no-op → başarısız tahminler tek log sonrası kalıcı kayıp
- Şiddet: low
- Sınıf: reliability
- Konum: dlq_tasks.py:20-45
- Durum: confirmed
- Kanıt:
    ```python
    raw = r.rpop("pred:dlq")        # kuyruktan KALDIRIR
    logger.error("[DLQ] prediction task failed: %s", payload)
    if requeue and "task_id" in payload:
        pass                         # NO-OP — gerçek requeue yok
    ```
  `drain-prediction-dlq-every-60s` beat task'ı pred:dlq'yu `rpop` ile boşaltıp her girdiyi yalnız loglar;
  `requeue=True` bayrağı hiçbir şey yapmaz (yorum kabul ediyor). Başarısız tahminler tek log satırından
  sonra kalıcı kaybolur, yeniden işlenmez (AUDIT-142 DLQ-replay-yok ailesi).
- Önerilen düzeltme: requeue'yu gerçekten uygula (task'ı yeniden gönder) veya kalıcı bir dead-letter
  tablosuna taşı + metrik.
- Bağımlılık: AUDIT-142, prediction_tasks pred:dlq lpush.

### AUDIT-162 — ocr_tasks `ocr_durumu="hata"` set edip `raise self.retry()` → UoW rollback ile durum geri alınır; kalıcı OCR başarısızlığı terminal "hata" durumunu hiç yazmaz
- Şiddet: low
- Sınıf: bug
- Konum: ocr_tasks.py:44-46,59-63
- Durum: confirmed
- Kanıt:
    ```python
    except OSError as exc:
        belge.ocr_durumu = "hata"        # UoW içinde set
        raise self.retry(exc=exc)        # exception → UoW __aexit__ ROLLBACK → set geri alınır
    ...
    except Exception as exc:
        belge.ocr_durumu = "hata"; raise self.retry(exc=exc)   # aynı
    ```
  `ocr_durumu="hata"` UoW transaction'ı içinde set edilip hemen `self.retry()` (Retry exception) raise ediliyor;
  UoW `__aexit__` exception'da rollback yaptığı için durum değişikliği persist edilmez. Max retry tükenince
  task kalıcı fail eder ama belge `ocr_durumu` terminal "hata"ya hiç geçmez → belgeler işleniyor/beklemede
  durumunda asılı kalır, operasyon görünürlüğü yok.
- Önerilen düzeltme: durum güncellemesini ayrı bir transaction/commit'te yap (retry'dan önce) ya da
  Celery `on_failure` handler'ında terminal "hata"yı yaz.
- Bağımlılık: UnitOfWork rollback semantiği, celery retry.

> **S5 TAMAMLANDI: infrastructure (54) + workers/tasks (15) = 69 dosya. Bulgular AUDIT-136..162 (27 bulgu,
> high 1=AUDIT-142). Gözlemlenebilirlik/audit/retry altsistemleri örnek kalitede; tekrar eden temalar:
> sync-in-async Redis, çok-worker/loop-bellek durumu, PII maskeleme boşlukları, DLQ-replay-yok.**
