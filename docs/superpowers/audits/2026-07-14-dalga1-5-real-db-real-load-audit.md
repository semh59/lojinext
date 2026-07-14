# Dalga 1-5 — Gerçek DB + Gerçek Yük Denetimi (2026-07-14)

Kullanıcı talebiyle: v2 modüler-monolit rebuild'inin ilk 5 dalgası
(location+route_simulation, notification, fleet, fuel, driver) gerçek
Postgres DB'ye karşı mock'suz test edildi, gerçek Locust yükü altında
koşturuldu, her modülün B.1 (bir dosya = bir use-case) kuralına uyumu
denetlendi, ve Sentry + GitHub üzerindeki açık hatalar tarandı.

## 1. Gerçek-DB test sonuçları (mock yok, `lojinext_test` Postgres)

| Modül | Sonuç | Not |
|---|---|---|
| location | 212/213 pass | 1 fail — aşağıda "ortam artefaktları" |
| route_simulation | 639/646 pass | 7 fail — aşağıda "ortam artefaktları" |
| notification | 111/111 pass | 0 fail |
| fleet | 871/871 pass | 0 fail |
| fuel | 487/488 pass | 1 fail — bilinen env-config gotcha'sı (`USE_SEFER_FUEL_ESTIMATOR=true`) |
| driver | 665/665 pass | 0 fail |

**Ortam artefaktları (kod bugı DEĞİL, bu oturumda kök nedeni tam izole edildi):**

