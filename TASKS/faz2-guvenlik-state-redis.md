# FAZ2 — Multi-Worker Güvenlik State'i → Redis

> ✅ **TAMAMLANDI (2026-07-23)** — kullanıcı onayıyla uygulandı (bkz. aşağıdaki
> "Uygulama notları" bölümü). FAZ2'nin 3 alt-görevinden ilk uygulanan buydu
> (bağımsız, DB şeması değişmiyor); `faz2-schema-per-module-postgres.md` ve
> `faz2-db-rol-izolasyonu-ve-read-model-grantlari.md` hâlâ ayrı onay bekliyor.

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Amaç:** MEMORY/PROGRESS.md §4.1'de tespit edilen in-memory per-process güvenlik sayaçlarını Redis-backed hale getirmek. Sert Kısıt 7 — bu sorun modülerleşmeyle KENDİLİĞİNDEN çözülmez, çünkü `security_probe.py` zaten platform-infra'da tek dosya; sorun modül sınırı değil, `UVICORN_WORKERS=4`'ün süreç-yerel state'i paylaşmaması.

**Giriş kriteri:** FAZ1 tamamlandı (platform-infra registry finali). **Çıkış kriteri:** 4 worker'da eşikler toplamda doğru sayılıyor (paylaşımlı sayaç); mevcut davranışsal testler (varsa) hâlâ geçiyor.

---

## Değiştirilecek bileşenler (MEMORY §4.1'den, tam liste)

