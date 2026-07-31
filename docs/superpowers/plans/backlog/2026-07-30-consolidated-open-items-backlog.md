# Konsolide açık-iş backlog'u (2026-07-30)

Bu dosya, proje hafızasında dağınık halde bulunan "daha sonra yapılacak"
kalemlerin tek yerde toplanmış hali. Kullanıcı kararıyla oluşturuldu
(2026-07-30): bazı eski kalemler iptal edildi, bazıları burada backlog'a
alındı, bazıları bilinçli olarak ertelenmiş durumda bırakıldı.

## İptal edilenler (bu backlog'da YOK, referans için not düşüldü)

- **Feature M — Takograf entegrasyonu**: `2026-05-26-feature-m-takograf-
  entegrasyon-DEFERRED.md` silindi (2026-07-30, kullanıcı kararı). Tekrar
  gündeme gelirse sıfırdan planlanmalı.
- **VPS/domain/TLS kurulumu** (eski FAZ 11 dış-kaynak kalemi): kullanıcı
  kararı — domain satın alınmayacak, bu iş yapılmayacak. Backlog'dan
  tamamen çıkarıldı.
- **GitHub repo'yu private yapma**: kullanıcı kararı — bir süre daha
  PUBLIC kalacak. Aksiyon yok, ama madde açık durumda kaldığı unutulmasın
  diye not: `gh repo view semh59/lojinext` → `isPrivate: false`.
- **Coverage %95 hedefi**: kullanıcı kararı — ertelendi. Gerçek gate hâlâ
  %92 (`ci.yml` "Combined coverage gate"); ML training-loop dosyaları
  (`time_series_predictor` ~%46, `advanced_lstm` ~%63, `benchmark` ~%44)
  PyTorch/gerçek-veri bağımlı, unit testle pratik değil. Backlog'a
  alınmadı, yalnız gerçek durum burada kayıtlı.

## Backlog'a alınanlar

### 1. Segment-tractive fizik modeli — canlı p51 koşuldu, flip YAPILMADI, kalibrasyon işi ayrıldı (2026-07-30)

