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

**Ayrı iş olarak planlandı (kullanıcı kararı, 2026-07-30)**: tek-günlük
fit'e güvenmeden **birden fazla günün** canlı geometri verisiyle
(farklı trafik/hava koşulları) kalibrasyonu tekrarlamak ve ortalamasını
almak — periyodik (haftalık?) bir "recalibration job" olarak
otomatikleştirmek de düşünülebilir. Bu iş birden fazla günün Open-Meteo
kotasını gerektirdiği için ayrı, kendi başına bir görev — bu backlog
dalgasının kapsamı dışında bırakıldı.

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

Epik fiilen durmuş durumda; `route_location_zero_mock_2026_07` planının
(Route/Location domain'i tam bitirme + `api_stub/` altyapısı) o oturumdan
sonra ne kadar ilerlediği bu backlog yazılırken doğrulanmadı — bir
sonraki oturumda o planın gerçek dosyalarına (`api_stub/`, dönüştürülen
test dosyaları) bakıp güncel % ilerleme ölçülmeli, sonra kapsam/öncelik
kararı kullanıcıya sorulmalı.

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

### 4. VAPID push bildirimleri — gerçek tarayıcıda hiç denenmedi

Push altyapısı (subscribe/unsubscribe/sender/410-cleanup + 3 tetikleyici:
kritik anomali, muayene, weekly digest) kodda tam kurulu, ama teslim ucu
(VAPID anahtar üretimi + `.env`'e `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/
`VAPID_SUBJECT`/`PUSH_NOTIFICATION_ENABLED=true` + gerçek bir tarayıcıda
"izin ver" diyalogundan geçip bildirim gelip gelmediğini görme) otomatize
edilemeyen manuel bir adım — hiç yapılmadı. Sıradaki adım: VAPID anahtar
çiftini üret (`web-push generate-vapid-keys` veya eşdeğeri), `.env`'e
ekle, gerçek bir tarayıcıda push izni verip bir test bildirimi tetikleyip
doğrula.

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
