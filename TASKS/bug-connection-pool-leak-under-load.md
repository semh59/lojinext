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
- [x] Kök neden bulundu (hangi kod yolu session/connection'ı sızdırıyor)
- [x] Düzeltildi
- [x] Yukarıdaki repro komutu leak uyarısı olmadan (0 occurrence) tamamlanıyor
- [x] p95/p99 latency GO gate #4 eşiklerine (p95<800ms) göre yeniden ölçüldü
- [x] `TASKS/STATUS.md`'deki ilgili not kaldırıldı, `TASKS/modules/platform-infra.md`'deki cross-reference güncellendi

---

## ÇÖZÜM (2026-07-14, sistematik debugging süreciyle — bkz. superpowers:systematic-debugging)

### Kök neden #1 — re-entrant `UnitOfWork` (asıl leak)

`AuthService`, `MLService`, `AttributionService` (`app/core/services/{auth,ml,attribution}_service.py`)
constructor'larında ZATEN `async with` içinde açılmış (FastAPI'nin
`get_uow()` dependency'si veya bir endpoint'in kendi `async with
UnitOfWork() as uow:` bloğu tarafından) bir `UnitOfWork` instance'ı alıyor,
sonra kendi metotlarının İÇİNDE bu SAME instance'ı `async with self.uow:`
ile İKİNCİ KEZ açıyordu.

`UnitOfWork.__aenter__`'in eski davranışı: `if self._session is not None:
self._owns = False` — bu SATIR, "yeni bir instance contextvar'daki
paylaşılan session'a katılıyor" (meşru nested pattern) ile "AYNI instance
ikinci kez açılıyor" (bug) arasında ayrım YAPMIYORDU. İkinci durumda
`_owns=False` DIŞ (asıl sahip) instance'ın kendi `_owns` slotunu da
BOZUYORDU (aynı obje) — dış `__aexit__` çalıştığında `if self._owns:
await self._session.close()` hiç tetiklenmiyordu. Session/connection hiç
kapatılmıyor, yalnızca garbage collector rastgele bir zamanda devreye
girince SQLAlchemy'nin "non-checked-in connection" uyarısıyla zorla
sonlandırılıyordu.

**İzole repro ile 100% doğrulandı** (`docker compose exec backend python
-c "..."`): `async with UnitOfWork() as uow: async with uow: ...` sonrası
`engine.pool.checkedout() == 1` (0 olmalıydı) + gerçek GC "non-checked-in
connection" uyarısı anında tetiklendi.

**Fix (4 dosya):**
- `app/core/services/auth_service.py` — 5 metodun (`authenticate`,
  `refresh_session`, `revoke_session`, `request_password_reset`,
  `reset_password`) hepsindeki `async with self.uow:` kaldırıldı, `self.uow`
  doğrudan kullanılıyor.
- `app/core/services/ml_service.py` — `update_task_progress`,
  `get_training_queue`, `register_model_version`'daki aynı desen kaldırıldı
  (`schedule_training` zaten önceki bir oturumda düzeltilmişti, bkz. dosya
  içi NOT).
- `app/api/v1/endpoints/admin_attribution.py` — `AttributionService`'in
  KENDİSİ dokunulmadı (`override_attribution`'ın `async with self.uow:`'u
  onun İKİ farklı çağıranından biri — `bulk_override` — için doğru/gerekli,
  `AttributionService(UnitOfWork())` taze/açılmamış bir instance geçiyor).
  Bunun yerine BUGGY çağıran (`override_trip_attribution` endpoint'i)
  düzeltildi: `async with UnitOfWork(db) as uow: AttributionService(uow)`
  yerine `AttributionService(UnitOfWork(db))` (taze, açılmamış) — tek giriş
  noktası artık servisin kendi `async with self.uow:`'u.
- `app/database/unit_of_work.py` — **defense-in-depth**: `__aenter__`'e
  re-entrancy guard eklendi (`_entered` bayrağı). Aynı instance ikinci kez
  `async with` edilirse artık SESSİZCE `_owns`'u bozmak yerine LOUD
  `RuntimeError` fırlatıyor — üç bağımsız dosyada aynı anti-pattern
  bulunması (3+ occurrence eşiği, systematic-debugging'in "mimariyi
  sorgula" kriteri) bu sınıfın kendi kendini koruması gerektiğini gösterdi.

### Kök neden #2 — senkron `bcrypt.checkpw()` event loop'u bloklıyor

Kök neden #1 düzeltildikten SONRA bile 30-kullanıcılı repro'da hâlâ 18 leak
uyarısı + 60-70 SANİYE gecikmeler görüldü (`GET /health/` bile 62 saniye
sürdü — DB'yle hiç ilgisi olmayan bir endpoint). Kanıt: cascading
ASGI exception'ların kök nedeni `asyncpg` `TimeoutError` (pool
`pre_ping` health-check sorgusu zaman aşımına uğruyordu — aşırı
contention'ın belirtisi, kendisi değil).

`app/core/security.py::verify_password` senkron `bcrypt.checkpw()`
çağırıyor, `auth_service.py::authenticate()` bunu `await` OLMADAN direkt
çağırıyordu — CPU-bound, ~100-300ms'lik bu işlem TEK THREADLI event loop'u
bloke ediyor. 30 eşzamanlı login (hepsi aynı hesabı paylaşıyor, locustfile.py
tasarımı gereği) event loop'u seri hale getiriyor, bu da TÜM eşzamanlı
isteklerin (auth'la ilgisiz olanlar dahil) kuyruklanıp DB pool zaman
aşımlarına kadar tırmanmasına yol açıyordu.

**Fix:** `auth_service.py::authenticate()`'te `jwt_handler.verify_password(...)`
çağrısı `await asyncio.to_thread(jwt_handler.verify_password, ...)`'e
taşındı — event loop artık bcrypt çalışırken diğer istekleri işlemeye
devam edebiliyor.

### Doğrulama (gerçek Docker backend + gerçek Postgres + gerçek Locust)

| Metrik | Öncesi (orijinal bulgu) | Fix #1 sonrası | Fix #1+#2 sonrası |
|---|---|---|---|
| "non-checked-in connection" uyarısı (90s, 30 kullanıcı) | 30-44 | 18 | **0** |
| `POST /auth/token` p99 | — | ~70000ms | **620ms** |
| Aggregated p95 / p99 | 710ms / 4900ms | 68000ms / 70000ms | **140ms / 500ms** |
| Toplam istek / başarısız | — | 40/15 fail | **1080/0 fail** |

Ek doğrulama: `app/tests/test_db_hardening.py`'ye 2 gerçek-regresyon testi
eklendi (`test_uow_reentrant_async_with_raises_instead_of_leaking`,
`test_auth_service_authenticate_does_not_leak_connection`) — ikisi de
fix'ten ÖNCE fail, SONRA pass olarak doğrulandı (TDD red→green). Tam
`auth`+`ml_service`+`attribution` test paketi (263 test) + tüm repo (7007
test, 13 pre-existing/ortam-kaynaklı hata hariç — hepsi bu bug'dan bağımsız
zaten dokümante edilmiş kategoriler) yeşil. `ruff`/`mypy` (6/6 baseline,
regresyon yok) temiz.