1. **`localhost:9000` ağ-topoloji sorunu** (24 fail → proxy ile 0'a indi): testler
   `api-stub` servisine sabit `http://localhost:9000` ile bağlanıyor — bu,
   ad-hoc `docker compose exec` oturumunda backend container'ının kendi
   network namespace'inde `api-stub`'a çözülmüyor (CI'nın runner-tabanlı
   topolojisinde çalışır). Container içine geçici bir TCP proxy
   (`asyncio` ile `127.0.0.1:9000` → `api-stub:9000`) kurulunca 24
   fail'in 24'ü de yeşile döndü — STATUS.md'nin dalga 1/3/4'te zaten
   dokümante ettiği "api-stub ağ topolojisi" kategorisiyle aynı.
2. **Kalıcı dev container'ın gerçek entegrasyon anahtarları** (8 fail):
   `get_integration_secret()` DB-override okuyan raw `UnitOfWork()` açıyor;
   bu testler `db_session` fixture'ı KULLANMADIĞI için test-DB izolasyonuna
   girmiyor, `settings.DATABASE_URL`'in gösterdiği GERÇEK dev DB'ye
   (`lojinext_db`) bağlanıyor — orada admin panelinden girilmiş gerçek
   mapbox/openroute anahtarları var (id 1,2). "no_api_key" senaryosu bu
   yüzden gerçek bir anahtar görüp None yerine dolu bir sonuç döndürüyor.
   Bu, CI'nın HER ZAMAN temiz/boş bir dev DB ile başlaması sayesinde CI'da
   asla görülmez; yalnız uzun süredir ayakta olan bu yerel container'a
   özgü.
3. **`USE_SEFER_FUEL_ESTIMATOR=true`** (1 fail, fuel) — STATUS.md dalga
   1'de zaten dokümante edilmiş env-config gotcha'sı.

**Gerçek bulgu — düzeltildi (kod değil, container state):** container'da
üç dosya git'te SİLİNMİŞ olmasına rağmen fiziksel olarak duruyordu
(`app/core/ai/chatbot.py`, `app/tests/test_analysis_and_report.py` — hiç
git-tracked olmamış bir stray dosya, `app/tests/unit/test_push_sender.py`
— dalga 2'de silinen `app.core.services.push_sender`'ı import ediyordu,
`ImportError` üretiyordu). Ayrıca daha önceki bir `docker cp` komutunun
(dalga 5 oturumu) `docker cp` hedef-dizin-var-olduğunda-alt-dizin-oluşturma
semantiği yüzünden `/app/v2/v2/` altında TÜM 5 modülün tam bir kopyası
duruyordu (inert, importlanmıyor ama disk kirliliği). Hepsi container'dan
temizlendi — repo'nun kendisi zaten temizdi, bu yalnız bu oturumun
doğrulama ortamını etkiliyordu.

## 2. Gerçek yük testi (Locust, gerçek backend + gerçek Postgres)

`loadtest/locustfile.py` ile `http://backend:8000`'e karşı 2 koşum
(40 kullanıcı/8 ramp/90s, sonra 15 kullanıcı/1 ramp/120s — ikisi de
container ağı üzerinden, host'a port-mapping olmadığı için ephemeral
node/python container'lar üzerinden).

**Sonuç:** Başarılı isteklerde gecikme MÜKEMMEL — medyan 6-9ms, p95
20-49ms, p99 ≤130ms (GO gate #4 eşiği p95<800ms'in çok altında) —
`/drivers/`, `/vehicles/`, `/vehicles/fleet-stats`, `/fuel/`, `/trips/*`
dahil tüm ölçülen endpoint'lerde. **0 connection-pool-leak uyarısı**
her iki koşumda da (`docker logs | grep "non-checked-in connection"`).

**Test isteklerinin ~70-85%'i 401/429 ile başarısız oldu** — bu bir
backend hatası DEĞİL: `locustfile.py`'nin tüm sanal kullanıcıları AYNI
`admin` (super_admin) hesabıyla giriş yapıyor, `SUPER_ADMIN_LOGIN_RATE=3.0`
rate-limiter'ı bu eşzamanlı-login deseninde beklendiği gibi devreye
giriyor (brute-force koruması çalışıyor). Bu, load-test tasarımının
(paylaşılan tek hesap) doğal sonucu, migrasyon/backend'in değil.

**Not — açık `bug-connection-pool-leak-under-load.md` görevi:** Bu görev
dalga4-sonrası ÖNCEKİ bir 30-kullanıcılı Locust koşumunda 52 leak uyarısı
buldu. Bu oturumdaki 2 koşum bunu YENİDEN ÜRETEMEDİ (0 uyarı) — ama bu
"düzeltildi" anlamına gelmiyor: (a) yük seviyem (15-40, çoğu erken
401/429 ile reddedildi) o görevin repro'sundan (30 kullanıcı, gerçek
non-rate-limited kullanıcı) daha hafifti, DB katmanına asıl istek hacmi
ulaşmadı; (b) bug'ın kendi repro talimatı ayrı, rate-limit'e takılmayan
normal-admin kullanıcı gerektiriyor (`scripts/create_admin.py`), bu
oturumda kurulmadı. Görev AÇIK kalmalı, bu bulgu onu kapatmaz.

## 3. B.1 (bir dosya = bir use-case) denetimi — tüm 5 modül

| Modül | Sonuç | Bulgu |
|---|---|---|
| location | ✅ PASS | Tüm dosyalar tek sorumluluk; dokümante istisna (`LokasyonHydrator`) doğru |
| route_simulation | 🔴 **1 FAIL** | `infrastructure/openroute_client.py`'deki `OpenRouteClient` sınıfı 3 ilgisiz sorumluluk taşıyor — bkz. §4 |
| notification | ✅ PASS | 0 dokümante-edilmemiş sınıf, `push_sender` 4-dosya bölünmesi + `admin_ws.py` ayrımı doğrulandı |
| fleet | ⚠️ Gevşek ama PASS | 0 gizli sınıf; 7 dosya (`list_vehicles.py`, `list_trailers.py`, `get_vehicle_maintenance_history.py`, `export_trailers.py`, `update_trailer.py`, `delete_vehicle.py`, `create_maintenance_record.py`) 2-4 ilişkisiz public fonksiyon barındırıyor (location'daki katı 1:1 disiplin uygulanmamış, ama servis-sınıfı değiller) |
| fuel | ⚠️ Gevşek ama PASS | 0 gizli sınıf; `get_yakit.py`/`list_yakit.py` (en ciddisi — sayfalı liste + istatistik + aylık özet aynı dosyada)/`distribute_fuel_to_trips.py`/ölü `consumption_prediction.py` benzer gevşeklik; `LinearRegressionModel` (driver'ın `DriverPerformanceML`'i ile aynı gerekçe sınıfı) CLAUDE.md'de açık istisna olarak işaretlenmemiş (dokümantasyon eksiği) |
| driver | ✅ PASS | (dalga 5'in kendi dedektif denetiminde zaten doğrulanmıştı) |

### §4 — route_simulation FAIL detayı: `OpenRouteClient` mimari sızıntısı

`v2/modules/route_simulation/infrastructure/openroute_client.py:32-616`:
1. `get_distance`/cache — meşru, tek sorumluluk (ORS ikincil sağlayıcı).
2. `geocode`/`_call_geocode_api` — **location modülünün
   `geocode_providers.py::geocode_via_openroute` ile aynı işi tekrarlıyor**
   (DRY ihlali + modül sınırı bulanıklığı). Prod route'larından hiç
   çağrılmıyor, yalnız `scripts/enrich_existing_data.py` + testler kullanıyor.
3. `update_route_distance` — **en ciddisi**: `lokasyonlar` tablosuna
   (root + her iki modülün CLAUDE.md'sinde açıkça `location`'ın
   sahipliğinde olduğu belirtilen tablo) ham SQL `UPDATE` atıyor,
   repository pattern'ini VE tablo-sahipliği kontratını ihlal ediyor.
   Prod'dan çağrılmıyor, ölü/legacy kod.

**Aksiyon alınmadı (kapsam dışı bırakıldı, bu bir taşıma/denetim oturumu,
davranış-değiştiren bir refactor değil):** `get_distance` kalmalı,
`geocode`/`update_route_distance`/`_call_geocode_api` ayrı bir dosyaya
taşınmalı veya (gerçekten kullanılmıyorsa) silinmeli. Ayrı bir görev
olarak açılması önerilir.

## 4. Sentry (de.sentry.io, org semh59, proje lojinext) — 28 çözülmemiş issue

Tümü tarandı, en son görülen (`LOJINEXT-182`, 2026-07-14T10:56:43Z) dahil
**HİÇBİRİ dalga 1-5'in tamamlanma zaman damgalarından SONRA yeni** değil.
Özellikle modüllere değinen 6 issue kontrol edildi — hepsi taşımadan
ÖNCEKİ tarihli (2026-07-09 ila 2026-07-13 arası), biri (`LOJINEXT-1D0`)
literal olarak artık var olmayan `AracService.create_arac`'a referans
veriyor (fleet migrasyonundan önceki kod). Sonuç: **5 dalganın hiçbiri
Sentry'de yeni bir hata üretmedi.** 28 issue'nun hiçbiri bu oturumda
kapatılmadı (kapsam dışı, ayrı bir Sentry-temizlik görevi gerektirir) —
bilgi amaçlı listelendi, çoğu route-level 502/network hatası ve harici
API kota/kesinti olayları (`Routing provider forbidden — Quota exceeded`).

## 5. GitHub — açık issue/Dependabot uyarısı

0 açık issue. Dependabot alerts repo için devre dışı (kontrol edilemedi,
API 403 döndü — `admin:repo_hook` scope gerekiyor). Son 10 CI run'ı
gözden geçirildi — dalga 5'in kendi düzeltme döngüsü dışında beklenmedik
bir kırmızı yok.

## Özet

5/5 modül gerçek DB'ye karşı fonksiyonel olarak sağlam (0 kod-bugı,
tüm fail'ler ortam artefaktı olarak izole edildi ve doğrulandı). Backend
gerçek yük altında hızlı ve stabil (leak yok, mükemmel gecikme). B.1
kuralı 4/5 modülde tam, 2 modülde (fleet, fuel) gevşek ama sınıf-kaçağı
yok; route_simulation'da 1 gerçek (ama ölü-kod, prod'u etkilemeyen)
mimari sızıntı bulundu. Sentry/GitHub'da yeni regresyon yok.

**Açık takip kalemleri (bu oturumda AÇILMADI, yalnız tespit edildi):**
- `OpenRouteClient` 3-sorumluluk sızıntısı (route_simulation) — bölünmeli/temizlenmeli.
- fleet/fuel'de birden fazla use-case barındıran dosyalar — istenirse bölünebilir.
- `bug-connection-pool-leak-under-load.md` hâlâ AÇIK, bu oturum onu ne doğruladı ne çürüttü.
- Sentry'deki 28 çözülmemiş issue (hepsi pre-migration, ayrı temizlik gerektirir).
