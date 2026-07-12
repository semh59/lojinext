# FAZ2 — Multi-Worker Güvenlik State'i → Redis

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
- [ ] BruteForceDetector + RBACViolationTracker Redis-backed, `rate_limit_middleware.py` deseniyle tutarlı
- [ ] AsyncRateLimiter Redis-backed
- [ ] slowapi `storage_uri` Redis'e işaret ediyor
- [ ] Redis kesintisinde fail-closed (sessiz fallback yok), log'a yansıyor
- [ ] 4-worker simülasyon testi: aynı IP'den 4 worker'a dağıtılan istekler TEK eşiğe tabi (önceden ~4× seyrelen davranış düzeldi)
