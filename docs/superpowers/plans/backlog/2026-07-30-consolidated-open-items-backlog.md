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

### 1. Segment-tractive fizik modeli — flag flip kararı bekliyor

`app/config.py:247` — `USE_SEGMENT_TRACTIVE_MODEL: bool = False`
(doğrulandı, 2026-07-30 itibarıyla hem dev hem prod compose dosyalarında
hiç set edilmemiş, hâlâ kapalı). Son gerçek dokunuş `2026-06-14`
(offline validasyon, Open-Meteo kotasından bağımsız depolanmış geometri
ile koşul-nötr **9/10 GREEN**). O tarihten beri:
- **Canlı p51 validasyonu** (`scripts/p51_real_world_validation.py`,
  gerçek Mapbox+Open-Meteo çağrılarıyla) flag AÇIKKEN hiç tekrar
  koşulmadı.
- **ML ensemble retrain** flag'in etkilediği fizik-tabanlı feature'lar
  için hiç yapılmadı.

**Sıradaki adım**: flag'i `true` yapmadan önce (a) Open-Meteo günlük
kotası müsaitken `P51_PACE_SECONDS=90` ile canlı p51'i flag=true ile
koş, ≥8/10 GREEN'i doğrula; (b) sonucu kullanıcıya raporla, flip kararını
onaylat; (c) onaylanırsa `docker-compose.prod.yml`'a env ekle + ML
retrain'in gerekip gerekmediğine karar ver.

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

### 8. OCR + Telegram servisleri — Python 3.11'de kalmış, 3.12'ye taşınmadı

Doğrulandı (2026-07-30): ana backend `Dockerfile` → `python:3.12-slim`,
ama `ocr_service/Dockerfile` ve `telegram_bot/Dockerfile` ikisi de hâlâ
`python:3.11-slim` (digest-pinned, 2026-06-17 tarihli). Bu, 2026-06-18
"tertemiz kurulum" oturumunda bilinçli bırakılmıştı: EasyOCR/torch
wheel'lerinin 3.12 uyumluluğu doğrulanmadığı için risk alınmadı
([[docker_clean_rebuild_2026]]). Backlog: bu iki servisi 3.12'ye
taşımadan önce EasyOCR + torch'un 3.12 wheel'lerinin gerçekten var
olup olmadığı araştırılmalı (PyPI'da uyumlu wheel yoksa taşıma
riskli/imkânsız olabilir); varsa izole bir dalda deneme build'i +
gerçek OCR/Telegram smoke testi ile doğrulanmalı.

## Önceki konuşmada "sonraya bırakalım" denen konu — BULUNAMADI

Kullanıcı bu oturumda ayrıca "konuşma içinde sonraya bırakalım dediğim
başka bir konu vardı" dedi. Mevcut hafıza kayıtlarında ve bu oturumun
(compaction sonrası) özetinde buna karşılık gelen açık bir referans
bulunamadı — muhtemelen compaction'da özetlenmeyen bir ayrıntı. Kullanıcıya
hangi konu olduğu sorulmalı, tahmin yürütülmemeli.
