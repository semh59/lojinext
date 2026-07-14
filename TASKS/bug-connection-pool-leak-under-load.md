# BUG — Connection-pool leak eşzamanlı yük altında (app-geneli, dalga-bağımsız)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Bu bir modül taşıma görevi DEĞİL.** FAZ1'in 17 dalga sırasının dışında,
bağımsız bir bug-investigation görevidir — **herhangi bir dalga beklemeden,
herhangi bir oturumda** ele alınabilir/alınmalı. `platform-infra` (dalga 17)
bu koddaki dosyaların (`app/api/deps.py`, `app/database/connection.py`)
nihai sahibi olacak olsa da, canlı-güvenilirlik riski taşıdığı için dalga
17'ye kadar beklenmesi ÖNERİLMEZ.

**Giriş kriteri:** yok (bağımsız). **Çıkış kriteri:** kök neden bulundu,
düzeltildi, gerçek eşzamanlı yük altında (Locust, ≥30 kullanıcı) tekrarlanan
koşumda leak uyarısı 0.

---

## 1. Bulgu (2026-07-14, dalga 4 sonrası kullanıcı talebiyle yapılan Locust yük testinde keşfedildi)

`loadtest/locustfile.py` ile gerçek Docker backend'ine (`lojinext_db`,
gerçek Postgres) karşı 30 eşzamanlı kullanıcı, 90 saniye headless koşum
yapıldı (`locust -f locustfile.py --host http://backend:8000 --headless -u 30 -r 5 -t 90s`).

**Gözlem:** Backend logunda yük testi öncesi (`docker logs --since 2h --until <test-başlangıcı>`)
`"non-checked-in connection"` uyarısı **0 kez** görüldü. Yük testi sırasında
(`docker logs --since 3m`) aynı uyarı **52 kez** göründü:

```
ERROR | sqlalchemy.pool.impl.AsyncAdaptedQueuePool | _finalize_fairy |
The garbage collector is trying to clean up non-checked-in connection
<AdaptedConnection <asyncpg.connection.Connection object at 0x...>>,
which will be terminated. Please ensure that SQLAlchemy pooled connections
are returned to the pool explicitly, either by calling ``close()`` or by
using appropriate context managers to manage their lifecycle.
```