| Bileşen | Dosya:satır | Bugünkü state | Hedef |
|---|---|---|---|
| BruteForceDetector | `security_probe.py:39` | `OrderedDict`+`Lock`, per-process | Redis `INCR`+`EXPIRE` (mevcut `rate_limit_middleware.py`'nin deseni referans) |
| RBACViolationTracker | `security_probe.py:97` | aynı | aynı desen |
| AsyncRateLimiter/RateLimiterRegistry | `resilience/rate_limiter.py` | class-level dict, per-process | Redis-backed token-bucket |
| slowapi adaptörü | `api/middleware/rate_limiter.py` | in-memory storage (varsayılan) | slowapi'nin Redis storage backend'i (`storage_uri=redis://...`) |

## Referans desen (zaten çalışan kod — `rate_limit_middleware.py`)
```python
async def _increment_redis(self, key: str, window_seconds: int) -> int:
    pipe = self._redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    result = await pipe.execute()
    return result[0]
```
Bu atomik INCR+EXPIRE deseni, `BruteForceDetector`/`RBACViolationTracker` için birebir uygulanır — yeni bir mekanizma İCAT EDİLMEZ, kanıtlanmış deseni tekrar kullanılır (kod kısalığı kuralı: mevcut çözüm varken yeniden icat yasak).

## Sessiz-düşme davranışının kaldırılması
Bugün `rate_limit_middleware.py` Redis düşünce in-memory'e SESSİZCE düşüyor (MEMORY §4.1). Bu FAZ'da: Redis erişilemezse **fail-closed** (istek reddedilir, log'lanır) VEYA en azından metriğe yansıyan bir uyarı — sessiz tek-worker fallback'i kaldırılır (güvenlik sayacının "çalışıyor gibi görünüp aslında seyrelmiş" davranışı MEMORY §4.1'in ana bulgusuydu, bu FAZ onu düzeltiyor).

## EnsemblePredictorService not (kapsam dışı, ama dokümante)
20-slot LRU model cache × 4 worker RAM çarpanı BU GÖREVİN KAPSAMI DIŞINDA — güvenlik state'i değil, kaynak-yönetimi. `TASKS/modules/prediction-ml.md` madde 4'te ayrı performans işi olarak işaretli, burada tekrar edilmez.

## Kabul Kriterleri
- [x] BruteForceDetector + RBACViolationTracker Redis-backed, `rate_limit_middleware.py` deseniyle tutarlı
- [x] AsyncRateLimiter Redis-backed
- [x] slowapi `storage_uri` Redis'e işaret ediyor
- [x] Redis kesintisinde fail-closed (sessiz fallback yok), log'a yansıyor
- [x] 4-worker simülasyon testi: aynı IP'den 4 worker'a dağıtılan istekler TEK eşiğe tabi (önceden ~4× seyrelen davranış düzeldi)

## Uygulama notları (2026-07-23)

**Kullanıcı kararı — Redis-down davranışı:** görev dosyasının "fail-closed VEYA
metriğe yansıyan uyarı" ikileminde kullanıcı **fail-closed**'ı seçti. İki
bileşen kategorisi farklı uygulandı:
- **Pre-request gate'ler** (`AsyncRateLimiter.acquire()`,
  `RateLimitMiddleware._increment_redis`, slowapi `Limiter`): Redis
  erişilemezse istek gerçekten reddedilir (429/503).
- **Post-response detector'lar** (`BruteForceDetector`/`RBACViolationTracker`):
  bunların bloklayacağı bir istek yok (yanıt zaten üretildi) — literal
  "reddet" uygulanamaz. Sadık karşılık: sayaç sessizce in-memory'e DÜŞMEZ,
  CRITICAL `ErrorEvent` yayınlanır (fail-loud) + bu detector'ların asıl
  koruduğu yüzey (`/api/v1/auth/token`) zaten `RateLimitMiddleware`'in
  `_AUTH_PATHS` sıkı-limit yoluyla ayrıca fail-closed oluyor.

**Değiştirilen dosyalar:** `monitoring/security_probe.py` (record() artık
async, Redis INCR+EXPIRE + SET NX alert-dedup + LPUSH/LTRIM endpoint-sample),
`middleware/logging_middleware.py` (await eklendi),
`resilience/rate_limiter.py` (AsyncRateLimiter sürekli-refill token-bucket'tan
Redis-backed sabit-pencere sayaca geçti — dokümante edilen kasıtlı davranış
değişikliği; `RateLimiterRegistry`/`RateLimiterDependency`/`rate_limited` API
yüzeyi değişmedi), `middleware/rate_limit_middleware.py` (sessiz
`_increment_memory` fallback'i + `_evict_expired` silindi, Redis hatası artık
503 döndürüyor), `middleware/slowapi_limiter.py` (`storage_uri=REDIS_URL`),
`app/main.py` (`redis_unavailable_handler` — `redis.exceptions.ConnectionError`
→ 503, slowapi'nin Redis storage hatalarını yakalar).

**Doğrulama (bu oturumda gerçekten koşuldu):**
- `ruff check --select E,F,W,I` → tüm değiştirilen dosyalar temiz.
- `mypy --ignore-missing-imports --no-strict-optional` → değiştirilen
  dosyalarda 0 yeni hata (4 pre-existing hata `trip/infrastructure/
  repository.py`'de, bu göreve dokunulmadı).
- `pytest` (izole venv, gerçek paket kurulumu — `app/tests/unit/
  test_monitoring/test_security_probe.py` +`test_security_probe_coverage.py`
  + `test_infrastructure/test_rate_limiter.py` +
  `test_rate_limit_middleware_coverage.py` + `test_rate_limit_master_switch.py`):
  **82/82 passed**, 4-worker simülasyon testleri dahil.
- **Yapılamadı (ortam kısıtı, dürüstçe not düşülüyor):** bu oturumun sandbox
  ortamında Docker daemon çalışmıyor — gerçek `docker compose stop redis` ile
  fail-closed davranışını canlı doğrulamak ve CI'nin gerçek combined-coverage
  koşusunu (`--cov-fail-under=92`) çalıştırmak mümkün olmadı. Push sonrası
  gerçek CI ("hard-gates" job'ı, bu oturumda main'de yeşil olduğu doğrulandı)
  bu doğrulamayı tamamlayacak — CI kırmızı çıkarsa düzeltme bu PR'a eklenir.
