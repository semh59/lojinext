# Servis: telegram_bot

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Standalone bir mikroservis — FastAPI `app`/`v2/modules` içine import edilmez,
kendi `Dockerfile`+`requirements.txt`'i ile ayrı bir container'da çalışır
(`docker-compose.yml`: `telegram-ops-bot` + `telegram-driver-bot` servisleri,
aynı image'dan `BOT_TYPE` env'iyle iki farklı process olarak başlatılır — bkz.
`main.py`). 2026-07-30'da repo kökünden (`telegram_bot/`) buraya taşındı
(`v2/modules/<name>/` deseninden FARKLI — bu bir FastAPI iş modülü DEĞİL,
sadece dosya konumu düzenlendi; `public.py`/`events.py`/DI-container wiring
YOK).

- `driver_bot.py` — şoför botu: fotoğraf yükleme (yakıt fişi/sefer fişi/TIR
  ekran, caption'a göre sınıflandırılır), `/pdf`, `/seferlerim`, `/score`,
  `/oneriler`, `/ariza` komutları. Hepsi backend'in `/api/v1/internal/*`
  endpoint'lerine `X-Internal-Token` header'ıyla HTTP çağrısı yapar.
- `ops_bot.py` — operasyon botu: `/durum`, `/uyarilar` (yalnız
  `TELEGRAM_OPS_CHAT_ID`'den gelen mesajlara yanıt verir), `/yeniden_baslat`
  (yalnız `OPS_ADMIN_TELEGRAM_IDS`'teki kullanıcılar). Ayrıca bir FastAPI
  webhook sunucusu (`webhook_app`, ayrı daemon thread, port 8080) barındırır:
  Alertmanager/backend'den gelen `/webhook/alertmanager`, `/webhook/error`,
  `/webhook/feedback` POST'larını Telegram'a iletir.
- `token_resolver.py` — bot token'ını admin-panelden (DB override, backend'e
  gerçek HTTP çağrısıyla) veya `.env` fallback'inden çözer.

NE YAPMAZ: backend'in kendi iş mantığını tekrar etmez (sadece ince bir HTTP
istemcisi); container restart'ı DOĞRUDAN Docker CLI/socket ile yapmaz (bkz.
"Docker restart mimarisi" altında).

## Docker restart mimarisi (`/yeniden_baslat`)

`docker` CLI bu image'a hiç kurulu değil (2026-07-30'a kadar `/yeniden_baslat`
komutu bu yüzden hiç çalışmamıştı — `subprocess.run(["docker", ...])` her
zaman `FileNotFoundError` atıyordu, fark edilmemişti çünkü sıfır test
kapsamı vardı). Artık `docker-socket-proxy-ops` adlı, minimal-yetkili ayrı
bir Tecnativa `docker-socket-proxy` instance'ına (`POST=1` + `ALLOW_RESTARTS=1`
SADECE — `CONTAINERS`/`EXEC` YOK, bkz. `docker-compose.yml`'daki geniş
yorum) async `httpx` ile konuşur (`DOCKER_RESTART_PROXY_URL` env).
**`/var/run/docker.sock`'un `:ro` (read-only) mount'u yazma isteklerini
ENGELLEMEZ** — yalnız socket dosyasının kendisinin değiştirilmesini/
silinmesini engeller; bu, canlı bir `POST .../restart` isteğiyle empirik
olarak doğrulandı (2026-07-30). Bu yüzden ham socket mount'u yerine dar
yetkili proxy tercih edildi.

## Test-isolation gotcha'sı

`tests/test_ops_bot_security.py` ve `tests/test_driver_bot.py`, modül
import zamanında gerçek ağ çağrısı yapmaması için `token_resolver.
resolve_bot_token`'ı **scoped** bir `unittest.mock.patch(...)` context
manager'ı içinde import ederler — ASLA kalıcı/unscoped bir modül-seviyesi
atama (`token_resolver.resolve_bot_token = lambda...`) YAPMAYIN. pytest her
test modülünü oturum başına bir kez import eder ve dosyaları alfabetik
toplar; kalıcı bir atama, `test_token_resolver.py`'nin KENDİ testlerine
(gerçek fonksiyonu import eden) sessizce sızar — yalnız TÜM `tests/`
dizini birlikte koşulduğunda görünür (2026-07-30'a kadar bu paketin CI
wiring'i yoktu, bu yüzden hiç yakalanmamıştı).

## CI durumu

**Bu servisin testleri `.github/workflows/ci.yml`'e BAĞLI DEĞİL** —
`python -m pytest tests/` yalnız container içinde elle koşularak
doğrulanıyor (2026-07-30 itibarıyla 36 test, hepsi yeşil). CI'ya wiring
eklemek backlog'da açık bir kalem (bkz.
`docs/superpowers/plans/backlog/2026-07-30-consolidated-open-items-backlog.md`).

## Ortam değişkenleri (zorunlu olanlar)

`TELEGRAM_OPS_BOT_TOKEN`/`TELEGRAM_DRIVER_BOT_TOKEN` (veya admin panelden DB
override), `TELEGRAM_OPS_CHAT_ID`, `OPS_WEBHOOK_SECRET` (boşsa webhook
fail-closed reddeder — güvenlik önceliği), `INTERNAL_API_SECRET`,
`BACKEND_URL`. Opsiyonel: `OPS_ADMIN_TELEGRAM_IDS` (boşsa `/yeniden_baslat`
tamamen devre dışı), `DOCKER_RESTART_PROXY_URL`.