Bu, en az bir kod yolunda bir `AsyncSession`/connection'ın `close()`
edilmeden (veya `async with` bloğu dışında bırakılarak) sızdırıldığı, ve
sadece garbage collector devreye girdiğinde (yani ne zaman olacağı belirsiz,
event-loop'u bloklayabilen) zorla temizlendiği anlamına gelir.

**Yan etkisi:** Aynı yük testinde toplam 1008 istekten 12'si (%1.19)
`ConnectionResetError(104, 'Connection reset by peer')` veya
`RemoteDisconnected` ile başarısız oldu — muhtemelen leak'in tükettiği
pool kapasitesinin bir sonucu. p95 latency 710ms, p99 4900ms (GO gate #4
eşiği: p95<800ms — p95 sınırda, p99 ÇOK üstünde).

## 2. Kapsam — dalga 1-4'e özgü DEĞİL

Leak uyarıları şu endpoint'lerin **hepsinde** karışık şekilde gözlendi
(zaman damgası + eşzamanlı istek log korelasyonuyla doğrulandı, tek bir
endpoint'e izole edilemedi):
`/api/v1/trips/`, `/api/v1/trips/stats`, `/api/v1/trips/today`,
`/api/v1/auth/token`, `/api/v1/anomalies/`, `/api/v1/vehicles/`,
`/api/v1/fuel/`, `/api/v1/drivers/`, `/api/v1/reports/executive/kpi`.

Bunlardan yalnız `/vehicles/*` (fleet, dalga 3) ve `/fuel/*` (fuel, dalga 4)
taşınmış modüllere ait — `/trips/*`, `/drivers/*`, `/anomalies/*`,
`/auth/token`, `/reports/executive/kpi` HENÜZ taşınmadı (trip/driver/anomaly/
auth-rbac/analytics-executive, dalga 5+). Leak, taşınmış-taşınmamış ayrımı
gözetmeksizin her ikisinde de görülüyor → **paylaşılan altyapı katmanının**
(request-scoped DB session yaşam döngüsü) sorunu, bir modülün kendi iş
mantığının değil.

Ayrıca dalga 1-4 boyunca yapılan TÜM gerçek-DB doğrulamaları (pytest,
`UnitOfWork`/`db_session` fixture'ları üzerinden binlerce test) bu uyarıyı
hiç üretmedi — yalnızca gerçek eşzamanlı HTTP isteği (Locust → uvicorn →
SQLAlchemy pool) altında tetiklendi. pytest'in test-başına-tek-session
modeli bu path'i hiç egzersiz etmiyor; bu yüzden mevcut hiçbir CI gate'i
(unit/integration testler) bunu yakalamıyor ve yakalayamaz — bir yük testi
gerektirir.

## 3. Şüpheli kod konumları (araştırma başlangıç noktaları, kanıtlanmamış)

- `app/api/deps.py::get_db` — FastAPI `Depends(get_db)` request-scoped
  session factory'si; her request için `async with` bloğu doğru
  kapatılıyor mu, yoksa bir exception/early-return path'i session'ı
  sızdırıyor mu kontrol edilmeli.
- `app/database/connection.py` — engine/pool konfigürasyonu (`pool_size`,
  `max_overflow`, `pool_timeout`, `pool_recycle`); 30 eşzamanlı istek
  altında pool'un gerçekten tükenip tükenmediği (`QueuePool limit reached`
  benzeri ek loglar var mı) ayrıca kontrol edilmeli.
- `app/database/unit_of_work.py` — nested UoW / paylaşılan session
  senaryolarında (`db_session_ctx` contextvar) bir path'in session'ı
  commit/rollback sonrası kapatmadan bırakıp bırakmadığı.
- Middleware zinciri (`app/infrastructure/middleware/logging_middleware.py`
  ve diğerleri) — bir middleware'in, altındaki dependency'nin session
  cleanup'ından ÖNCE response döndürüp döndürmediği (bu, FastAPI'de bilinen
  bir "yield dependency cleanup response'dan sonra çalışır ama middleware
  zaten dönmüşse GC'ye kalır" tuzağı).

## 4. Yeniden üretme

```bash
# Backend + DB ayakta olmalı (docker compose up -d db backend)
# Gerçek (super_admin olmayan, rate-limit'e takılmayan) bir kullanıcı gerekli —
# scripts/create_admin.py ile admin@lojinext.com oluşturulabilir.

docker run --rm --network lojinext_lojinext_network \
  -e LOAD_USER=admin@lojinext.com -e "LOAD_PASS=<şifre>" \
  -v "<repo>/loadtest:/work" -w /work \
  python:3.12-slim bash -c "pip install -q locust && \
    locust -f locustfile.py --host http://backend:8000 \
    --headless -u 30 -r 5 -t 90s --csv results/repro"

# Ayrı bir terminalde, koşum sırasında:
docker logs lojinext-backend-1 --since 2m | grep -c "non-checked-in connection"
```

## Kabul kriterleri
- [ ] Kök neden bulundu (hangi kod yolu session/connection'ı sızdırıyor)
- [ ] Düzeltildi
- [ ] Yukarıdaki repro komutu leak uyarısı olmadan (0 occurrence) tamamlanıyor
- [ ] p95/p99 latency GO gate #4 eşiklerine (p95<800ms) göre yeniden ölçüldü
- [ ] `TASKS/STATUS.md`'deki ilgili not kaldırıldı, `TASKS/modules/platform-infra.md`'deki cross-reference güncellendi