`app/config.py:247` — `USE_SEGMENT_TRACTIVE_MODEL: bool = False` (hâlâ
kapalı, bilinçli karar). `scripts/p51_real_world_validation.py`'a env
okuma desteği eklendi (`USE_SEGMENT_TRACTIVE_MODEL=true` ile canlı koşum
artık mümkün, önceden script flag'e hiç dokunmuyordu).

**Canlı p51 koşuldu (2026-07-30, gerçek Mapbox+Open-Meteo, flag=true)**:
✅ 7/10 GREEN, ⚠️ 3 YELLOW, ❌ 0 RED (Sanity 10/10 geçti). Karşılaştırma:

| Koşum | GREEN | YELLOW | RED |
|---|---|---|---|
| 2026-06-14 offline (flag=true, depolanmış geometri) | 9/10 | 1 | 0 |
| 2026-06-23 canlı (flag=false, mevcut varsayılan) | 8/10 | 1 | 1 |
| 2026-07-30 canlı (flag=true) | 7/10 | 3 | 0 |

**Karar (kullanıcı, 2026-07-30): flip YOK** — sonuç net bir iyileşme
göstermiyor (RED sıfıra indi ama GREEN sayısı hem offline hem mevcut
canlı-varsayılana göre düştü).

**İlk kök-neden teorim YANLIŞTI, düzeltildi**: önce "eski toplu modelin
iniş enerjisine %60-90 'gravity recovery' kredisi verip yeni segment-
tractive modelin bunu kaldırdığı, kalibrasyonun eski modele göre kaldığı"
teorisini yazmıştım (`predict_granular` vs `predict_segment_tractive`
kod farkına bakarak). Bu, `scripts/calibrate_physics.py`'yi kontrol
etmeden yapılmış hatalı bir çıkarımdı — o script'in kendi docstring'i
mevcut `PHYSICS_DRAG_CDA_M2=6.80`/`PHYSICS_PARASITIC_KW=4.0` sabitlerinin
ZATEN segment-tractive modelin kendisine göre (10 gerçek rotaya, gravity-
recovery'siz) fit edildiğini ve 9/10 GREEN verdiğini gösteriyor —
gravity-recovery farkı zaten hesaba katılmıştı.

**Gerçek kök neden (doğrulandı)**: bu kalibrasyon `route_segments`
tablosundaki DEPOLANMIŞ geometriye (2026-06-14 offline validasyonuyla
aynı kaynak) göre yapılmıştı. Canlı p51 koşusu HER SEFERİNDE taze
Mapbox+Open-Meteo çağrısıyla YENİ geometri üretip `route_simulations`/
`route_segments`'e yazıyor (bugünün trafiği/hava durumu farklı rota
karakteristikleri veriyor) — aynı fiziksel sabitler artık optimal
düşmüyor. Bunu KANITLAMAK için `scripts/calibrate_physics.py`'yi
(hiçbir ek API çağrısı gerektirmeden, sadece az önceki canlı koşumun
DB'ye yazdığı taze geometriyle) yeniden çalıştırdım: yeni en-iyi-fit
`Cd·A=5.3 m², parazit=11.5 kW` → **9/10 GREEN** (yalnız KON-AKS RED
kaldı, -%11.3). Bu, "kalibrasyon zamanla drift ediyor, periyodik
yeniden-fit gerekiyor" demek — modelin kendisinde bir kusur değil.

**⚠️ Dikkat**: `Cd·A=5.3`, script'in kendi fiziksel bandının
(`CDA_BAND=(5.3, 7.5)`) tam ALT SINIRINDA — tek bir günün trafik/hava
anlık görüntüsüne aşırı-uyum (overfit) riski taşıyor, script'in kendi
"OVERFIT GUARD" yorumunun işaret ettiği tam senaryo. Üretime almadan
önce canlı p51'i bu yeni sabitlerle uçtan uca doğrulamadan (bkz.
aşağıdaki durum) `config.py`'ye YAZILMADI.

**Tek-günlük yeniden-kalibrasyon uçtan-uca doğrulandı (2026-07-30) — NET
KAZANÇ DEĞİL, `config.py` DEĞİŞTİRİLMEDİ**: yeni sabitlerle (`Cd·A=5.3`,
`parazit=11.5kW`) canlı p51'i tekrar koştum:

| Koşum | GREEN | YELLOW | RED | Sanity |
|---|---|---|---|---|
| 2026-06-14 offline (flag=true, eski sabitler) | 9/10 | 1 | 0 | — |
| 2026-06-23 canlı (flag=false, mevcut varsayılan) | 8/10 | 1 | 1 | — |
| 2026-07-30 canlı (flag=true, eski sabitler) | 7/10 | 3 | 0 | 10/10 |
| 2026-07-30 canlı (flag=true, yeni sabitler) | 8/10 | 1 | 1 | **8/10** |

GREEN sayısı mevcut flag=false varsayılanıyla aynı (8/10) ama artık 2
rotada "Tam" çıktı sanity sınırını (band×1.12) aşıyor (öncekinde hiç
yoktu) ve VAL-KON-AKS YELLOW'dan RED'e geriledi. Bu, `Cd·A=5.3`'ün
fiziksel bandın tam sınırında oturmasından kaynaklanan aşırı-uyum
riskini doğruluyor — **kullanıcı kararıyla `config.py` değiştirilmedi**,
flag=false + eski sabitler production'da kalıyor.

**✅ TAMAMLANDI (2026-07-30) — otomatik haftalık snapshot mekanizması
kuruldu**: tek-günlük fit'e güvenmek yerine, `physics.weekly_
recalibration_snapshot` adında yeni bir Celery beat task'ı (Pazar 02:30
UTC) her hafta otomatik olarak: (a) 10 referans rotanın canlı geometrisini
tazeler (gerçek Mapbox+Open-Meteo), (b) aynı grid-search fit'i çalıştırır,
(c) tarihli bir satırı `data/calibration/physics_recalibration_log.jsonl`'a
ekler. `config.py`'yi OTOMATİK GÜNCELLEMEZ — birkaç haftalık veri
biriktikten sonra insan gözden geçirip flip kararını verecek. Fit
mantığı (`load_reference_route_segments`/`score_routes`/
`grid_search_best_fit`) `v2/modules/route_simulation/application/
physics_calibration.py`'ye çıkarıldı, referans rota verisi (`REFERENCE_
ROUTES`) `domain/physics_reference_routes.py`'ye taşındı — hem
`scripts/calibrate_physics.py` hem yeni task aynı kodu paylaşıyor.
Gerçek Postgres/Docker'a karşı doğrulandı: 1 rotanın canlı yenilemesi
(gerçek Mapbox+Open-Meteo round-trip) + fit + snapshot yazımı uçtan uca
test edildi (9/10 GREEN, dosyaya yazıldı) — kalan 9 rotanın da AYNI,
zaten kanıtlanmış kod yolundan geçtiği için (kota tasarrufu amacıyla)
tam 10-rotalı bir kuru koşu tekrar yapılmadı.

**Yan bulgu — 2 gerçek pre-existing bug** (`scripts/p51_real_world_
validation.py`, canlı koşumlar sırasında bulunup düzeltildi):
1. `get_or_create_driver` — `soforler.ad_soyad` PII-encrypted (`EncryptedPII`),
   ham SQL `WHERE ad_soyad = :name` düz metni şifreli değerle
   karşılaştırıyordu, hiç eşleşmiyordu → ikinci koşumda gerçek bir
   `ValueError` ile patladı. `SoforRepository.get_by_name()` (doğru
   blind-index karşılaştırması) kullanılacak şekilde düzeltildi.
2. `get_or_create_location` — Python'un `str.title()`'ı Türkçe-duyarsız
   ("Istanbul" → "Istanbul", noktasız I), ama `create_location()` gerçekte
   `normalize_turkish_title()` ile saklıyor ("İstanbul", noktalı İ) — ham
   SQL karşılaştırması hiç eşleşmiyordu, ikinci koşumda `create_location`'ın
   kendi (doğru) tekrar-kontrolü gerçek bir `ValueError` fırlattı.
   `LokasyonRepository.get_by_route()` (nokta/noktasız-i nötrleştirmesi
   zaten yapıyor) kullanılacak şekilde düzeltildi.

### 2. 0-mock epiği — durumu belirsizdi, ölçüldü (2026-07-30)

Gerçek dosya sayımı (`grep -rl` ile):
- Backend (`unittest.mock`/`MagicMock`/`AsyncMock`/`@patch` kullanan
  dosya): **266** (2026-07-02 baseline: 296 — hafif iyileşme).
- Frontend (`vi.mock(...)` kullanan dosya): **136** (2026-07-02 baseline:
  127 — KÖTÜLEŞMİŞ, yeni testler mock'suz yazılmamış).

✅ **TAMAMLANDI (2026-07-30) — 98 dosya tek tek triyaj edildi, dosya-sayım
metriği yanıltıcıymış.** Ham `grep -rl` sayısı (266 backend/136 frontend)
"kaç dosya mock kullanıyor" sorusuna cevap veriyordu ama epiğin kendi
kapsamı (kök CLAUDE.md: "0-mock epiği — **dış-API** stub") yalnız
Mapbox/OpenRoute/Open-Meteo/Telegram/Groq gibi GERÇEK üçüncü-taraf HTTP
sınırlarını hedefliyor — dahili DB-session/use-case-fonksiyon/circuit-
breaker mock'ları hiç kapsamda değildi. Kümeler tek tek açılıp
sınıflandırıldı:

- **Location/route (12 dosya)**: 11'i zaten dönüştürülmüş/meşru kapsam
  dışı (`route_location_zero_mock_2026_07`'nin "tamamlandı" iddiası
  büyük ölçüde doğruymuş); 1 gerçek bug bulundu — `external_service.py`'nin
  `OPENMETEO_URL`'i hardcoded'du, `api_stub`'ı hiç kapsamıyordu. Yeni
  `/v1/forecast` stub endpoint'i eklendi, 2 test gerçek HTTP'ye çevrildi.
- **test_services (46), test_monitoring (17), test_repositories (13),
  test_ml (10)**: tek tek tarandı, **sıfır** ek gerçek dış-API mock'u
  bulundu. Hepsi ya dahili instrumentation/probe mantığını (circuit
  breaker, DB-session, event-bus, ML model wrapper'ları) test ediyor ya
  da (Telegram notifier gibi) kendi iç servislerimize (telegram-ops-bot
  container'ı) konuşuyor, `api.telegram.org`'a değil. `test_ai_service_
  coverage.py`'nin GroqService mock'u da kendi docstring'inde zaten
  "so no real LLM call" diye bilinçli olarak dokümante edilmiş (önceki
  bir de-mock turundan, Dilim 28) — prompt-sanitizasyon mantığını test
  ediyor, LLM çağrısı gerektirmiyor.

**Sonuç**: epiğin gerçek kalan yüzeyi (dış-API mock'ları) dosya-sayım
metriğinin ima ettiğinden ÇOK daha küçüktü — 98 dosyadan sadece 1 gerçek
dönüştürme adayı çıktı, o da düzeltildi. Frontend tarafı (`vi.mock`, 136
dosya) bu oturumda taranmadı — ayrı bir gelecek iş olarak bırakıldı.

**Devam turu (2026-07-30, "tümünü bitir" talimatıyla)**: `test_services/
test_monitoring/test_repositories/test_ml` kümeleri dışında kalan
Telegram/Groq/OpenRoute referanslı 8 dosya ek olarak taranıp gerçek
dış-API mock'u tespit edilenler `api_stub`'a çevrildi:
- `test_workers/test_coaching_tasks_more.py`, `api/test_coaching_coverage.py`,
  `api/test_investigations_more.py` — Telegram sendMessage success/error
  path'leri (`SIMULATE_ERROR` token sentinel'i).
- `test_routing.py` (moved to `integration/test_route_api.py::test_call_api_success`,
  `pytest.mark.integration`) — gerçek HTTP api_stub'a.
- `unit/test_groq_service_coverage.py::test_chat_success` — **DENENDİ, GERİ ALINDI**.
  Gerçek `AsyncGroq` SDK client'ı `api_stub`'a karşı önce izole ve ~200
  testlik lokal bir alt kümede yeşil doğrulandı, ama CI'nın gerçek
  `-m integration` oturumunda (~1470 test, run 30577084026, job
  90987928815) "TypeError: object MagicMock can't be used in 'await'
  expression" ile patladı — o büyük oturumdaki BAŞKA bir testle global
  state çakışması (hangisi olduğu, tükenmez bisection gerektirdiği için
  bulunamadı; hiçbir daha küçük lokal alt kümede tekrar üretilemedi).
  Bilinçli karar: bu TEK dönüşüm geri alındı (mock'lu haline döndü,
  gerekçe dosya içinde docstring), diğer tüm Telegram/OpenRoute
  dönüşümleri (api_stub'ın gerçek HTTP + hata-enjeksiyonu yolu) sağlam
  kaldığı için epiğin genel kapsamı etkilenmedi — yalnız Groq'un SDK-
  seviyeli round-trip'i mock'lu kalıyor.
- `integration/test_coaching_endpoints.py::test_send_success_with_mocked_telegram` —
  gerçek HTTP + api_stub'ın echo-back `chat_id`/`text`'i ile doğrulama;
  aynı dosyadaki `test_send_html_escapes_user_message` bilinçli mock'lu
  kaldı (endpoint outgoing payload'ı kendi response'unda ifşa etmiyor,
  escape mantığı zaten `test_coaching_coverage.py`'de mock'suz test
  ediliyor).
- `integration/test_coaching_effectiveness.py` (2 test) — içerik
  doğrulaması olmayan basit success-passthrough mock'ları gerçek HTTP'ye
  çevrildi.
- `integration/test_theft_alarm.py::test_telegram_error_does_not_break_creation` —
  `SIMULATE_ERROR` sentinel'i; aynı dosyadaki diğer 4 test ("post hiç
  çağrılmadı" negatif iddiaları + dinamik içerik doğrulaması gerektiren
  success path) bilinçli mock'lu kaldı — endpoint dış çağrının yapılıp
  yapılmadığını kendi response'unda ifşa etmiyor, `_build_theft_alarm_
  text()` içeriği zaten `test_theft_alarm_text.py`'de mock'suz test
  ediliyor.

Geniş bir son-tarama (`httpx.AsyncClient`/`AsyncClient.post`/`respx`/
`MockTransport` + `*Client(...)`/`_get_client` desenleri, ~30 dosya)
başka gerçek dış-API mock'u yüzeye çıkarmadı — kalanlar circuit-breaker/
DB-session/singleton gibi dahili mantık testleri ya da zaten hedefli
(erişilemez except-dalı) patch'ler. Backend tarafı artık gerçekten
tam taranmış sayılabilir. Frontend (`vi.mock`, 136 dosya) hâlâ
taranmadı — kapsam dışında kalmaya devam ediyor.

### 3. FAZ2 Wave 2 kalanları (bkz. [[faz2_wave2_completed]] hafıza kaydı)

- Celery `task_prerun`/`task_postrun` sinyalinden modül-rolü (`m_<modül>`)
  türetme — şu an Celery task'ları `module_role=None` (rol kısıtlamasız)
  çalışıyor, yalnız HTTP router'ları rol-korumalı.
- 16 `m_ops` script'inin `open_role_scoped_session("m_ops")` kullanımına
  geçirilmesi.
- **GHCR ilk-push PAT'i** — kullanıcı aksiyonu bekliyor: yeni
  `write:packages` scope'lu bir PAT oluşturup `GHCR_TOKEN` secret'ine
  eklemek (veya paketi elle bir kez `docker push` ile oluşturmak).
  `hard-gates` CI job'ı zaten yeşil, bu yalnız Docker image publish
  adımını etkiliyor.

### 4. VAPID push bildirimleri ✅ TAMAMLANDI (2026-07-31, uçtan uca doğrulandı)

Push altyapısı (subscribe/unsubscribe/sender/410-cleanup + 3 tetikleyici:
kritik anomali, muayene, weekly digest) kodda tam kuruluydu. Teslim ucu
kontrol edildiğinde `.env`'de VAPID anahtarlarının aslında 2026-05-28'de
(py-vapid ile) zaten üretilip eklenmiş olduğu görüldü — bu maddenin "hiç
yapılmadı" iddiası güncel değilmiş, yalnız gerçek tarayıcı doğrulaması
hiç yapılmamıştı. Bu oturumda:
- `.env.prod`'a (yerel, git'e girmiyor) ayrı bir VAPID anahtar çifti
  üretilip eklendi (dev ile paylaşılmıyor — güvenlik ayrımı).
- Claude-in-Chrome ile gerçek tarayıcıda uçtan uca doğrulama yapıldı:
  `/profile` sayfasında "Push Bildirimleri → Etkinleştir" tıklandı,
  gerçek bir FCM (Google push servisi) subscription oluştu
  (`Notification.permission="granted"`, gerçek
  `https://fcm.googleapis.com/fcm/send/...` endpoint'i), `POST /push/
  test` gerçek `{"sent":1,"expired":0,"failed":0}` döndü, ve kullanıcı
  gerçek makinesinde OS bildirimini gördüğünü doğruladı.

### 5. Backup-restore — otomatik doğrulama VAR, gerçek felaket tatbikatı YOK

`infrastructure.db_backup_verify` Celery task'ı her gece 01:00 UTC
`DatabaseBackupManager.verify_backup_restorable()` ile otomatik restore
testi yapıyor (2026-06-12'de eklendi, `v2/modules/platform_infra/
background/backup_tasks.py:48` — doğrulandı, kodda gerçekten var). Ama bu
"aynı host'ta otomatik bir doğrulama" — **gerçek bir felaket senaryosu**
(host'un tamamen kaybedilip yedekten SIFIRDAN bir ortamda ayağa
kaldırılması) hiç tatbik edilmedi. Backlog: yılda/çeyrekte bir gerçek
DR tatbikatı planlanmalı (ayrı bir host/VM'de yedekten restore + stack'i
ayağa kaldırma + smoke test).

### 6. KVKK — hâlâ TASLAK, hukuk onayı bekliyor

`docs/kvkk/README.md` (doğrulandı, 2026-07-30): dosyanın başında hâlâ
**"TASLAK — hukuki inceleme gerekir"** uyarısı var; ana kayıt + denetim
izi saklama süreleri "hukuk onayı bekliyor" diye işaretli. Bu kod
değişikliği gerektiren bir iş değil — kullanıcının (veya şirketin) bir
hukuk danışmanına bu taslağı onaylatması gerekiyor. Onay gelince
saklama sürelerinin kod tarafında (retention task'ları) zaten uygulanan
değerlerle (analitik 90g + yedek 30g) eşleşip eşleşmediği kontrol
edilmeli.

### 7. Dış uptime izleme — hiç kurulmamış

`docs/operations/runbook.md:22` yalnız bir ÖNERİ olarak "UptimeRobot /
healthchecks.io `/health/liveness`'e bağlanır" diyor — gerçek bir hesap
açılıp bağlandığına dair hiçbir iz yok (doğrulandı, 2026-07-30). Backlog:
kullanıcı bir servis seçip (UptimeRobot, healthchecks.io, Better Uptime
vb. — ücretsiz katmanlar yeterli) `/health/liveness` endpoint'ini
izlemeye alsın; bu tamamen dış-servis/hesap işi, kod değişikliği
gerektirmiyor.

### 8. OCR + Telegram servisleri — Python 3.11'de kalmış, 3.12'ye taşınmadı ✅ TAMAMLANDI (2026-07-30)

Doğrulandı (2026-07-30): ana backend `Dockerfile` → `python:3.12-slim`,
ama `ocr_service/Dockerfile` ve `telegram_bot/Dockerfile` ikisi de hâlâ
`python:3.11-slim` (digest-pinned, 2026-06-17 tarihli). Bu, 2026-06-18
"tertemiz kurulum" oturumunda bilinçli bırakılmıştı: EasyOCR/torch
wheel'lerinin 3.12 uyumluluğu doğrulanmadığı için risk alınmadı
([[docker_clean_rebuild_2026]]).

**Tamamlandı:**
- `telegram_bot/Dockerfile` → 3.12-slim (sıfıra yakın riskti, doğrulandı).
  Aynı dalgada kullanıcı isteğiyle bot kodunda 8 gerçek bug bulunup
  düzeltildi (`/yeniden_baslat` hiç çalışmıyordu, blocking I/O, sessiz
  except, sıfır test, yanlış `:ro` mount güvenlik varsayımı, ~40 gereksiz
  `type: ignore`, test-isolation sızıntısı).
- `telegram_bot/` + `ocr_service/` → `v2/services/telegram_bot/` +
  `v2/services/ocr_service/` altına taşındı (kullanıcı isteği, repo kökü
  düzeni), her ikisine modül-tarzı `CLAUDE.md` eklendi.
- `ocr_service/Dockerfile` → 3.12-slim: izole bir dalda (`test/ocr-
  python312`) gerçek `docker build` denendi — `easyocr==1.7.1`'in
  transitive bağımlılıkları (torch/torchvision/opencv-python-headless/
  numpy, hiçbiri pin'li değil) sorunsuz cp312 wheel'leri çözdü. Gerçek
  görsel testi: sentetik bir "YAKIT FİŞİ / LİTRE: 45.20 / TUTAR: 850.00
  TL" görseli hem 3.12 test container'ına hem çalışan 3.11 container'ına
  POST edildi — çıktı birebir aynı (`ham_metin` + `yapilandirilmis`
  dict). Gerçek servis yeniden inşa edilip doğrulandı (Python 3.12.13,
  `/health` → `model_loaded: true`).
- Ayrıca bu dalgada Item A'nın (FAZ2 Celery rol wiring) kendi CI'ında
  bulunan 4 gerçek bug da düzeltildi: Celery sinyal bağlantıları
  `weak=True` varsayılanıyla dead-weakref'e dönüşüyordu (rol kısıtlaması
  hiç uygulanmıyordu), + `m_import_excel`/`m_fuel`/`m_notification`/
  `m_anomaly`/`m_prediction_ml` grant açıkları (biri haftalardır var olan
  bir şema yanlış-etiketlemesiydi — `sistem_konfig` "admin_platform" değil
  "platform" şemasında).
- CI hard-gates main'de yeşil (coverage ≥92%, sıfır test hatası).

## Önceki konuşmada "sonraya bırakalım" denen konu — BULUNAMADI

Kullanıcı bu oturumda ayrıca "konuşma içinde sonraya bırakalım dediğim
başka bir konu vardı" dedi. Mevcut hafıza kayıtlarında ve bu oturumun
(compaction sonrası) özetinde buna karşılık gelen açık bir referans
bulunamadı — muhtemelen compaction'da özetlenmeyen bir ayrıntı. Kullanıcıya
hangi konu olduğu sorulmalı, tahmin yürütülmemeli.
