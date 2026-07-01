# LojiNext — Prod-Grade Mühendislik Denetimi (Birleşik Rapor)

**Tarih:** 2026-07-01
**Kapsam:** 23 bağımsız derin denetim ajanı (9 SaaS-lens + 12 bug/eksik/refactor/sınır-ihlali odaklı + 2 tamamlık-doğrulama turu), tamamı gerçek kod okumasıyla, file:line kanıtlı. Multi-tenancy/billing bu turda kullanıcı talimatıyla kapsam dışı bırakıldı (önceki tur ayrı bir bakış olarak saklı — bkz. konuşma geçmişi, SaaS-lens denetim).
**Yöntem:** Her bulgu gerçek dosya/satır referansı taşır; doğrulanamayan noktalar "Şüpheli" olarak işaretlenmiştir. Sıfır mock/hayali bulgu — hiçbir madde varsayımla üretilmedi.
**Uygulama durumu:** Denetimin ardından, aşağıda **✅ DÜZELTİLDİ** işaretli maddeler TDD ile (önce kırmızı test, sonra fix, sonra yeşil doğrulama) gerçekten kodda düzeltildi ve bağımsız bir code-review turundan geçirildi — detay için bkz. "Uygulanan Düzeltmeler — Neden/Sonuç" bölümü.

---

## P0 — Üretimde aktif kırılma/veri kaybı riski (acil)

| # | Bulgu | Kanıt | Tip | Durum |
|---|---|---|---|---|
| 1 | `BaseRepository.get_by_id` soft-delete filtresi uygulamıyor. **62 gerçek çağrı noktası tek tek incelendi** (bkz. "Ek: 62 Çağrı Noktasının Tam Sınıflandırması") — 16'sı gerçek bug, 12'si başka bir kontrolle zaten korunuyor, 30'u zararsız-ama-tutarsız, 4'ü N/A/ölü kod. En kritikleri: `maintenance_service.py:107,113` (pasif araç/dorseye bakım/arıza kaydı açılabiliyor), `arac_service.py:195` (update endpoint'i reaktivasyon-akışını bypass ediyor) | `app/database/base_repository.py:207-222` | **Bug** | ✅ **DÜZELTİLDİ** |
| 1b | `sefer_write_service.py:281` (update) ve `:402` (create) — soft-deleted/pasif bir `guzergah_id` seçilirse `LokasyonRepository.get_by_id` filtresizliği nedeniyle eski/silinmiş mesafe-koordinat verisi doğrudan canlı yakıt tahminine (`pred_service.predict_consumption`) beslenir ve kalıcı sefer kaydına yazılır — CLAUDE.md'nin işaret ettiği tahmin-doğruluğu riskinin doğrudan kaynaklarından biri | `app/core/services/sefer_write_service.py:281,402` | **Bug** | ✅ **DÜZELTİLDİ** (kök fix #1 ile) |
| 2 | `Arac.yas_faktoru` — `yil=None` olan her araçta `TypeError` ile 500 patlıyor (Excel import'ta üretim yılı boş bırakılan araçlarda garanti) | `app/core/entities/models.py:174-188` | **Bug** | ✅ **DÜZELTİLDİ** |
| 3 | `investigations.py` (571 satır) ve `locations.py` (626 satır) hiçbir servis katmanı kullanmıyor — iş mantığı + ham SQL doğrudan endpoint içinde | `app/api/v1/endpoints/investigations.py`, `locations.py` | **Sınır İhlali** | Açık (büyük refactor, bu turda kapsam dışı bırakıldı — bkz. Yol Haritası #2) |
| 4 | Celery backfill: broker `visibility_timeout=120s` < task `soft_time_limit=600s` → görev zaman aşımına uğramadan önce başka worker'a tekrar dağıtılıyor; claim/lock yok → aynı sefer iki kez işleniyor, çift Mapbox/Open-Meteo maliyeti + duplike `route_simulations` satırı | `celery_app.py:29-34`; `prediction_backfill_tasks.py:14-23`; `prediction_backfill_service.py:64-100` | **Bug** | ✅ **DÜZELTİLDİ** |
| 5 | OCR servisi `easyocr.readtext` çağrısına timeout yok — ağır görüntü thread-pool'u tüketip servisi DoS'a düşürebilir | `ocr_service/ocr_processor.py:13-14` | **Bug** | ✅ **DÜZELTİLDİ** |
| 6 | Round-trip sefer güncellemesinde dönüş seferi oluşturma başarısız olursa exception yutuluyor, çağıran "başarılı" döner — kullanıcı dönüş seferinin oluştuğunu sanır, oluşmamıştır | `app/core/services/sefer_write_service.py:658-701` | **Bug** | ✅ **DÜZELTİLDİ** |
| 7 | IDOR güvenlik testi (`test_idor_notifications.py`) seed admin kullanıcı yoksa **sessizce skip** ediliyor — CI'da seed garantisi yoksa kritik bir yetkilendirme testi hiç çalışmamış olabilir | `app/tests/security/test_idor_notifications.py:35-37` | **Bug/Eksik** | ✅ **DÜZELTİLDİ** |
| 8 | Dashboard "Bugünün Aktif Seferleri" widget'ı Türkçe durum sözlüğü kullanıyor, backend kanonik İngilizce string döndürüyor (`"Planned"` vb.) → her satırda çeviri kaybolur, renksiz/gri rozet. Aynı dosyada `TripTable.tsx` doğru çözücüyü zaten kullanıyor, bu widget'a uygulanmamış | `frontend/src/components/dashboard/TodaysActiveTrips.tsx:20-30,90` vs `app/schemas/sefer.py:29-34` | **Bug** | ✅ **DÜZELTİLDİ** |
| 9 | Yüklenen belgeler + ML model dosyaları (.pkl) yalnız Docker named volume'de — gerçek multi-host/yeniden-zamanlanan dağıtımda veri kaybolur/diverge eder | `app/core/services/internal_service.py:65-68`, `ensemble_core.py:1189-1282` | **Eksik (mimari)** | Açık |

---

## Uygulanan Düzeltmeler — Neden / Sonuç (2026-07-01, ikinci tur)

Kullanıcı talimatıyla, yukarıdaki tablonun **✅ DÜZELTİLDİ** işaretli maddeleri + Excel formula injection (P1) kapatıldı. Her madde için: **Neden** (kök sebep — bu bug neden vardı), **Sonuç** (ne değişti, hangi dosyalar), **Doğrulama** (nasıl kanıtlandı). Kapsam dışı bırakılanlara (P0 #3,4,5,7,8,9 ve P1/P2/P3'ün geri kalanı) dokunulmadı — kullanıcı talimatı gereği yalnız listelenen maddeler işlendi.

### 1. Kök neden — `BaseRepository.get_by_id` soft-delete filtresizliği (P0 #1, #1b + 16 alt-bug)

**Neden:** `get_by_id` hiçbir zaman `aktif`/`is_deleted` alanına bakmıyordu (`session.get(self.model, id)` — çıplak PK sorgusu). `get_all`/`count` gibi kardeş metodlar zaten filtreliyordu; `get_by_id` bu sözleşmenin dışında kalmıştı. Sonuç: soft-delete edilmiş bir araç/şoför/dorse/lokasyon/yakıt kaydı, "var mı?" kontrolünden sessizce geçip yazma işlemlerine (bakım kaydı açma, skor güncelleme, sefer route enrichment) girebiliyordu.

**Sonuç:**
- `app/database/base_repository.py` — `get_by_id`'ye `include_inactive: bool = False` parametresi + model'de `aktif`/`is_deleted` varsa otomatik filtre eklendi (`for_update` yolu dahil).
- `app/database/repositories/sefer_repo.py` — kendi override'ı da aynı `include_inactive` sözleşmesine uyacak şekilde güncellendi (mypy imza uyumu için de gerekliydi).
- **7 "kasıtlı" `include_inactive=True` işaretlemesi** eklendi (kök fix'in aksi halde kırdığı meşru akışlar): `arac_service.py:251` (smart-delete 2. aşama), `lokasyon_service.py:236` (aynı desen), `sofor_service.py:182` (idempotent silme guard'ı), `yakit_service.py:221` (hard-delete pasif kaydı da silebilmeli), `vehicles.py:145`/`trailers.py:156`/`user_service.py:62` ("az önce oluşturulan kaydı geri oku").
- **16 gerçek-bug çağrı noktasının 12'si** kök fix'in kendisiyle otomatik düzeldi (zaten `if not X: raise 404` gibi bir kontrol vardı, sadece filtre eksikti): `maintenance_service.py:64,107,113`, `sofor_service.py:212`, `driver_coaching_engine.py:80`, `prediction_service.py:645`, `trip_planner.py:255,289`, `lokasyon_service.py:310`, `sefer_write_service.py:281,402`, `route_calibration_service.py:37`, `yakit_service.py:194`.
- **2 site ek kod değişikliği gerektirdi** (kök fix yetmedi çünkü `update()` çağrısı `get_by_id`'nin sonucundan bağımsız çalışıyordu — filtre "var mı" kontrolünü düzeltti ama update'i gate'lemiyordu): `arac_service.py:195` (`_update_arac_impl`) ve `sofor_service.py:158` (`update_sofor`) — ikisine de "reaktivasyon-farkında guard" eklendi: `get_by_id` None dönerse (pasif kayıt), yalnızca payload'da açıkça `aktif=True` varsa `include_inactive=True` ile tekrar okunup işleme devam ediliyor; aksi halde `return False` (404'e denk).

**Doğrulama:** `test_base_repository.py`'ye 4 yeni test (varsayılan filtre, `for_update` filtresi, `include_inactive` bypass, aktif kayıt etkilenmez). Yeni dosyalar: `test_maintenance_service_soft_delete.py` (5), `test_sofor_service_soft_delete.py` (4), `test_yakit_service_soft_delete.py` (3). `test_arac_service_reactivate.py`'ye 3, `test_sefer_write_service_coverage.py`'ye 4 test eklendi. Her biri git-stash ile fix geçici geri alınıp önce **kırmızı** (bug gerçekten üretiliyor) sonra **yeşil** (fix çalışıyor) olarak kanıtlandı.

### 2. `Arac.yas_faktoru` — `yil=None` TypeError (P0 #2)

**Neden:** `yas_faktoru` computed_field, `self.yas`'ı (yil=None ise None döner) hiç None-kontrolü yapmadan `if yas <= 2:` karşılaştırmasına sokuyordu.

**Sonuç:** `app/core/entities/models.py` — `yas is None` durumunda nötr fallback `1.0` (5 yıllık baseline'a eşdeğer) dönecek şekilde guard eklendi.

**Doğrulama:** `test_entities/test_arac_yas_faktoru.py` (5 yeni test) — `yil=None`'da hem `.yas_faktoru` erişiminin hem tam `model_dump()` serileştirmesinin patlamadığı + yaş-bantlarının doğru hesaplandığı kanıtlandı. Kırmızı-yeşil doğrulandı.

### 3. Round-trip sefer güncellemesinde sessiz exception yutma (P0 #6)

**Neden:** `_handle_round_trip_on_update`, dönüş seferi oluşturma adımının tamamını (hem `SeferCreate(...)` validasyonunu hem `_create_return_trip` çağrısını) tek bir `except Exception: logger.error(...)` ile sarmalıyordu — hem gerçek altyapı hataları hem de kaynak verinin yapısal validasyon hataları aynı şekilde sessizce yutuluyordu. `update_sefer` yine de `True` dönüyor, kullanıcı dönüş seferinin oluştuğunu sanıyordu.

**Sonuç:** `app/core/services/sefer_write_service.py` — iki kategori ayrıştırıldı:
- `SeferCreate(...)` inşası sırasında **yalnızca** `pydantic.ValidationError` yakalanıp loglanır ve sessizce atlanır (bu, kaynak `current_sefer` kaydının kendisinin yapısal olarak round-trip mirror'ına uygun olmaması durumudur — ör. `mesafe_km=0`, tek karakterlik `cikis_yeri` — kullanıcının şu anki işlemiyle ilgisizdir, ana update'i bozmamalıdır).
- `_create_return_trip`'in kendisinden gelen **her türlü hata artık propagate edilir** — try/except'e hiç girmez, `_update_sefer_uow`'un kendi dış except/raise zincirine yükselip transaction'ı (henüz commit edilmemiş) rollback'e götürür ve caller'a görünür olur.

**Doğrulama:** İlk fix (blanket propagate) tam paket taramasında `test_sefer_write_more2.py`'deki **2 mevcut testi kırdı** (`test_handle_round_trip_on_update_edge_data_skips_gracefully`, `..._short_place_name_skips_gracefully`) — bunlar bilinçli olarak "yapısal geçersiz kaynak veri → sessizce atla" davranışını kilitliyordu. `ValidationError`'a daraltılmış ikinci fix ile hem bu 2 eski test hem yeni `test_update_sefer_round_trip_failure_is_not_silently_swallowed` testi (gerçek `_create_return_trip` hatasının artık propagate ettiğini kanıtlar) birlikte yeşil. Üç ayrı durum (orijinal kod / blanket-propagate ara durum / daraltılmış nihai fix) tek tek kırmızı-yeşil doğrulandı.

### 4. Excel/CSV formula injection (P1, kullanıcı talimatıyla ek kapsam)

**Neden:** (a) `excel_exporter.py`'deki iki `ExcelWriter`, xlsxwriter'ın varsayılan `strings_to_formulas=True` davranışını değiştirmiyordu — `"="` ile başlayan herhangi bir string hücre otomatik olarak çalıştırılabilir formüle dönüşüyordu. (b) Excel import parser'ları (`notlar`/`marka`/`model`/`ad_soyad`/`dorse_tipi`) serbest metin alanlarını hiç sanitize etmiyordu.

**Sonuç:**
- `app/core/services/excel_exporter.py` — her iki `ExcelWriter`'a `engine_kwargs={"options": {"strings_to_formulas": False}}` eklendi.
- `app/core/services/excel_parser.py` — `_sanitize_formula_prefix` helper'ı eklendi, `notlar`/`marka`/`model`/`ad_soyad`/`dorse_tipi` alanlarına uygulandı. **`telefon`/`ehliyet_sinifi` bilinçli olarak hariç tutuldu** (bkz. madde 5).
- `app/core/services/export_service.py` — derin kontrol turunda bulunan **ikinci, daha önce hiç raporlanmamış** aynı-sınıf zafiyet (`ws["A1"] = title`, ham openpyxl `Workbook()` kullanıyor, aynı otomatik-formül davranışı) de kapatıldı. Bu metod (`export_to_excel`) şu an hiçbir endpoint'ten çağrılmıyor (ölü kod) ama aynı zafiyet sınıfını taşıdığı için kullanıcı onayıyla düzeltildi.

**Doğrulama:** `test_excel_exporter_coverage.py`, `test_excel_parser_coverage.py`, `test_export_service_coverage.py`'ye toplam 10 yeni test — gerçek `.xlsx` byte'ları üretilip `openpyxl.load_workbook` ile geri okunarak hiçbir hücrenin `data_type == 'f'` (formül) olmadığı doğrulandı. Kırmızı-yeşil doğrulandı.

### 5. Derin kontrol turunda bulunan ve düzeltilen ek regresyonlar (kendi fix'lerimin yan etkileri)

Bu maddeler orijinal denetimde yoktu — "derin kontrol et" talimatıyla yapılan bağımsız code-review + tam paket regresyon taraması sırasında **kendi fix'lerimin** ürettiği 3 yan etki bulundu ve kapatıldı:

- **`telefon` alanının formula-sanitize listesine yanlışlıkla girmesi** — Türk telefon numaraları rutin olarak `+90...` ile başladığı için gerçek veri `'+90...` olarak bozulurdu (madde 4'ün import-sanitize kısmının aşırı geniş kapsamı). Bağımsız code-review ajanı buldu; `telefon`/`ehliyet_sinifi` sanitize kapsamından çıkarıldı.
- **mypy imza uyumsuzluğu** — `include_inactive` parametresi `BaseRepository.get_by_id`'ye eklenince `SeferRepository.get_by_id`'nin override imzası uyumsuz hale geldi (mypy soft-baseline 7→8 olurdu). `sefer_repo.py`'ye aynı parametre eklenip baseline'a (7 hata, hepsi önceden var olan) geri dönüldü.
- **Round-trip regresyon** — madde 3'te detaylandırıldı; tam paket taramasının (5144 test) bu 2 testi yakalaması sayesinde bulundu, aksi halde ilk "tamamlandı" raporunda gözden kaçmış olacaktı.

**Ders:** Hedefli test dosyalarını çalıştırmak yeterli değildi — sadece **tüm `app/tests/unit` paketinin** (2000+ dosya) çalıştırılması bu round-trip regresyonunu ortaya çıkardı. Bu yüzden nihai doğrulama her zaman tam paket taramasıyla kapatıldı.

### 6. IDOR güvenlik testinin sessiz skip'i (P0 #7) — 2026-07-01, üçüncü tur

**Neden:** Ampirik olarak doğrulandı (`pytest -v` → `1 skipped`) — test üç ayrı nedenle hiçbir zaman gerçek koruma sağlamıyordu: (a) `Kullanici.id == 1`'in var olduğunu varsayıyordu, taze test şemasında hiçbir fixture bunu garanti etmiyordu → sessiz skip; (b) `auth_headers` fixture'ı normal kullanıcı değil, sentetik id'li break-glass süper-admin token'ı üretiyordu — gerçek bir peer-to-peer IDOR senaryosunu test etmiyordu; (c) istek URL'i yanlıştı (`/api/v1/notifications/...` yerine gerçek mount noktası `/api/v1/admin/notifications/...`) — test çalışsaydı bile muhtemelen "route yok → 404" ile yanlış sebepten PASS olurdu.

**Sonuç:** `app/tests/security/test_idor_notifications.py` tamamen yeniden yazıldı — artık iki bağımsız gerçek kullanıcıyı (owner + attacker) kendi içinde oluşturuyor (hiçbir dış seed'e bağımlı değil, asla skip olmaz), attacker'ın gerçek login token'ıyla doğru URL'e istek atıyor, ve status-code kontrolüne ek olarak bildirimin DB'de gerçekten okunmamış kaldığını da doğruluyor (pozitif kontrol). Altta yatan `NotificationRepository.mark_as_read_for_user` ownership-filtresi (`app/database/repositories/notification_repository.py:49-64`) okunup gerçekten `WHERE id=... AND kullanici_id=...` ile filtrelediği doğrulandı — üretim kodu zaten güvenliydi, sorun yalnızca testin kendisindeydi.

**Doğrulama:** Düzeltme öncesi `pytest -v` çıktısı `1 skipped` (kanıt). Düzeltme sonrası `1 passed`, skip yok. `app/tests/security/` tam dizini (34 test) yeşil. `ruff check` temiz.

### 7. OCR servisi timeout eksikliği (P0 #5) — 2026-07-01, üçüncü tur

**Neden:** `OcrProcessor.process()`, `easyocr.Reader.readtext`'i `asyncio.to_thread` ile sarmalıyordu ama hiçbir üst sınır uygulamıyordu — CPU-only easyocr'da yüksek-çözünürlüklü/karmaşık bir görüntü dakikalarca sürebilir; art arda birkaç ağır istek thread-pool'u tüketip servisi fiilen DoS'a düşürür.

**Sonuç:** `ocr_service/ocr_processor.py` — `asyncio.wait_for(..., timeout=_OCR_TIMEOUT_SECONDS)` eklendi (env-configurable, varsayılan 30s), zaman aşımında `TimeoutError` fırlatır. `ocr_service/main.py` — bu `TimeoutError`'ı yakalayıp HTTP 504'e çevirir. Not: `asyncio.wait_for` alttaki OS thread'ini zorla öldüremez (Python thread'leri iptal edilemez) — bu, "istek sonsuza dek asılı kalır" riskini "istek zamanında 504 alır, thread pool eninde sonunda kendini toparlar" haline getirir; gerçek hard-kill için multiprocessing gerekir (kapsam dışı).

**Doğrulama:** `ocr_service/tests/test_ocr_processor_timeout.py` (yeni, 2 test) — `easyocr` paketi bu ortamda kurulu olmadığından (`sys.modules` stub'ı ile modül-seviyesi import atlatıldı) sahte yavaş/hızlı `readtext` fonksiyonlarıyla test edildi. Kırmızı-yeşil doğrulandı (fix öncesi `AttributeError: no attribute '_OCR_TIMEOUT_SECONDS'`, fix sonrası 2/2 geçti). `ruff check ocr_service` temiz.

### 8. Celery backfill visibility_timeout uyuşmazlığı (P0 #4) — 2026-07-01, üçüncü tur

**Neden:** Redis broker `visibility_timeout` **tüm task'lar için tek bir global değerdir** (per-task override edilemez). Kod okunup teyit edildiğinde, sorunun raporda belirtilenden daha geniş olduğu ortaya çıktı: sadece `prediction.backfill_missing` (600/660s) değil, `coaching_tasks.py`'deki haftalık digest task'ı da **3600/3900s** (65 dakika!) `time_limit` taşıyordu — eski `visibility_timeout=120s` her ikisinin de çok altındaydı. Herhangi bir uzun task normal süresi içinde bitmeden broker onu "kayıp" sayıp başka bir worker'a yeniden dağıtıyordu.

**Sonuç:**
- `app/infrastructure/background/celery_app.py` — `visibility_timeout` 120 → **4200s** (en uzun task'ın (3900s) üzerinde marjlı).
- `app/core/services/prediction_backfill_service.py` — ikincil savunma: yazma öncesi sefer'in `tahmini_tuketim` alanı zaten doluysa (başka bir worker doldurmuşsa) dış IO (Mapbox/Open-Meteo) çağrısı yapılmadan atlanır — visibility_timeout dışındaki senaryolarda (worker crash/restart) da duplike yazımı/maliyeti önler.

**Doğrulama:** `app/tests/unit/test_infrastructure/test_celery_app_config.py` (yeni) — `app/workers/tasks/*.py` dosyalarını tarayıp tüm `time_limit=` değerlerinin `visibility_timeout`'un altında kaldığını doğrular (gelecekte biri daha uzun bir task eklerse bu test yakalar — regresyon guard'ı). `test_prediction_backfill_service.py`'ye 1 yeni test (`test_backfill_skips_sefer_already_filled_by_another_worker`). Kırmızı-yeşil doğrulandı — fix öncesi celery config testi `assert 120 > 3900` ile FAIL etti (kanıt), backfill testi de `filled=1` yerine beklenen `skipped=1`'i doğrulayamadı. `app/tests/unit/test_workers/` + `test_monitoring/` (341 test) yeşil.

### 9. Dashboard TR/EN durum çevirisi (P0 #8) — 2026-07-01, üçüncü tur

**Neden:** `TodaysActiveTrips.tsx`'teki `TURKISH_STATUS_META` sözlüğü Türkçe anahtarlarla (`Planlandı`/`Yolda`/`Tamamlandı`/`İptal`) tanımlıydı, ama backend `app/schemas/sefer.py:29-34`'teki `TripStatus` enum'u (DB CHECK constraint ile birebir) yalnız 3 kanonik İngilizce değer döner: `Planned`/`Completed`/`Cancelled` — "Yolda" (in-progress) durumu DB'de hiç yok (ölü kod olarak zaten kaldırılmış). Sözlük anahtarları hiçbir zaman gerçek backend değerleriyle eşleşmiyordu → her satırda `?? {label: durum, variant:"neutral"}` fallback'ine düşüp ham İngilizce string'i renksiz rozette gösteriyordu. Aynı dosyada zaten kullanılan `TripTable.tsx` doğru çözücüyü (`normalizeTripStatus` + `getTripStatusMeta`) kullanıyordu, bu widget'a hiç uygulanmamıştı.

**Sonuç:** `frontend/src/components/dashboard/TodaysActiveTrips.tsx` — `TURKISH_STATUS_META` sözlüğü tamamen kaldırıldı; `TripTable.tsx`'in zaten kullandığı `normalizeTripStatus` (`lib/trip-status.ts`) + `getTripStatusMeta` (`lib/status-labels.ts`) kombinasyonunu kullanan `tripStatusMetaFor()` yardımcı fonksiyonu eklendi — bilinmeyen bir durum değeri için hâlâ nötr fallback korunuyor.

**Doğrulama:** `frontend/src/components/dashboard/__tests__/TodaysActiveTrips.test.tsx` (yeni, 2 test) — üç kanonik durumun doğru Türkçe etikete çevrildiğini VE ham İngilizce string'in ekranda kalmadığını (regresyon guard'ı) doğrular + bilinmeyen durum için fallback testi. Kırmızı-yeşil doğrulandı (fix öncesi ekranda ham `"Cancelled"` görünüyordu, `"İptal"` değil — DOM dump ile kanıtlandı). `eslint` + `tsc --noEmit` temiz. `frontend/src/components/dashboard/` + `trips/` dizinleri (17 dosya, 123 test) yeşil.

### 10. Break-glass süper-admin rate-limiting (P1, Dalga 2 madde 1) — 2026-07-01, üçüncü tur

**Neden:** `POST /auth/token`'daki break-glass süper-admin girişi, tüm endpoint'e uygulanan genel `auth_token` bucket'ını (5 req/s — normal kullanıcı trafiği için tasarlanmış) paylaşıyordu. `secrets.compare_digest` zamanlama saldırısına karşı korur ama deneme SAYISINI sınırlamaz — saniyede birkaç kez `SUPER_ADMIN_PASSWORD` denenebiliyordu.

**Sonuç:** Kullanıcıya soruldu — tam MFA (TOTP/OTP) yeni bağımlılık+enrollment akışı gerektiren ayrı bir tasarım kararı olduğu için kullanıcı **"sadece sıkı rate-limit ekle"** seçeneğini onayladı; MFA/IP-allowlist ayrı bir epik olarak bırakıldı. `app/api/v1/endpoints/auth.py` — süper-admin kullanıcı adıyla yapılan HER deneme (şifre doğru/yanlış fark etmeksizin) artık ayrı, çok daha sıkı bir bucket'tan (`super_admin_login`, 5 dakikada 3 deneme) geçiyor — genel `auth_token` bucket'ına ek olarak.

**Doğrulama:** `app/tests/api/test_auth_coverage.py`'ye 2 yeni test: (1) 3 denemeden sonra 4. denemenin 429 döndüğünü doğrular, (2) normal kullanıcı girişinin bu yeni sıkı limitten etkilenmediğini doğrular. Kırmızı-yeşil doğrulandı (fix öncesi 4. deneme 401 dönüyordu, 429 değil). `ruff`+`mypy` temiz (baseline korunuyor). `app/tests/security/` + `test_auth_coverage.py` + `test_users.py` (60 test) yeşil.

### 11. Rate-limit middleware fail-open → fail-closed (P1, Dalga 2 madde 2) — 2026-07-01, üçüncü tur

**Neden:** `app/api/middleware/rate_limiter.py` — `slowapi` import edilemezse (`ImportError`), modül sessizce `_NoopLimiter()`'a düşüyordu; bu limiter'ın `.limit(...)` decorator'ı hiçbir şey yapmadan fonksiyonu olduğu gibi döndürüyor. Tek uyarı bir `_log.critical(...)` satırıydı — uygulama yine de tamamen rate-limit'siz şekilde ayağa kalkıp trafik almaya devam ediyordu (fail-open).

**Sonuç:** Karar mantığı test edilebilir bir `_build_limiter(environment, rate_limit_enabled)` fonksiyonuna çıkarıldı. `environment == "prod"` VE slowapi yoksa artık `RuntimeError` fırlatılıp **uygulama başlamayı reddediyor** (fail-closed) — `app/config.py`'deki diğer prod-only startup validator'larıyla (CORS, ADMIN_PASSWORD) aynı desen. Dev/test'te (slowapi'nin her ortamda kurulu olmayabileceği hafif geliştirme ortamları) eski fail-open + critical log davranışı korunuyor — yerel geliştirmeyi bloklamıyor.

**Doğrulama:** `app/tests/unit/test_coverage_boost.py`'deki `TestRateLimiterModule`'e 3 yeni test: prod'da `RuntimeError`, dev'de `_NoopLimiter` fallback, slowapi mevcutken normal davranış. Kırmızı-yeşil doğrulandı (fix öncesi `_build_limiter` fonksiyonu hiç yoktu — `AttributeError`). `ruff`+`mypy` temiz. `test_coverage_boost.py` + `test_system_coverage.py` (117 test) yeşil.

### 12. Failed login / 403 → admin_audit_log (P1, Dalga 2 madde 3) — 2026-07-01, üçüncü tur

**Neden:** (a) `auth_service.py`'de başarısız giriş denemeleri sadece `logger.warning(...)` (dosya log) — `admin_audit_log`'a hiç yazılmıyordu. (b) 403 izin reddi hiçbir yerde audit'e düşmüyordu — `security_service.py`'nin `verify_permission`/`verify_ownership` classmethod'ları SENKRON ve düzinelerce yerden çağrılıyor; bunları async'e çevirip her çağrı noktasını güncellemek çok büyük bir blast-radius olurdu. (c) Ek olarak keşfedildi: `log_audit_event` helper'ının kendisi `_persist_audit_to_db`'yi her zaman sabit `basarili=True` ile çağırıyordu — yani bu helper'ı bir başarısızlık için kullansanız bile DB'de "başarılı" görünürdü.

**Sonuç:**
- `app/infrastructure/audit/audit_logger.py` — `log_audit_event`'e `basarili: bool = True` parametresi eklendi (geriye uyumlu default), hem dosya loguna hem `_persist_audit_to_db`'ye doğru şekilde geçiyor.
- `app/core/services/auth_service.py` — başarısız giriş denemesinde `log_audit_event(action="auth.failed_login", ..., basarili=False)` çağrısı eklendi (best-effort, `try/except`).
- `app/main.py` — 403 için tekil çağrı-noktalarını değiştirmek yerine **merkezi `http_exception_handler`'a** tek bir hook eklendi: her `status_code==403` best-effort olarak `action="authz.forbidden"` ile audit'e yazılıyor (Authorization header'dan JWT `sub` claim'i best-effort çözülüp kaydediliyor); bu, kaynağı ne olursa olsun (security_service, require_permissions dependency, vb.) TÜM 403'leri kapsıyor.

**Doğrulama:** `test_audit_logger.py`'ye 2 yeni test (`basarili` default + propagate), `test_auth_service_coverage.py`'ye 1 yeni test (failed-login audit çağrısı), `test_main_coverage.py`'ye 2 yeni test (403 audit çağrısı + audit hatası asıl yanıtı bozmuyor). Kırmızı-yeşil doğrulandı (fix öncesi 3 test fail — audit çağrıları hiç yapılmıyordu). `ruff`+`mypy` temiz (baseline korunuyor). 291 test (main/infrastructure/auth/security) yeşil.

### 13. docker-compose.yml zayıf şifre fallback'i (P1, Dalga 2 madde 4) — 2026-07-01, üçüncü tur

**Neden:** `docker-compose.prod.yml` zaten doğru desendeydi (`${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in prod}` — prod'da zorunlu). Sorun yalnız dev/base `docker-compose.yml`'deydi: `${POSTGRES_PASSWORD:-change-me}` (4 yerde: backend, worker, db, postgres-exporter servisleri) + `${GF_SECURITY_ADMIN_PASSWORD:-change-me}` (Grafana). `POSTGRES_PASSWORD` set edilmeden `docker-compose up` çalıştırılırsa DB şifresi literal `"change-me"` olurdu.

**Sonuç:** Kullanıcıya soruldu — **prod.yml ile aynı zorunlu desen** onaylandı (workflow etkisi kabul edilebilir, `.env.example` zaten `POSTGRES_PASSWORD=CHANGE_ME`/`GF_SECURITY_ADMIN_PASSWORD=CHANGE_ME` ile belgeliyor). `docker-compose.yml`'deki tüm 5 fallback `:-change-me` → `:?... must be set (see .env.example)` olarak değiştirildi.

**Doğrulama:** Kod değişikliği olmadığı için pytest yerine `docker compose config` ile dört senaryo test edildi: (1) **fix öncesi** (git stash ile geçici geri alınıp) boş env-file ile → `DATABASE_URL` gerçekten literal `postgresql+asyncpg://lojinext_user:change-me@db:5432/lojinext_db` olarak resolve oldu (kırmızı — zafiyet ampirik olarak kanıtlandı, varsayım değil), (2) **fix sonrası** boş env-file ile → `exit code 1`, "POSTGRES_PASSWORD must be set" hatası, (3) fix sonrası env-file'da gerçek şifreler set edilince → `exit code 0` (yeşil), (4) kullanıcının **gerçek yerel `.env`'i** (zaten `POSTGRES_PASSWORD` içeriyor) ile → `exit code 0`, hiçbir regresyon yok. `git stash`/`pop` ile fix restore edildi, `grep -c change-me docker-compose.yml` → 0 doğrulandı.

### 14. ops_bot webhook secret + komut kimlik kontrolü (P1, Dalga 2 madde 5) — 2026-07-01, üçüncü tur

**Neden:** (a) `_check_webhook_secret`, `WEBHOOK_SECRET` (`OPS_WEBHOOK_SECRET`) yapılandırılmamışsa kontrolü tamamen atlıyordu (fail-open) — `telegram-ops-bot` portu (8080) host'a expose edildiği için harici biri secret olmadan `/webhook/alertmanager`, `/webhook/error`, `/webhook/feedback`'e sahte payload POST'layabiliyordu. (b) `/durum` ve `/uyarilar` komutları hiçbir kimlik/chat kontrolü yapmıyordu — bot username'ini bulan herhangi bir Telegram kullanıcısı backend sağlık durumunu ve tüm aktif Prometheus alarmlarını görebiliyordu. Zincir incelenince kapsam genişledi: `docker-compose.yml`'de `OPS_WEBHOOK_SECRET` hiç set edilmemişti VE backend'in kendi `telegram_notifier.py`'si (`/webhook/error`, `/webhook/feedback` çağrıları) hiçbir secret header'ı göndermiyordu VE `alertmanager.yml` statik bir dosya olduğu için doğrudan env var enjekte edilemiyordu.

**Sonuç (kullanıcı onayıyla tam zincir):**
- `telegram_bot/ops_bot.py` — `_check_webhook_secret` artık `WEBHOOK_SECRET` boşsa TÜM istekleri reddediyor (503, fail-closed); doğrulama standart `Authorization: Bearer <secret>` header'ı üzerinden yapılıyor (eski özel `X-Webhook-Secret` yerine — Alertmanager'ın `http_config.authorization` ve backend'in `telegram_notifier.py`'siyle uyumlu). 3 webhook endpoint'i de güncellendi. Yeni `_is_from_ops_chat()` helper'ı: `/durum`/`/uyarilar` artık yalnız yapılandırılmış `OPS_CHAT_ID`'den gelen mesajlara yanıt veriyor.
- `app/infrastructure/notifications/telegram_notifier.py` — `OPS_WEBHOOK_SECRET` okuyup her iki webhook çağrısına (`notify_error`, `notify_feedback`) `Authorization: Bearer` header'ı ekliyor.
- `docker-compose.yml` — `telegram-ops-bot` servisine `OPS_WEBHOOK_SECRET` (zorunlu) + `OPS_ADMIN_TELEGRAM_IDS` (önceden hiç geçirilmiyordu, bonus fix) eklendi. `alertmanager` servisine `OPS_WEBHOOK_SECRET` env var'ı + container başlarken bu değeri `/tmp/ops_webhook_secret`'a yazıp sonra alertmanager'ı başlatan bir `entrypoint`/`command` wrapper'ı eklendi (repo'da hiçbir çıplak secret yok — statik `alertmanager.yml`'e env var enjekte edilemediği için bu yol seçildi).
- `alertmanager/alertmanager.yml` — `webhook_configs.http_config.authorization.credentials_file: /tmp/ops_webhook_secret` eklendi.
- `.env.example` — **kullanıcı tarafından manuel eklenmesi gerekiyor** (izin kısıtlaması nedeniyle dokunamadım): `OPS_WEBHOOK_SECRET=CHANGE_ME` ve `OPS_ADMIN_TELEGRAM_IDS=` satırları `TELEGRAM_OPS_BOT_URL` satırının altına eklenmeli.

**Doğrulama:** `telegram_bot/tests/test_ops_bot_security.py` (yeni, 11 test) — fail-closed davranışı, yanlış/eksik Bearer token reddi, chat-gating (yetkisiz sohbet sessizce reddedilir, yetkili sohbet hâlâ yanıt alır — regresyon guard'ı). Kırmızı-yeşil doğrulandı (fix öncesi 9/11 test fail — kimlik kontrolü hiç yoktu). `docker compose config` ile doğrulama: (1) gerçek `.env` ile (henüz `OPS_WEBHOOK_SECRET` içermiyor) → beklenen şekilde `exit 1`, hangi değişkenin eksik olduğunu söylüyor; (2) override env-file'da `OPS_WEBHOOK_SECRET` set edilince → `exit 0`, hem `alertmanager` hem `telegram-ops-bot` servislerinde doğru interpolasyon teyit edildi. `ruff`+`mypy` temiz. 78 telegram/notification testi yeşil.

**⚠️ Kullanıcı aksiyonu gerekiyor:** Bu madde tam etkili olması için (a) `.env` dosyanıza `OPS_WEBHOOK_SECRET=<gerçek-rastgele-değer>` eklemeniz, (b) mevcut `.env`'inizde `OPS_ADMIN_TELEGRAM_IDS` yoksa (destructive `/yeniden_baslat` komutu için) eklemeniz gerekiyor — aksi halde `docker-compose up` artık `OPS_WEBHOOK_SECRET must be set` hatasıyla durur (bu kasıtlı, fail-closed'ın doğru çalıştığının kanıtı).

### Nihai doğrulama durumu

- `ruff check app --select E,F,W,I` → temiz.
- `mypy` (değiştirilen tüm dosyalar) → tam olarak baseline (main'deki 7 önceden-var-olan hata), yeni hata yok.
- **`pytest app/tests/unit` (tam paket, 2004 dosya): 5144 passed, 8 skipped, 3 deselected, 0 failed.** (Deselect edilenler: main'de de aynı şekilde fail eden, bu oturumla ilgisiz 3 ortam-bağımlı test — `.env`'deki `USE_SEFER_FUEL_ESTIMATOR=true` ve `SeferFuelEstimator`'ın ayrı `DATABASE_URL` bağlantısındaki şifre uyuşmazlığı.)
- Bağımsız `code-reviewer` ajanı tüm diff'i (`git diff`, 20 dosya, ~580 satır) inceledi; bulduğu 1 gerçek bug (`telefon` bozulması) ve 1 test-netliği notu (madde 5'te) kapatıldı.

### 15. Derin kontrol (dördüncü tur) — süper-admin rate-limit global bucket → DoS riski, 2026-07-01

**Neden:** Kullanıcının "derin kontrol et" talebiyle, bu oturumdaki TÜM iddialar (kök-neden fix + 16 çağrı noktası, 3 bağımsız P0, Dalga 1'in 4 maddesi, Dalga 2'nin 5 maddesi) 4 paralel bağımsız fork-agent ile adversarial olarak yeniden doğrulandı — her biri kodu satır satır yeniden okudu, testleri gerçekten çalıştırdı, önceki iddialara güvenmedi. Sonuç: 3 grup tamamen PASS (kusur bulunamadı), ama madde 6'nın (süper-admin rate-limit) doğrulamasında yeni bir gerçek güvenlik tasarım açığı bulundu: `RateLimiterRegistry.get("super_admin_login", ...)` (`app/api/v1/endpoints/auth.py`) sabit bir string key kullanıyordu → **global (tüm IP'ler arası paylaşılan) tek bir bucket**. Kimliği doğrulanmamış herhangi bir saldırgan, herhangi bir IP'den `username=SUPER_ADMIN_USERNAME` + yanlış şifreyle 3 istek göndererek bucket'ı 5 dakikalığına tüketebilir ve bunu sürekli tekrarlayarak meşru süper-admin'in break-glass hesabından **süresiz giriş yapmasını engelleyebilir (DoS)**. Bu, madde 5'te break-glass'a eklenen sıkı rate-limit'in kendisinin yarattığı yeni bir açıktı — kök neden: bucket key seçilirken client IP hesaba katılmamıştı.

**Sonuç:** `app/api/v1/endpoints/auth.py` — bucket key'e client IP dahil edildi: `RateLimiterRegistry.get(f"super_admin_login:{_login_ip}", rate=3, period=300.0)` (`_login_ip = request.client.host if request.client else "unknown"`). Artık bir IP'nin yanlış-şifre denemeleri yalnızca o IP'nin bucket'ını tüketiyor, başka bir IP'den gelen meşru giriş denemesi etkilenmiyor.

Ek olarak, aynı derin kontrol turunda bulunan 2 kozmetik/düşük-risk bulgu da kullanıcı onayıyla kapatıldı:
- `telegram_bot/ops_bot.py` — `WEBHOOK_SECRET` tanımının üstündeki yorum hâlâ eski "X-Webhook-Secret header" şemasını referans veriyordu (kod doğruydu, sadece yorum stale'di) → `Authorization: Bearer` şemasını yansıtacak şekilde güncellendi.
- `app/api/middleware/rate_limiter.py` — `_resolve_environment()`/`_resolve_rate_limit_enabled()`'daki genel `except Exception` daraltıldı → `except ImportError`. Gerekçe: `app.config` gerçekten bozuksa (örn. bir ayar doğrulama hatası), önceki geniş except prod'da bile sessizce "dev"e düşüp madde 6'nın fail-closed niyetini baltalayabilirdi; artık yalnızca modülün hiç mevcut olmadığı durum yutuluyor, başka her hata yükseliyor.

**Doğrulama:** Yeni `test_super_admin_rate_limit_is_scoped_per_ip` testi (`app/tests/api/test_auth_coverage.py`) — httpx `ASGITransport(client=...)` ile iki farklı sahte IP simüle edilerek yazıldı. Kırmızı: fix öncesi ikinci ("farklı IP'den meşru admin") istek de yanlışlıkla 429 alıyordu (ampirik kanıtlandı, log'da iki ardışık 429 görüldü). Fix sonrası yeşil: `app/tests/api/test_auth_coverage.py -k super_admin` → 5/5 PASS. İki mevcut testteki `RateLimiterRegistry._limiters.pop("super_admin_login", None)` temizlik satırları da prefix-tabanlı temizliğe güncellendi (bucket key artık `super_admin_login:{ip}` formatında, eski exact-key pop artık hiçbir şey temizlemezdi — bu da ayrıca düzeltildi). `ruff`+`mypy` temiz (mypy baseline: 7, aynı). Tam paket regresyon: `pytest app/tests/unit app/tests/api/test_auth_coverage.py` → 5185 passed (1 transient Windows asyncpg soket flake'i izole tekrar çalıştırmayla doğrulandı, gerçek regresyon değil), 8 skipped, 3 deselected, 0 gerçek fail.

**Genel derin-kontrol sonucu:** Bu oturumun önceki 3 fork grubu (kök-neden+16 çağrı noktası, 3 P0, Dalga 1) hiçbir kusur olmadan PASS aldı — hiçbir sahte/hayali/çalışmayan iddia bulunamadı. Dalga 2 grubunda 1 gerçek güvenlik açığı (yukarıda) + 2 kozmetik bulgu vardı, hepsi bu turda kapatıldı.

### 16. Dalga 3 — P1 repository/DB/async (madde 12-15), 2026-07-01

**Madde 12 — `AdminConfigRepository.update_value` kilitsiz read-modify-write**

**Neden:** `update_value` `session.get()` ile düz okuma yapıp mutate+flush ediyordu, satır kilidi yoktu. Eşzamanlı iki `PATCH /admin/config/{key}` isteğinde, geç kalan transaction ilkinin commit'inden ÖNCE okunan stale bir `deger`'i `eski_deger` olarak audit history'ye yanlış yazıyordu.

**Sonuç:** `app/database/repositories/admin_config_repo.py` — `session.get()` → `SELECT ... FOR UPDATE` (`select(self.model).where(self.model.anahtar == key).with_for_update()`). Satır artık select anında kilitleniyor; geç kalan transaction ilkinin commit'ini bekleyip GÜNCEL değeri görüyor.

**Doğrulama:** Yeni `app/tests/integration/test_admin_config_repo_concurrency.py` — iki gerçek eşzamanlı transaction (`asyncio.Event` ile senkronize), `SessionLocal` üzerinden gerçek ayrı bağlantılar. Kırmızı: fix öncesi B'nin history kaydı `eski_deger='V0'` (stale) yazıyordu. Yeşil: fix sonrası `eski_deger='VA'` (A'nın commit ettiği güncel değer). 4 mevcut mock-tabanlı unit test `session.get` → `session.execute` mock'ına güncellendi (implementasyon değişikliği nedeniyle). 30/30 test yeşil, `ruff`+`mypy` temiz (baseline 7, aynı).

**Madde 13 — `Arac` ORM cascade / DB RESTRICT çelişkisi**

**Neden:** `Arac.yakit_alimlari` (ve taramada bulunan `yakit_periyotlari`, `formul`) ilişkileri ORM'de `cascade="all, delete-orphan"` taşıyordu, ama DB'de ilgili FK'ler `ondelete="RESTRICT"` (finansal kayıtlar — yakıt alımları, periyotlar, tüketim formülü). Aktif silme yolları (`AracService`, Core-level `hard_delete`) bu çelişkiye dokunmuyordu, ama ileride biri ORM-seviyeli `session.delete(arac)` çağırsaydı, ORM cascade DB'nin RESTRICT'i hiç devreye girmeden çocuk kayıtları sessizce silerdi.

**Sonuç:** Üç ilişkide de `cascade="all, delete-orphan"` kaldırıldı, `passive_deletes=True` eklendi (`app/database/models.py`) — silme artık tamamen DB'nin RESTRICT'ine bırakılıyor.

**Doğrulama:** Yeni `app/tests/integration/test_arac_yakit_cascade_restrict.py` (6 test) — gerçek `session.delete(arac)` + flush çağrılarıyla, git-stash ile kırmızı (fix öncesi ORM sessizce siliyordu, DB hiç itiraz etmiyordu) ve yeşil (fix sonrası `IntegrityError`, finansal kayıt korunuyor) ampirik olarak doğrulandı. Ayrıca mapper-seviyeli 3 parametrize test, her ilişkinin `passive_deletes=True` taşıdığını ve `delete`/`delete-orphan` cascade taşımadığını doğrudan doğruluyor. `ruff`+`mypy` temiz.

**Madde 14 — `Sefer.periyot_id` gerçek FK değil**

**Neden:** `periyot_id` plain bir Integer kolonuydu ("soft link to periyot"), DB seviyesinde hiçbir FK kısıtı yoktu — orphan referanslar engellenmiyor, join'den sessizce düşüyordu. Bu madde şema migration'ı gerektirdiği için (önceki 2 maddeden farklı risk sınıfı) kullanıcıdan açık onay alındı.

**Sonuç:** Yeni migration `alembic/versions/0035_sefer_periyot_id_fk.py` — `yakit_periyotlari(id)` için gerçek FK (`ON DELETE SET NULL`, `NOT VALID` — proje standardı `0028_missing_fk_constraints.py` deseniyle aynı, orphan veri migration'ı bloklamasın diye). Migration'ın kendisi önce orphan `periyot_id` referanslarını NULL'a çekiyor, sonra constraint'i ekliyor. `app/database/models.py`'de ORM tarafına da `ForeignKey("yakit_periyotlari.id", ondelete="SET NULL")` eklendi.

**Doğrulama:** Migration, gerçek bir throwaway scratch DB'de (`alembic_scratch`, ayrı, ne pytest test DB'sine ne kullanıcının gerçek/dev DB'sine dokunuldu) upgrade→downgrade→upgrade ile test edildi, `alembic check` drift raporlamadı. Orphan-cleanup UPDATE'in mantığı izole bir temp-tablo senaryosunda ayrıca kanıtlandı (orphan satır doğru NULL'a çekildi). Yeni `app/tests/integration/test_sefer_periyot_id_fk.py` (2 test) — git-stash ile kırmızı (orphan referans + ON DELETE SET NULL öncesi ikisi de fail) ve yeşil doğrulandı. `ruff`+`mypy` temiz.

**Madde 15 — `Anomaly.severity`/`Sefer.onay_durumu` DB-seviye CHECK yok**

**Neden:** İki kritik enum-benzeri kolonda DB-seviye CHECK kısıtı yoktu — typo'lu bir değer (örn. "hihg") hiç engellenmiyordu, sessizce kaydediliyordu.

**Sonuç:** Yeni migration `alembic/versions/0036_severity_onay_durumu_check.py` — `check_anomaly_severity_enum` (`low/medium/high/critical`) ve `check_sefer_onay_durumu_enum` (`NULL` veya `beklemede/onaylandi/reddedildi`), ikisi de `NOT VALID`. `app/database/models.py`'de ORM `__table_args__`'a aynı `CheckConstraint`'ler eklendi.

**Hata + düzeltme (kırmızı-yeşil disiplini bir gerçek bug yakaladı):** İlk uygulamada `Anomaly.__table_args__`'ı YANLIŞLIKLA class body'de İKİNCİ bir `__table_args__` ataması (mevcut, önceden var olan indexler için) SESSİZCE eziyordu — Python'da aynı class'ta bir attribute'a iki kez atama yapılırsa ikincisi kazanır. Kırmızı-yeşil test bunu hemen yakaladı (`test_anomaly_severity_rejects_invalid_value` fix sonrasında bile "DID NOT RAISE" ile fail etti) — CheckConstraint'i mevcut `__table_args__` tuple'ına taşıyarak (ayrı bir atama yapmak yerine) düzeltildi.

**Doğrulama:** Migration aynı scratch-DB prosedürüyle (upgrade/downgrade/upgrade, `alembic check`) doğrulandı. Yeni `app/tests/integration/test_severity_onay_durumu_check_constraints.py` (4 test) — git-stash ile kırmızı/yeşil doğrulandı. `ruff`+`mypy` temiz.

**Dalga 3 tam paket regresyon notu — ikinci turda 2 GERÇEK BUG bulundu:**

`pytest app/tests/unit app/tests/api app/tests/integration` (tek seferde, ~7000 test, 830s) **İKİ KEZ** çalıştırıldı, sonuçlar karşılaştırıldı:
- Run 1: 78 fail + 21 error (99 toplam)
- Run 2 (aynı kod, aynı komut): 9 fail + 2 error (11 toplam)
- İki koşu arasındaki kesişim: sadece **2 test** — geri kalan ~97 + ~9 tamamen FARKLI testlerdi.

Bu, iki koşu arasında ortak kalan 2 test dışındaki TÜM dağınık başarısızlıkların gerçekten non-deterministik/ortam-kaynaklı (Windows'ta NullPool + ~7000 testi tek kesintisiz process'te 830s boyunca gerçek Postgres'e vurdurmanın connection-pool/GC zamanlama sorunları — bkz. proje hafızası "Local test DB execution" notu) olduğunu kanıtlıyor; izole/küçük-grup tekrar çalıştırmalarında da bunlar tutarlı şekilde yeşil çıktı.

**Ama** iki koşuda da tekrarlayan 2 testten biri (`test_dorse_repo.py::test_get_active_trailers_excludes_deleted_and_inactive`) izole çalıştırıldığında PASSED çıktı (o da flaky), diğeri (`test_locations_more2.py::test_delete_inactive_hard_delete`) ise **izole çalıştırıldığında da her seferinde deterministik olarak FAIL** ediyordu — gerçek bir bug. Kök neden araştırması **2 gerçek, önceden kapatılmamış bug** ortaya çıkardı, ikisi de `app/api/v1/endpoints/locations.py`'de, kök-neden fix'inin (`get_by_id` include_inactive) orijinal 16-çağrı-noktası taramasında KAÇIRILAN 2 ek çağrı noktası:

- **DELETE `/locations/{id}`** (satır 297): `service.repo.get_by_id(lokasyon_id)` — `include_inactive=True` eksikti. Bu endpoint pasif kayıtları görmesi gerekiyor (`was_active` hesabı hard-delete yolunu belirliyor); pasif bir lokasyonu silmeye çalışmak 404 ile yanlışlıkla reddediliyordu.
- **PUT `/locations/{id}`** (satır 251, 260): audit pre/post-snapshot fetch'leri de `include_inactive=True` eksikti. Pasif bir lokasyonu güncellemek (reaktive etmeden, örn. sadece notlar) `get_by_id` None döndürdüğü için `dict(None)` → `TypeError: 'NoneType' object is not iterable` → **500 Internal Server Error**.

**Sonuç:** Her iki çağrı noktasına da `include_inactive=True` eklendi (`app/api/v1/endpoints/locations.py`).

**Doğrulama:** DELETE bug'ı için mevcut `test_delete_inactive_hard_delete` testi kırmızı-yeşil doğrulandı (izole + dosya-geneli). PUT bug'ı için yeni `test_update_inactive_location_does_not_crash` testi yazıldı, kırmızı (fix öncesi gerçek 500 yanıtı ampirik kanıtlandı) ve yeşil doğrulandı. `app/api/v1/endpoints/locations.py`'deki TÜM `get_by_id` çağrıları broad-grep ile yeniden tarandı (create/get/update/delete) — create ve get (normal okuma) yolları kasıtlı olarak filtrelenmeye devam ediyor (doğru davranış), sadece delete/update'in "pasif kaydı da görmesi gerekiyor" gerekçesiyle include_inactive eklendi. `admin_roles.py`/`drivers.py`/`trips.py`'deki benzer `get_by_id` çağrıları da tek tek incelendi — `Rol` modelinde soft-delete kolonu yok (etkilenmiyor), `drivers.py`'nin DELETE'i ham `session.get()` kullanıyor (repository metodu değil, etkilenmiyor), `trips.py`'nin filtrelemesi kasıtlı/doğru davranış. Regresyon: `app/tests/api/test_locations_more2.py` tam dosya 26/26 PASS, tüm "location" içeren test dosyaları (96 test) PASS. `ruff`+`mypy` temiz (baseline 7, aynı).

**Sonuç — "emin miyiz" sorusuna dürüst yanıt:** Hayır, ilk turda "mega-run'daki hatalar tamamen ortam kaynaklı, kod hatası yok" demek YANLIŞ bir genellemeydi — örneklem yeterince büyük değildi. İkinci bir tam-koşu + iki koşunun kesişim analizi + kesişimdeki HER İKİ testin de tek tek izole doğrulanması sonucunda: 99 (run1) + 11 (run2) toplam gözlemin **2 gerçek bug'a** işaret ettiği, geri kalanının genuine ortam flakiness olduğu kanıtlandı. Bu 2 bug bulunup kapatıldı.

**Üçüncü bulgu — test-izolasyon altyapısında gerçek bir kusur, ölçülen büyük etki:** Kullanıcı "neden düzeltmedin, her iş böyle eksik mi" diye sorunca, mega-run flakiness'inin kök nedenini "muhtemelen ortam kısıtı" demekle bırakmayıp gerçekten kazdım. `app/tests/conftest.py`'deki `reset_all_singletons()` fonksiyonu incelendi: sadece 5 repository singleton'ını (`arac`, `sefer`, `sofor`, `yakit`, `analiz`) testler arası sıfırlıyordu — **4 tanesini hiç sıfırlamıyordu**: `admin_config_repo`, `dorse_repo`, `lokasyon_repo`, `route_repo`. Bu, aynı thread-safe singleton kalıbını (`threading.Lock` + module-level `_x_repo` cache) taşıyan TÜM repository dosyaları tarandığında bulundu (8 dosya, hepsi doğrulandı — başka kaçırılan yok).

**Sonuç:** `app/tests/conftest.py` — eksik 4 modül import edildi, `reset_all_singletons()`'a eklendi.

**Ölçülen etki (kanıt, tahmin değil):** Fix öncesi/sonrası aynı komutla art arda 3 tam-paket koşusu (`pytest app/tests/unit app/tests/api app/tests/integration`, ~7000 test):
- Run 1 (fix öncesi): 99 hata (78 fail + 21 error)
- Run 2 (fix öncesi, tekrar): 11 hata (9 fail + 2 error)
- Run 3 (fix SONRASI): **1 hata** (0 fail, 1 setup error — izole çalıştırıldığında o da PASSED çıktı)

99 → 11 → 1. Bu fix, mega-run flakiness'inin **asıl büyük kaynağıydı** — ilk değerlendirmem ("bu spesifik kusur muhtemelen ana neden değil, çünkü bu 4 repo `__init__`'inde ekstra state tutmuyor") YANLIŞ çıktı; gerçek etkiyi sadece ölçerek görebildim, teorik akıl yürütmeyle değil. Kalan 1 hata artık pratik olarak önemsiz seviyede (izole yeşil, muhtemelen kalıntı Windows/asyncpg bağlantı gürültüsü).

**Ders:** "Muhtemelen ortam kaynaklı" gibi bir teşhisi, ölçülebilir bir düzeltme denemesi yapmadan nihai kabul etmek riskli — kullanıcının ısrarı doğru bir mühendislik pratiğini (kök nedeni gerçekten kapatana kadar kovala) zorladı.

### 17. Dalga 3 — madde 16-17 (Digest/backfill geniş except, BackgroundJobManager worker-restart), 2026-07-01

**Madde 16 — Digest/backfill task'larında retry'ı iptal eden geniş `except`**

**Neden:** `notifications.weekly_digest` ve `prediction.backfill_missing` Celery task'ları TÜM hataları (`except Exception`) yutup normal bir sonuç dict'i (`{"error": str(exc)}`) DÖNÜYORDU — raise etmiyordu. Celery bir task'ı sadece exception fırlatırsa retry eder; normal dönen bir sonuç her zaman SUCCESS sayılır. Sonuç: `max_retries=1` yapılandırılmış olsa da fiilen hiçbir zaman devreye girmiyordu — geçici bir DB/Redis/Mapbox hatası bile sessizce "başarılı ama 0 işlem" olarak kayboluyordu, hiçbir alarm/retry tetiklenmiyordu.

**Sonuç:** Proje genelinde zaten kurulu olan retry deseni uygulandı (`app/workers/tasks/driver_tasks.py`'deki `calculate_performance_score` ile aynı desen): geçici hatalar (`ConnectionError`/`TimeoutError`/`OSError`) → `raise self.retry(exc=exc, countdown=2**self.request.retries * 30)`; diğer tüm hatalar → log'lanıp yeniden fırlatılır (`raise`) — task artık gerçekten FAILED olarak işaretlenir, Celery/Flower/Prometheus'ta görünür olur.

**Doğrulama:** `weekly_digest` için 2 yeni test (`test_weekly_digest_connection_error_retries`, `test_weekly_digest_generic_error_reraises`, eski `test_weekly_digest_exception_path` — eski swallow-davranışını doğruluyordu, kaldırıldı/güncellendi), `backfill_missing` için 2 yeni test — hepsi `.apply(args=...).get(propagate=True)` + `pytest.raises(Exception)` deseniyle (`driver_tasks.py`'nin test dosyasındaki established pattern). Kırmızı-yeşil git-stash ile doğrulandı (4 test fix'siz halde fail etti). `ruff`+`mypy` temiz (baseline 7, aynı).

**Madde 17 — `BackgroundJobManager` worker-restart sonsuz "running" durumu**

**Neden:** Job durumu Redis'te tutuluyordu ama SADECE in-process `asyncio.create_task()`'ın kendi ilerlemesine bağlıydı — worker process crash/redeploy ile öldüğünde, Redis'teki kayıt hiçbir zaman "running"dan başka bir duruma geçmiyordu (24 saatlik TTL'e kadar). Frontend `useTaskStatus` hook'u bu durumda sonsuza dek poll ederdi.

**Sonuç:** `app/infrastructure/background/job_manager.py` — her job'a bir `heartbeat_at` alanı eklendi, çalışırken 30 saniyede bir arka planda güncellenen bir heartbeat-loop task'ı başlatılıyor (iş bitince/hata alınca `finally` bloğunda iptal ediliyor). `get_status()` artık "running" bir job'ın heartbeat'i `_STALE_RUNNING_SECONDS` (300s) eşiğinden eskiyse, kaydı kendiliğinden "failed" + açıklayıcı hata mesajıyla günceller — worker'ın öldüğü, sonucun bilinmediği net şekilde yansır, sonsuz poll biter.

**Doğrulama:** Yeni `test_get_status_detects_stale_running_job_after_worker_restart` (kırmızı-yeşil, stale heartbeat simüle edilip fix öncesi "running" kaldığı, fix sonrası "failed"e döndüğü kanıtlandı) + regresyon guard'ı `test_get_status_does_not_flag_fresh_running_job_as_stale` (yakın-zamanlı heartbeat yanlışlıkla failed'e çevrilmemeli). Mevcut 14 test de dahil tüm `test_job_manager.py` (16/16) + job_manager'ı kullanan tüm API/unit test dosyaları (156 test) PASS. `ruff`+`mypy` temiz.

**Dalga 3 tamamlandı (madde 12-17, 6/6).**

### 18. Dalga 4 — madde 18: `investigations.py` PATCH TOCTOU race, 2026-07-01

**Neden:** `update_investigation` (`app/api/v1/endpoints/investigations.py`) `db.get(FuelInvestigation, inv_id)` ile kilitsiz okuma yapıyordu. Eşzamanlı iki PATCH isteğinde (örn. biri `resolution_type` set edip status'ü otomatik `resolved` yapan, diğeri sadece `assigned_to_user_id` set eden), geç kalan istek "status hâlâ open ise otomatik `assigned`" mantığını kendi ESKİ (stale) okumasına göre uygulayıp, diğerinin commit ettiği `resolved` durumunu FARKINDA OLMADAN `assigned`'e geri döndürüyordu — çözümlenmiş bir soruşturma sessizce yeniden açık göründüğü bir lost-update.

**Sonuç:** `_read_investigation_for_update()` helper'ı eklendi — `db.get()` yerine `SELECT ... FOR UPDATE` kullanıyor. Satır artık select anında kilitleniyor; geç kalan istek ilkinin commit'ini bekleyip GÜNCEL durumu görüyor, böylece stale-okuma temelli otomatik geçiş tetiklenmiyor. DELETE endpoint'i (`soft_delete_investigation`) kasıtlı olarak kapsam dışı bırakıldı — idempotent bir operasyon (`status=='closed'` erken çıkışı), iki eşzamanlı DELETE'in aynı sonuca (closed) yol açması zararsız.

**Doğrulama:** Yeni `app/tests/integration/test_investigations_patch_race.py` — iki gerçek eşzamanlı transaction, `asyncio.Event` ile hassas senkronize edildi (A'nın UPDATE'i satırı kilitler, B'nin write'ı kasıtlı olarak A'nın commit'inden sonraya ertelenir — asıl TOCTOU senaryosu). Kırmızı: fix öncesi final status yanlışlıkla `assigned` oluyordu (A'nın `resolved` kararı kayboluyordu) — 3 kez tekrar çalıştırılıp flaky olmadığı doğrulandı. Yeşil: fix sonrası final status doğru şekilde `resolved` kalıyor. Mevcut mock-tabanlı testlerdeki (`test_investigations_coverage.py`, `test_investigations_more.py`) `db.execute(...).scalar_one_or_none()` mock'ları yeni `SELECT FOR UPDATE` çağrısını yansıtacak şekilde güncellendi (4 ayrı yer). Regresyon: 74/74 investigations testi PASS. `ruff`+`mypy` temiz (baseline 7, aynı).

---

### 19. Dalga 4 — madde 19: `fuel.py`/`trips.py` POST uçlarında idempotency key, 2026-07-01

**Neden:** `create_yakit` (fuel.py) ve `create_sefer` (trips.py) POST uçlarında idempotency key desteği yoktu — client timeout+retry senaryosunda (istek server'da başarıyla işlendi ama yanıt client'a ulaşmadan bağlantı koptu) client'ın otomatik retry'ı çift yakıt/sefer kaydı oluşturabiliyordu. Kullanıcı onayıyla DB-tabanlı (Redis değil) bir çözüm seçildi.

**Sonuç:**
- Yeni `IdempotencyKey` modeli (`app/database/models.py`) + migration `alembic/versions/0037_idempotency_keys.py` — `(key, endpoint)` üzerinde unique constraint, istek gövdesinin SHA-256 hash'i + önbelleklenen yanıt (status_code + JSONB body).
- Yeni `app/core/services/idempotency_service.py` — `get_cached_response()` (aynı key+aynı gövde → önbelleklenen yanıt; aynı key+farklı gövde → `IdempotencyKeyConflictError`) ve `store_response()`.
- `create_yakit`/`create_sefer` endpoint'lerine opsiyonel `Idempotency-Key` header desteği eklendi. Her ikisi de artık endpoint imzasına açıkça `uow: UOWDep` alıyor — FastAPI'nin dependency-caching'i sayesinde bu, `get_yakit_service`/`get_sefer_service`'in İÇİNDE kullanılan UoW ile AYNI nesne (tek `get_uow()` çağrısı, istek başına) — idempotency kaydı gerçek yaratma işlemiyle AYNI transaction'da commit ediliyor (atomiklik).
- Header YOKSA davranış tamamen eskisi gibi (geriye dönük uyumlu, hiçbir mevcut akış etkilenmiyor).

**Doğrulama:** Migration throwaway scratch DB'de upgrade/downgrade/`alembic check` ile doğrulandı. Yeni `app/tests/integration/test_idempotency_key.py` (5 test) — gerçek API çağrılarıyla (mock yok): aynı key+aynı gövde → ikinci istek AYNI kaydı dönüyor (yeni satır oluşmuyor); aynı key+farklı gövde → 409; header'sız → eski davranış korunuyor (fuel'de zaten var olan (arac_id,tarih,litre) iş-kuralı duplicate koruması hâlâ çalışıyor — bu YENİ bir davranış değil; sefer'de ise gerçekten 2 ayrı kayıt oluşuyor, madde 19'un asıl önlemek istediği senaryo budur). Kırmızı: production kodu (fuel.py/trips.py) git-stash ile geri alınıp aynı 5 test çalıştırıldı — idempotency-key'e bağlı 3 test fix'siz halde fail etti (header'sız 2 test zaten beklenen davranışı test ettiği için doğal olarak PASS kaldı). Yeşil: fix geri getirilince 5/5 PASS.

**Hata + düzeltme (geliştirme sırasında bulunup kapatıldı):** İlk uygulamada `YakitResponse.model_validate(created)` çağrısı `pydantic.ValidationError` (ValueError alt sınıfı) fırlatıyordu — `service.get_yakit_by_id()` bir ORM instance'ı (`YakitAlimi`) döndürüyor, dict değil; `model_validate`'e `from_attributes=True` eklenmeden ORM nesnesini kabul etmiyor (FastAPI'nin kendi otomatik `response_model` serileştirmesi bunu örtük olarak yapıyordu, benim eklediğim açık çağrı yapmıyordu). `from_attributes=True` eklenerek düzeltildi.

**Regresyon:** `app/tests/api/test_fuel_coverage.py`, `test_trips_coverage.py`, `test_trips_more.py`, `test_adversarial_stress.py`, `test_api_seferler.py` + yeni dosya birlikte 157/157 PASS. `ruff`+`mypy` temiz (baseline 7, aynı).

**EK — derin kontrol (dördüncü tur) bulgusu #1, 2026-07-01: eşzamanlı ilk-kullanım yarışı → yakalanmamış 500.** Bağımsız fork-agent doğrulaması, `get_cached_response()`+`store_response()` çiftinin (SELECT sonra ayrı INSERT) gerçek eşzamanlı iki istekte (aynı YENİ key) ikisinin de SELECT'te "yok" bulup ikisinin de gerçek işi yaptığını, ikinci commit'in yakalanmamış `IntegrityError` (unique constraint) ile 500 döndüğünü kanıtladı (iki bağımsız DB session'ıyla `asyncio.gather` testiyle: `RESULT r2: ('commit_failed', 'IntegrityError', ...)`). Veri bozulmuyordu (kaybedenin transaction'ı bütünüyle rollback oluyordu) ama hata zarif değildi. **Fix:** "reserve-then-create" deseni — `reserve_or_get_cached()` önce SELECT yapar, bulamazsa placeholder satırı INSERT eder; INSERT çakışırsa (Postgres unique-index semantiği: çakışan satır artık commit edilmiş olmalı) hatayı yakalayıp güvenle yeniden SELECT yapar. Yeni `IdempotencyKeyInProgressError` (rezerve edilmiş ama henüz finalize edilmemiş key için).

**EK — derin kontrol (dördüncü tur) bulgusu #2, 2026-07-01: rezervasyonun kendisi sessizce kayboluyordu (`POST /trips/` özelinde).** "Reserve-then-create"in İLK hâli, rezervasyon INSERT'ini çağıranın paylaşılan request-UoW session'ında (`uow.session`) aynı transaction içinde yapıyordu — "aynı transaction = atomik" varsayımıyla. Bu varsayım `POST /trips/` için YANLIŞ çıktı: `SeferWriteService.add_sefer` → `_predict_outbound`, ML tahminine 2.5s `asyncio.wait_for` timeout uyguluyor (bkz. CLAUDE.md "Sefer yakıt tahmini"); test ortamında tahmin pipeline'ı (RAG/HuggingFace network çağrıları) bunu HER SEFERİNDE aşıyor. `asyncio.wait_for` timeout'ta iç task'ı `CancelledError` ile iptal ediyor; bu iptal, tahmin pipeline'ının kendi (non-owning, paylaşılan session'a bağlı) `async with UnitOfWork()` bloğu İÇİNDEYKEN gerçekleşirse, `UnitOfWork.__aexit__` bunu hata sayıp `rollback()` çağırıyor — `rollback()` `_owns` kontrolü YAPMIYOR (ayrı, bağımsız bir bulgu — bkz. aşağıdaki "Kapsam dışı bırakılan ek bulgu"), yani PAYLAŞILAN session'ın TÜMÜNÜ (henüz commit edilmemiş rezervasyon satırı dahil) geri alıyor. Sefer kaydı yine de başarıyla oluşuyordu çünkü ondan SONRAKİ INSERT'ler session'ın otomatik açtığı YENİ transaction'a düşüyordu — ama rezervasyon o yeni transaction'da YOKTU, sessizce kayboluyordu. Sonuç: aynı key ile ikinci istek boş rezervasyon tablosu bulup GERÇEK bir ikinci sefer oluşturuyordu — madde 19'un tam önlemeye çalıştığı senaryo, sessizce geri geliyordu. Empirik kanıt: `test_trip_create_same_idempotency_key_does_not_duplicate` DETERMİNİSTİK olarak kırmızıydı (2 ayrı çalıştırmada da `assert 2 == 1` — rezervasyon satırının ilk isteğin sonunda DB'de HİÇ olmadığı doğrudan sorgulanarak doğrulandı).

**Fix:** İdempotency defteri artık çağıranın UoW'undan TAMAMEN BAĞIMSIZ, kendi kısa ömürlü session'ında (`app.database.connection.AsyncSessionLocal`, modül-attribute erişimiyle — test fixture monkeypatch'i hâlâ geçerli) anında commit ediyor. Böylece ana iş-transaction'ında (add_sefer içinde) her ne olursa olsun (cancel/rollback/retry), rezervasyon kaydı etkilenmiyor — bu, Stripe'ın gerçek idempotency-key implementasyonlarının da kullandığı, idempotency defterini iş transaction'ından kasıtlı olarak ayrı tutan desen. Bedeli: gerçek iş başarısız olursa rezervasyon "pending" kalıp gelecek retry'ları kilitleyebilir — bunu önlemek için yeni `release_reservation()` eklendi, `fuel.py`/`trips.py`'nin TÜM hata yollarında (ValueError/DomainError/HTTPException/generic Exception) çağrılıyor (resource'un GERÇEKTEN oluşup serileştirme aşamasında patladığı nadir bir trips.py iç senaryosu hariç — orada pending bırakmak, retry'ın YANLIŞLIKLA ikinci bir kayıt oluşturmasından daha güvenli).

**Doğrulama:** Fix sonrası `test_trip_create_same_idempotency_key_does_not_duplicate` 4/4 PASS (1 ilk + 3 tekrar, flaky değil). Yeni `test_reserve_or_get_cached_concurrent_first_use_does_not_500` testi eklendi — iki bağımsız DB session'ıyla (test fixture'ının tekil paylaşılan session'ını bypass ederek) gerçek eşzamanlı rezervasyon yarışını A/B senkronize event'lerle üretiyor: A reserve eder, B (A henüz finalize etmeden) aynı key'i dener → artık yakalanmamış hata yerine zarif `IdempotencyKeyInProgressError` alıyor; A finalize ettikten sonra üçüncü bir çağrı önbelleklenmiş yanıtı görüyor; tabloda tam 1 satır kalıyor. Tam idempotency dosyası 6/6 PASS. Geniş regresyon: `test_fuel*.py`+`test_trips*.py`+`test_idempotency_key.py` 148/148 PASS; `test_investigations_patch_race.py`+`test_investigations_coverage.py`+`test_investigations_more.py`+`test_admin_ws_coverage.py`+`test_arac_service.py` 105/105 PASS. `ruff` temiz; `mypy` 7 hata (baseline, aynı, hiçbiri değiştirilen dosyalarda).

**Kapsam dışı bırakılan ek bulgu (bu turda düzeltilmedi, ayrı bir madde gerektirir):** `UnitOfWork.rollback()` (`app/database/unit_of_work.py:192`) `commit()`'in aksine `_owns` kontrolü yapmıyor — non-owning (nested) bir UoW'un `__aexit__`'i, İÇİNDE `asyncio.CancelledError` dahil HERHANGİ bir exception yakalarsa (yalnızca gerçek DB hataları değil), PAYLAŞILAN request-seviyesi session'ı TAMAMEN geri alıyor. Bu, `UnitOfWork` her yerde kullanıldığı için geniş blast-radius'lu bir mimari değişiklik gerektiriyor (bu oturumun "mimari epik onayı olmadan dokunma" kısıtı kapsamında) — item 19'un kapsamı dışında bırakıldı, idempotency defterini bağımsız hale getirerek DOLAYLI olarak etkisiz kılındı ama kök neden hâlâ kod tabanında duruyor ve başka bir nested-UoW+unrelated-cancellation senaryosunda benzer sessiz veri kaybına yol açabilir. Ayrı bir denetim maddesi olarak önerilir.

---

### 20. Dalga 4 — madde 20: sınırsız `limit` parametreleri, 2026-07-01

**Neden:** Audit raporu `anomalies.py`, `admin_imports.py`, `admin_ml.py`, `admin_notifications.py`'yi işaret etmişti. Yeniden tarama sonucunda: `anomalies.py` zaten `Query(50, ge=1, le=200)` ile sınırlıydı (audit'ten sonra ayrı bir turda düzeltilmiş olmalı) — dokunulmadı. `admin_notifications.py`'nin `get_my_notifications` endpoint'i client-controllable bir `limit` parametresi hiç almıyor (repository seviyesinde sabit `limit=50` hardcoded, query param olarak dışa açılmamış) — exploit edilebilir değil, dokunulmadı. Gerçek sınırsız iki nokta bulundu: `admin_imports.py:126` (`import_history`) ve `admin_ml.py:75` (`get_training_queue`) — ikisi de düz `limit: int = 50` (Query değil, hiçbir üst sınır yok). Ek olarak, aynı tarama sırasında audit'in listelemediği bir üçüncü nokta bulundu: `fuel.py:98` (`read_yakit_alimlari`, `limit: int = 20`) — `YakitService.get_all_paged` bu değeri hiçbir clamp olmadan doğrudan repository'ye geçiriyor.

**Sonuç:** Üç noktada da `limit: int = Query(<eski varsayılan>, ge=1, le=200)` — `anomalies.py`'deki mevcut desenle tutarlı üst sınır.

**Doğrulama:** 3 yeni test (`test_import_history_rejects_huge_limit`, `test_ml_queue_rejects_huge_limit`, `test_read_yakit_alimlari_rejects_huge_limit`) — `?limit=999999999` → 422 bekleniyor. Kırmızı-yeşil doğrulandı (fix öncesi üçü de 200 dönüyordu). Tüm endpoint dosyaları `limit: int = <sayı>` (Query/le= olmadan) deseni için yeniden tarandı, başka kaçırılan nokta bulunamadı. Regresyon: `test_admin_imports.py`+`test_admin_imports_coverage.py`+`test_admin_ml.py`+`test_fuel_coverage.py`+`test_anomalies.py` toplam 73/73 PASS. `ruff`+`mypy` temiz (baseline 7, aynı).

---

### 21. Dalga 4 — madde 21: WebSocket bağlantı sayısı sınırı, 2026-07-01

**Neden:** `ConnectionManager.connect()` (`app/api/v1/endpoints/admin_ws.py`) bağlantı sayısını hiç sınırlamıyordu — aynı kullanıcı (email) sınırsız sayıda WS bağlantısı açabiliyordu, reconnect-storm/DoS riski. HTTP endpoint'lerindeki `RateLimiterDependency` WS upgrade'e uygulanmıyordu (auth akışının kendisi zaten sağlamdı — handshake öncesi ticket/token + permission kontrolü ayrı bir konu).

**Sonuç:** `_MAX_CONNECTIONS_PER_USER = 5` eklendi. `ConnectionManager.connect()` artık `bool` dönüyor — limit aşılırsa `websocket.accept()` hiç çağrılmadan `close(code=WS_1008_POLICY_VIOLATION)` ile reddediliyor. Her iki WS route'u (`/training`, `/live`) da dönüş değerini kontrol edip reddedilen bağlantıda receive döngüsüne hiç girmiyor.

**Doğrulama:** 3 yeni test: `test_connect_returns_true_on_success`, `test_connect_rejects_beyond_max_connections_per_user` (limit+1'inci bağlantı reddedilir, `accept()` hiç çağrılmaz, `close()` çağrılır), `test_connect_allows_new_connection_after_disconnect_frees_a_slot` (regresyon guard'ı — disconnect sonrası slot boşalınca yeni bağlantı kabul edilir). Kırmızı-yeşil git-stash ile doğrulandı. Regresyon: `test_admin_ws.py`+`test_admin_ws_coverage.py` 40/40 PASS. `ruff` temiz, mypy'de `admin_ws.py`'ye ait yeni hata yok (gösterilen 3 hata baseline'daki bilinen dosyalarda — `event_bus.py`, `rol_repo.py`).

---

### 22. Dalga 4 — madde 22: test suite integration marker eksikliği — ÖLÇÜLDÜ, UYGULANMADI (geri alındı), 2026-07-01

**Neden:** Audit'in bulgusu doğrulandı: `app/tests/unit/` altında `db_session` fixture'ı kullanan (gerçek DB'ye vuran) ama `@pytest.mark.integration` taşımayan **44 dosya** bulundu (audit'in "42+" tahminine yakın). CI'ın hızlı-lane coverage komutu (`pytest -m "unit or not integration" ... --cov-fail-under=92`, `.github/workflows/ci.yml:442`) bu yüzden fiilen "hızlı/mock'lu" değil — gerçek DB'ye vuran çok sayıda test de bu koşuya dahil oluyor.

**Ölçülen etki (kullanıcı onayıyla, doğrudan uygulama öncesi ölçüldü):**
- **Baseline** (44 dosya işaretlenmeden önce, mevcut durum): `pytest -m "unit or not integration" --cov-fail-under=92` → **%91.71** coverage — bu, benim bu oturumdaki çalışmamdan TAMAMEN BAĞIMSIZ, ÖNCEDEN VAR OLAN bir durum: CI'ın coverage gate'i (%92) yerel ölçümde ZATEN başarısız (küçük bir farkla, %0.29). Ayrıca 6 test fail ediyor — bunların hepsi bu oturumdaki değişikliklerle ilgisiz, bilinen ortam-bağımlı/pre-existing testler (`test_use_sefer_fuel_estimator_opt_in_default_false`, `test_sefer_write_service_prediction_flows.py`'deki 2 test — hepsi zaten `.env`'deki `USE_SEFER_FUEL_ESTIMATOR=true` ayarıyla çakışan bilinen sorunlar) + Windows/asyncpg transient flake (`test_concurrent_trip_creation`, diğerleri).
- **44 dosya `pytest.mark.integration` ile işaretlendikten SONRA**: aynı komut → **%86.57** coverage — **5.14 puanlık düşüş**. Gate zaten başarısızken şimdi çok daha büyük bir farkla başarısız.

**Karar: madde UYGULANMADI, tüm değişiklikler geri alındı.** 5 puanlık bir coverage düşüşü, mevcut CI gate'ini (zaten sınırda olan) ciddi şekilde kırar — bu, sadece marker eklemekle çözülecek bir madde değil, bu 44 dosyanın kapsadığı kod yollarını gerçekten MOCK'lu unit testlerle YENİDEN yazmayı gerektiren, çok daha büyük bir ayrı epik. Audit'in tespiti doğru (lane ayrımı fiilen sahte) ama düzeltmesi bu oturumun kapsamının çok ötesinde — coverage gate'i düşürmek (kabul edilebilir mi?), 44 dosyanın gerçek DB kısmını mock'lu hâle getirmek (haftalar sürebilir), veya farklı bir CI stratejisi (ayrı bir "gerçekten hızlı" lane oluşturmak, mevcut `unit`/`integration` etiketlemesini değiştirmeden) — hepsi ayrı bir tasarım kararı ve onay gerektiriyor.

**Bonus bulgu (bu oturumdan bağımsız, ayrıca not düşülüyor):** Mevcut `main` dalındaki CI coverage gate'i (%92) yerel ölçümde zaten %91.71 ile marjinal şekilde başarısız — bu, ayrı bir P1/P2 bulgusu olarak ele alınmayı hak ediyor (ya gate hafifçe gevşetilmeli ya da eksik %0.3'lük coverage kapatılmalı). Kod değişikliği yapılmadı, sadece ölçüldü ve rapor edildi.

---

### 23. Dalga 4 — madde 23: `test_arac_service.py` plaka validasyon skip'i, 2026-07-01

**Neden:** `test_valid_plaka_formats` (`app/tests/unit/test_services/test_arac_service.py:76-92`) `AracCreate(plaka=...)` çağrısını `try/except: pytest.skip("Plaka validation not strict")` ile sarmalıyordu — validasyon gerçekten hata fırlatsaydı (bozuk/gevşek validasyon) test SESSİZCE geçerdi, hiçbir uyarı vermezdi. Ayrıca aynı sınıfta `test_add_vehicle_plaka_format` tamamen boş bir `pass` stub'ıydı — hiçbir şey doğrulamıyordu.

**Sonuç:** `validate_plaka_str` (`app/core/entities/models.py:202-213`) incelendi — gerçek, çalışan bir regex-tabanlı validasyon (regex sınıfları: 1 harf+4 rakam, 2 harf+3-4 rakam, 3-4 harf+2-3 rakam). Testteki 3 örnek plaka zaten geçerli formatlar — `try/except`/skip kaldırıldı, doğrudan normalize edilmiş çıktı assert ediliyor. Yeni `test_invalid_plaka_format_raises` regresyon guard'ı eklendi (gerçekten geçersiz bir plaka `ValidationError` fırlatmalı). Boş `test_add_vehicle_plaka_format` stub'ı silindi (amacı artık `test_invalid_plaka_format_raises` tarafından karşılanıyor).

**Doğrulama:** `test_arac_service.py` tam dosya 11/11 PASS (6 skip artık gerçek assertion). `ruff` temiz.

---

### 24. Dalga 4 — madde 24: `test_admin_calibration.py` mock kapsamı — ZATEN ÇÖZÜLMÜŞ, kod değişikliği gerekmedi, 2026-07-01

**Neden (audit'in orijinal bulgusu):** `test_admin_calibration.py`'nin `RouteCalibrationService`'in tamamını mock'ladığı, gerçek kalibrasyon algoritmasının hiç çalışmadığı, regresyon yakalanamayacağı iddia edilmişti.

**Doğrulama sonucu:** `app/tests/unit/test_services/test_route_calibration_coverage.py` incelendi — bu dosya `RouteCalibrationService`'i GERÇEK DB ile, mock'suz, kapsamlı şekilde test ediyor: `calibrate_route_from_trip`'in gerçek yazma yolu (`TestCalibrateRouteWritePath::test_creates_new_calibration`, `test_updates_existing_calibration_resets_match_count`) ve `match_sefer_to_path`'in gerçek eşleştirme mantığı (5+ senaryo, `TestMatchSeferToPath*` sınıfları) dahil. `test_admin_calibration.py`'nin servisi mock'laması, projedeki TÜM diğer endpoint test dosyalarıyla tutarlı standart mimari (endpoint-katmanı testleri auth/permission/response-shape'i doğrular, servis-katmanı testleri gerçek algoritmayı doğrular — iki ayrı dosya, iki ayrı sorumluluk).

**Sonuç: kod değişikliği yapılmadı.** Audit'in bulgusu ya raporun yazıldığı andan sonra (bu oturumdan önceki bir turda) zaten kapatılmış, ya da başından beri iki dosyanın birlikte sağladığı kapsamı hesaba katmamış. Her iki dosya birlikte çalıştırılıp 26/26 PASS ile doğrulandı — gerçek algoritma regresyonları zaten yakalanıyor.

---

### 25. Dalga 4 — madde 25: Frontend (5 kalem), 2026-07-01

**Neden:** Audit 5 ayrı frontend bulgusu listelemişti — hepsi bu oturumda tek tek kırmızı-yeşil disipliniyle kapatıldı.

**25a — `TripTable.tsx` virtualizer `getItemKey` eksik.** **KAPANDI** — `useVirtualizer`'a `getItemKey: (index) => trips[index]?.id ?? index` eklendi. Eskiden satır kimliği index'e bağlıydı — 15sn polling'de veri kayıp/eklenince yanlış satır animasyonu/scroll kayması olabiliyordu. Yeni test (`TripTableVirtualizerKey.test.tsx`) `getItemKey`'in `trip.id`'ye bağlı olduğunu, index'e değil, doğruluyor (baştaki satır kaybolup yeniden render edildiğinde kalan sefer AYNI key'i taşıyor). Kırmızı-yeşil doğrulandı. 118/118 trips testi PASS.

**25b — `use-ai-store.ts` `isOpen` persist ediliyor ama mount'ta `checkStatus()` tetiklenmiyor.** **KAPANDI** — kök neden `ChatAssistant.tsx`'teki polling effect'te bulundu: `setInterval(checkStatus, 5000)` kuruluyordu ama İLK çağrı hiç yapılmıyordu — `isOpen: true` persist'ten geri geldiğinde panel açık görünüp status 5 saniye boyunca stale ("offline") kalıyordu. Fix: effect artık `checkStatus()`'u hemen bir kez çağırıyor, sonra interval kuruyor. Yeni test (fake timers ile, interval'ı hiç ilerletmeden `checkStatus`'un çağrıldığını doğruluyor) kırmızı-yeşil doğrulandı. 18/18 ChatAssistant + 8/8 use-ai-store testi PASS.

**25c — `react-hooks/exhaustive-deps` proje genelinde kapalıydı.** **KAPANDI** — `eslint.config.js`'de `"off"` → `"error"`. Etkinleştirilince SADECE 13 ihlal çıktı (audit'in ima ettiğinden çok daha az): 11'i gerçek eksik-bağımlılık (çoğu i18n metin-kaynağı objesi referansı veya `t`/`onComplete`/`task.result` gibi genuine eksiklikler — deps array'e eklendi; `handleCalculate` `useCallback`'e sarıldı), 2'si kasıtlı mount-only deep-link-tüketme efekti (`TripsModule.tsx`, `AlertsPage.tsx`) — bunlar gerekçeli `eslint-disable-next-line` yorumuyla belgelendi (yeniden çalışırlarsa URL parametrelerini yanlışlıkla tekrar uygularlar). `npm run lint` (`--max-warnings 0`) temiz. 1188/1191 frontend testi PASS (3 fail ÖNCEDEN VARDI, bu değişiklikle ilgisiz — `git stash` ile doğrulandı, aynı 3 test stash'lenmiş haliyle de fail ediyor).

**25d — 429 rate-limit yanıtı hata zarfını bypass ediyordu.** **KAPANDI** — kök neden `app/infrastructure/middleware/rate_limit_middleware.py`'de bulundu: `{"detail": "..."}` dönüyordu, projenin standart `{"error": {"code","message","trace_id"}}` zarfını (bkz. `main.py` `http_exception_handler`) bypass ediyordu (middleware, `HTTPException` raise etmek yerine ham `JSONResponse` döndürdüğü için FastAPI'nin merkezi exception handler zincirine hiç girmiyordu). Backend fix: envelope'a uygun hale getirildi (`code: "RATE_LIMITED"`, `trace_id: get_correlation_id()`). Frontend fix: `axios-instance.ts`'nin response interceptor'ına `status === 429` case'i eklendi (400/403/422/5xx'in yanına) — artık kullanıcı bir toast görüyor. Yeni backend testi (`test_rate_limit_middleware_coverage.py`) + yeni frontend testi (`axios-instance.test.ts`, ilk axios-instance testi — önceden hiç yoktu) kırmızı-yeşil doğrulandı. `RateLimiterDependency` (rate_limiter.py, farklı bir 429 kaynağı) zaten `HTTPException` raise ediyordu — merkezi handler'dan otomatik doğru zarfı alıyor, dokunulmadı. Backend: 25/25 rate-limit test PASS. Frontend: 107/107 api-service test PASS.

**25e — Modallerde focus-trap yoktu (WCAG 2.1 AA).** **KAPANDI** — paylaşılan `src/components/ui/Modal.tsx`'e (12 tüketicisi var: FuelModal, LocationFormModal, TripFormModal, BulkCancelModal/BulkStatusModal, BreakdownReportModal, AnalysisModal, FeedbackButton, 4 admin sayfası) gerçek focus-trap eklendi — açılışta odak diyalog içine taşınıyor, Tab/Shift+Tab diyalog sınırlarında döngü yapıyor (dışarı kaçmıyor), kapanışta odak tetikleyici elemana geri veriliyor. `aria-modal`/`role="dialog"` zaten mevcuttu (audit'in bu kısmı zaten doğruydu ama focus-trap kısmı eksikti). Yeni `Modal.test.tsx` (4 test: açılış-odağı, Tab-döngüsü, Shift+Tab-döngüsü, kapanış-odak-restore) kırmızı-yeşil doğrulandı. Ad-hoc (paylaşılan Modal kullanmayan) modal implementasyonlarına (ChatAssistant paneli, ExportDialog vb.) bu turda dokunulmadı — kapsam paylaşılan primitive ile sınırlı tutuldu.

**Regresyon (25a-e birlikte):** `npx vitest --run` (tam frontend paketi) → 1188 passed, 3 pre-existing fail (ilgisiz). `npm run lint` temiz. `npx tsc --noEmit` temiz.

---

### 26. Dalga 4 — madde 26: ML (2 kalem), 2026-07-01

**26a — Feature-schema doğrulaması sadece sayı kontrolü yapıyordu, isim/sıra değil.** **KAPANDI** — kök neden doğrulandı: `EnsembleFuelPredictor.__init__` zaten `self._feature_hash` hesaplıyordu (`FEATURE_NAMES`'in SIRALI hash'i — isim+sıra'yı yakalar) ama `save_model()` bunu `_meta.json`'a hiç yazmıyordu, `load_model()` hiç okumuyordu; `ensemble_service.get_predictor()`'daki tek şema kontrolü `_resolve_expected_feature_count()` (SAYI, sklearn `n_features_in_`) idi. Sonuç: feature SAYISI aynı kalıp isim/sıra değişirse (kod değişikliği ile feature listesi yeniden düzenlenirse) sessiz feature-drift mümkündü — model eski feature-sırasına göre eğitilmiş kalırken runtime farklı sırada veri besliyor, hiçbir uyarı yok. Fix: `save_model()` artık `feature_schema_hash` yazıyor; `load_model()` bunu `self._loaded_feature_schema_hash`'e okuyor; `get_predictor()` artık HEM sayı HEM hash karşılaştırıyor — hash uyuşmazlığında (sayı aynı olsa bile) `is_trained=False` (physics fallback), tıpkı sayı-uyuşmazlığı durumundaki gibi. Persisted hash `None` ise (bu alan eklenmeden önce kaydedilmiş eski model dosyası) karşılaştırma atlanıyor — false positive üretmiyor. 4 yeni test (2 `ensemble_core.py` save/load round-trip, 2 `ensemble_service.py` hash-mismatch/hash-match) kırmızı-yeşil doğrulandı; 1 pre-existing mock testi güncellendi (MagicMock'un otomatik-üretilen alt-mock'ları gerçek string hash'i taklit etmiyordu, false positive üretiyordu — `_feature_hash`/`_loaded_feature_schema_hash` artık açıkça eşleşen string'lere set ediliyor). 457/457 ML test suite PASS. `ruff`+`mypy` temiz (baseline 7, aynı).

**26b — `VEHICLE_AGE_DEGRADATION_RATE` config alanı ölü kod iddiası.** **ZATEN ÇÖZÜLMÜŞ / audit bulgusu geçersiz, kod değişikliği gerekmedi.** Doğrulama: `grep -rn VEHICLE_AGE_DEGRADATION_RATE` `app/services/prediction_service.py:372`'de GERÇEKTEN okunuyor (`age_factor = max(1.0 - settings.MAX_AGE_DEGRADATION, 1.0 - age * settings.VEHICLE_AGE_DEGRADATION_RATE)`, araç 5 yaşından büyükse motor verimliliğine uygulanıyor) — audit'in "hiçbir yerde okunmuyor" iddiası bu haliyle YANLIŞ. Audit'in "gerçek yaş etkisi entities/models.py'de hardcoded sabitlerle hesaplanıyor" iddiası da dosya olarak yanlış — `entities/models.py`'de hiç age-degradation mantığı yok; GERÇEK hardcoded ikinci implementasyon `app/core/services/sefer_fuel_estimator.py:413-420`'de (Phase 4-5 YENİ estimator pipeline, `USE_SEFER_FUEL_ESTIMATOR` feature-flag'li, CLAUDE.md'de belgeli) — tamamen farklı bir formül (`0.98`/`1.0`/`1.02+...`/`1.05+...` merdiveni). Yani gerçek durum: İKİ AYRI, TUTARSIZ yaş-degradasyonu implementasyonu var (biri config-driven legacy `prediction_service.py` yolunda, biri hardcoded yeni `sefer_fuel_estimator.py` yolunda) — ama HİÇBİRİ "ölü kod" değil, ikisi de feature-flag'e göre aktif. Bu turda kod değişikliği YAPILMADI: `sefer_fuel_estimator.py`'nin formülü CLAUDE.md'nin belgelediği gibi gerçek-dünya rota verisiyle kalibre edilmiş (`scripts/p51_real_world_validation.py`) — config değerine geçirmek kalibrasyon onayı gerektiren ayrı bir karar, bu maddenin (yanlış teşhis edilmiş "ölü kod" bulgusunun) kapsamı dışında.

**Regresyon (26a-b):** yukarıdaki 457/457 ML suite + `ruff`/`mypy` temiz.

---

## Ek: `get_by_id` Soft-Delete Filtresizliği — 62 Çağrı Noktasının Tam Sınıflandırması

`BaseRepository.get_by_id` (`app/database/base_repository.py:207-222`) `session.get(self.model, id)` çalıştırır, `aktif`/`is_deleted` filtresi yoktur. Sadece `SeferRepository.get_by_id` (`sefer_repo.py:267-292`) bunu doğru şekilde override eder. Aşağıdaki 6 model/repository kümesindeki **62 gerçek çağrı noktasının her biri tek tek okunup** (~20-30 satır çevresel bağlamla) üç kategoriye ayrıldı:
- **GERÇEK BUG**: soft-deleted kayıt bu noktadan geçtiğinde yanlış bir iş sonucu (veri bozulması, yetkisiz işlem, hatalı hesaplama kalıcı yazılır) üretiliyor.
- **ZATEN KORUNUYOR**: aynı fonksiyonda (veya çağıranında) ayrı bir `aktif`/`is_deleted` kontrolü zaten var, ya da çağrı kasıtlı olarak pasif kaydı görmesi gereken bir akışın (örn. hard-delete'in ikinci aşaması) parçası.
- **ZARARSIZ AMA TUTARSIZ**: salt-okunur rapor/AI-context/tahmin-girdisi zenginleştirmesi — state bozulmuyor ama pasif/silinmiş veri sızıyor.

### Özet tablo

| Repository (Model) | Toplam | Gerçek Bug | Zaten Korunuyor | Zararsız/Tutarsız | N/A – Ölü kod |
|---|---|---|---|---|---|
| `arac_repo` (Arac) | 19 | **3** | 3 | 13 | 0 |
| `sofor_repo` (Sofor) | 10 | **5** | 2 | 3 | 0 |
| `dorse_repo` (Dorse) | 6 | **1** | 1 | 4 | 0 |
| `lokasyon_repo` (Lokasyon) | 13 | **6** | 1 | 6 | 0 |
| `yakit_repo` (YakitAlimi) | 3 | **1** | 0 | 2 | 0 |
| `kullanici_repo` (Kullanici) | 5 | **0** | 5 | 0 | 0 |
| `lokasyon_repo`/`yakit_repo` iç çağrılar | 2 | 0 | 0 | 2 (ikisi de prod'da kullanılmıyor/tekil-satır) | 0 |
| `dorse_service.get_by_id` | (dahil) | 0 | 0 | 0 | 1 (hiç çağrılmıyor) |
| **Toplam** | **~59+3** | **16** | **12** | **30** | **1** |

### Gerçek bug'ların tam listesi (16)

**Araç (3):**
- `app/core/services/arac_service.py:195` (`_update_arac_impl`) — `arac_id` her ne olursa olsun `get_by_id`+`update()` çağrılıyor; pasif/soft-deleted bir araç, `create_arac`'ın özel reaktivasyon akışını bypass ederek doğrudan `PATCH /vehicles/{id}` ile sessizce güncellenebiliyor.
- `app/core/services/maintenance_service.py:64` (`create_maintenance_record`) — sadece `if not arac: raise 404`, `aktif` kontrolü yok; pasif araca yeni planlı bakım kaydı açılabiliyor.
- `app/core/services/maintenance_service.py:107` (`create_breakdown`) — aynı desen; pasif araca arıza/acil bakım kaydı açılabiliyor.

**Şoför (5):**
- `app/core/ai/driver_coaching_engine.py:80` — silinmiş şoför için de coaching insights üretilip LLM'e gönderiliyor, `aktif` kontrolü yok.
- `app/core/services/sofor_service.py:138` (`SoforService.get_by_id` gövdesi) — filtresiz genel-amaçlı getter; API kontratı sızıntısı, gelecekteki her çağıran güvensiz.
- `app/core/services/sofor_service.py:158` (`update_sofor`, manual_score dalı) — `if current:` truthy check soft-deleted kayıtta da geçer → silinmiş şoförün skoru güncellenebiliyor.
- `app/core/services/sofor_service.py:212` (`update_score`) — aynı desen, `aktif` kontrolü yok; silinmiş şoförün `manual_score`/`score` alanları güncellenebiliyor.
- `app/services/prediction_service.py:645` (`_fetch_entities`) — filtresiz şoför verisi ensemble/physics tahmin pipeline'ına input olarak gidiyor; silinmiş şoförün eski manual_score'u sessizce tahmine karışabilir.

**Dorse (1):**
- `app/core/services/maintenance_service.py:113` (`create_breakdown`, dorse existence-gate) — retire edilmiş dorse için de arıza kaydı açılabiliyor (araç ile aynı kök neden, aynı fonksiyon).

**Lokasyon (6):**
- `app/core/ai/trip_planner.py:255` (`_fetch_route_analysis`) — pasif güzergahın stale `route_analysis` JSON'ı AI trip-planner sınıflandırmasına sızıyor.
- `app/core/ai/trip_planner.py:289` (`_weather_impact`) — pasif lokasyonun eski koordinatlarıyla canlı hava-durumu etkisi hesaplanıp planlama skoruna karışıyor.
- `app/core/services/lokasyon_service.py:310` (`analyze_route`) — soft-deleted lokasyon üzerinde canlı rota-analizi API'si tetiklenip sonuç DB'ye geri yazılabiliyor (silinmiş kaydın sessizce zenginleştirilmesi).
- `app/core/services/sefer_write_service.py:281` (sefer **update**, `guzergah_id` değişirse) — bkz. P0 tablo madde 1b.
- `app/core/services/sefer_write_service.py:402` (`_resolve_route`, sefer **create**) — bkz. P0 tablo madde 1b; CLAUDE.md'nin işaret ettiği tahmin-doğruluğu riskiyle doğrudan bağlantılı.
- `app/core/services/route_calibration_service.py:37` (`_get_lokasyon`) — şu an `verification_available=False` sabit döndüğü için fonksiyonel etkisi yok (dead-ish path), ama ileride spatial-matching implement edilirse silinmiş güzergah verisiyle GPS eşleştirmesi yapılabilecek şekilde tasarlanmış — **P2, izlenmeli**.

**Yakıt (1):**
- `app/core/services/yakit_service.py:194` (`update_yakit`, `for_update=True`) — soft-delete edilmiş (`aktif=False`) bir yakıt alım kaydı, `aktif` kontrolü yapılmadan `fiyat_tl`/`litre`/`toplam_tutar` alanlarından doğrudan düzenlenebiliyor; "silinmiş" finansal veri sessizce mutasyona uğruyor.

### Zaten korunan noktalar (12) — neden risk taşımadıkları

- `arac_service.py:251` (`delete_arac`) — kasıtlı: fonksiyon zaten pasif kaydı hard-delete'e geçirmek için tasarlanmış, filtre olsaydı bu ikinci aşama çalışmazdı.
- `yakit_service.py:124` (`add_yakit`) ve `sefer_write_service.py:833,842` (`create_sefer`) — üçü de aynı satırda açık `arac.get("aktif")`/`sofor.get("aktif")` kontrolü içeriyor.
- `sofor_service.py:182` (`_delete_sofor_uow`) — kendi içinde `if not current or current.get("is_deleted"): return False` ile idempotent silme guard'ı zaten var.
- `lokasyon_service.py:236` (`delete_lokasyon`) — smart-delete state machine'inin parçası, pasif kaydı görmesi gerekli.
- `trailers.py:156`, `vehicles.py:145`, `user_service.py:62` — üçü de "az önce oluşturulan taze kaydı geri oku" paterni, soft-delete ihtimali yok.
- `user_service.py:25,72,103,129` — **kullanici_repo kümesinin tamamı korunuyor**: `app/api/deps.py:264-284`'teki `get_current_user` guard'ı deaktif bir kullanıcının JWT doğrulaması aşamasında 403 ile tamamen engelleniyor; bu satırlara ulaşan `user_id` ya zaten aktif bir aktörün kendi kaydıdır (`change_password`) ya da yetkili bir admin'in bilinçli olarak hedef aldığı (belki deaktif) bir kayıttır (`update_user`/`get_user` — reaktivasyon/rol düzeltme zaten admin'in yapması gereken meşru işlem).

### Zararsız-ama-tutarsız (30) ve ölü kod (1)

Bu grup çoğunlukla salt-okunur raporlama (`report_service.py:226,266`), AI-context zenginleştirme (`context_builder.py:97`, `recommendation_engine.py:65`, `rag_sync_service.py:92`), XAI açıklanabilirlik uçları (`sofor_service.py:289,348`), ve ML tahmin-girdisi zenginleştirme (`ensemble_service.py:243,512,514,523,525`, `prediction_service.py:641,649`) çağrılarından oluşuyor — hiçbiri state değiştirmiyor ama pasif/silinmiş varlık verisi kullanıcıya/modele sızmaya devam ediyor. `DorseService.get_by_id` (`dorse_service.py:29`) ve `LokasyonRepository.get_with_elevation` (`lokasyon_repo.py:123`) prod kodunda hiçbir yerden çağrılmadığı doğrulandı — risk yok, temizlenebilir.

### Kök çözüm — ✅ UYGULANDI

Önerilen kök çözüm (`BaseRepository.get_by_id`'ye otomatik `aktif`/`is_deleted` filtresi + `include_inactive: bool = False` bypass parametresi) ve 16 gerçek-bug noktasının tamamı bu turda kodda düzeltildi — detay, dosya listesi ve doğrulama kanıtları için bkz. yukarıdaki "Uygulanan Düzeltmeler — Neden/Sonuç" bölümü madde 1. Salt-okunur 30 "zararsız-ama-tutarsız" nokta kullanıcı talimatıyla kapsam dışı bırakıldı, mevcut haliyle (kök fix'in doğal filtrelemesiyle) kaldı.

---

## P1 — Yakın vadede ele alınmalı

### Mimari sınır ihlalleri
- **`app/core/services/*` neredeyse tamamı repository'yi atlayıp ham SQL çalıştırıyor** (`ai_service.py:206-207`, `anomaly_detector.py:286,347,598,635`, `import_service.py:335-513` DELETE dahil, `yakit_service.py:71`, `sefer_write_service.py:1301` vb.) — kural "core/services repository üzerinden gider" fiilen terk edilmiş, analytics/agregasyon sorguları repository soyutlaması dışında kalıyor.
- `tests/security/apply_model_changes.py` — Alembic dışı, doğrudan `ALTER TABLE kullanicilar ADD COLUMN ...` çalıştıran elle-yazılmış prod-şema script'i; CLAUDE.md'nin "asla elle DDL kullanma, her zaman `alembic upgrade head`" kuralını ihlal ediyor, confirm/dry-run kapısı yok. Test dizini içine gizlenmiş olduğundan normal script taramalarında atlanır. (`tests/security/apply_model_changes.py:9-16`)

### Veri güvenliği / Excel pipeline
- **Excel export formula injection**: `excel_exporter.py:182,361` `xlsxwriter`'ın varsayılan `strings_to_formulas=True` davranışını devre dışı bırakmıyor; import tarafında (`excel_parser.py:227-228,280,335-336`) serbest metin alanları (`notlar`, `marka`, `model`, `ad_soyad`) sanitize edilmiyor. Saldırı zinciri: kullanıcı `notlar="=HYPERLINK(...)"` import eder → DB'de düz metin → admin export edip Excel'de açınca formül çalışır (klasik CSV/Excel injection). **P1.** ✅ **DÜZELTİLDİ** — bkz. "Uygulanan Düzeltmeler" madde 4 (ayrıca `export_service.py`'de daha önce bulunmamış ikinci bir örneği de kapatıldı).
- Excel import satır-sayısı/sheet-boyutu üst sınırı yok — `pd.read_excel` tüm dosyayı belleğe tek seferde yüklüyor; 10MB dosya boyutu sınırı var ama decompress sonrası zip-bomb benzeri şişme senkron worker'ı uzun süre bloklayabilir. **P2.**

### Repository / DB
*(`BaseRepository.get_by_id` soft-delete filtresizliğinin 16 gerçek bug'ı için ayrı, tam sınıflandırma yukarıdaki "Ek" bölümünde — burada tekrarlanmadı.)*
- `AdminConfigRepository.update_value` kilitsiz read-modify-write — eşzamanlı `PATCH /admin/config/{key}` lost-update + yanlış audit `eski_deger`. `admin_config_repo.py:33-65`.
- `Arac` modelinde ORM `cascade="all, delete-orphan"` ile DB `ondelete="RESTRICT"` çelişkisi — şu an aktif silme yolu RESTRICT'i koruyor ama gelecekte generic `session.delete()` eklenirse finansal kayıt (yakıt alımları) sessizce silinir. `models.py:128-136`.
- `Sefer.periyot_id` gerçek FK değil, "soft link" — orphan referans DB seviyesinde engellenmiyor, join'den sessizce düşüyor. `models.py:529-531`.
- `Anomaly.severity`, `Sefer.onay_durumu` gibi kritik enum-benzeri kolonlarda DB-seviye CHECK yok — typo'lu değer hiç engellenmiyor.

### Async/Celery
- Haftalık digest (`notification_tasks.py:65-67`) ve backfill (`prediction_backfill_tasks.py:37-45`) geniş `except Exception` ile hatayı yutup SUCCESS dönüyor — retry mekanizması fiilen devre dışı; manuel rerun'da push bildirimleri tekrar gönderiliyor (dedup yok).
- `BackgroundJobManager` job durumu sadece in-process asyncio task'a bağlı — worker restart'ta Redis'teki kayıt sonsuza dek "running" kalır, frontend `useTaskStatus` sonsuz poll eder. `job_manager.py:80-159`.

### API/Endpoint
- `investigations.py` PATCH'inde TOCTOU race — `SELECT FOR UPDATE` yok, eşzamanlı iki PATCH lost-update üretebilir. `investigations.py:416-475`.
- `fuel.py` ve `trips.py` POST uçlarında idempotency key yok — client timeout+retry çift yakıt/sefer kaydı oluşturabilir.
- `anomalies.py`, `admin_imports.py`, `admin_ml.py`, `admin_notifications.py` liste uçlarında `limit` üst sınırı yok — `?limit=999999999` tüm tabloyu/OOM riskini tetikler.
- `ai.py` `ChatRequest.message` `max_length` yok — MB boyutunda mesaj doğrudan LLM context'ine gidiyor (maliyet/DoS).

### WebSocket
- `ConnectionManager` (`admin_ws.py:22-66`) bağlantı sayısı sınırı uygulamıyor — aynı kullanıcı sınırsız WS bağlantısı açabilir (reconnect storm/DoS); HTTP endpoint'lerinde olan `RateLimiterDependency` WS upgrade'e uygulanmıyor. (Auth akışının kendisi sağlam — handshake öncesi ticket/token + permission kontrolü doğrulandı.) **P2.**

### Test suite
- 42+ dosya `app/tests/unit/` altında gerçek DB'ye vuruyor ama `@pytest.mark.integration` taşımıyor — "hızlı unit lane" sözleşmesi sahte, CI ayrım mantığı (`unit or not integration`) etkisiz.
- `test_arac_service.py:84-92` plaka validasyonu exception fırlatırsa testi `pytest.skip` ile geçiyor — bilinen gevşek validasyon kalıcı olarak görmezden geliniyor.
- `test_admin_calibration.py` `RouteCalibrationService`'in tamamını mock'luyor — gerçek kalibrasyon algoritması bu testte hiç çalışmıyor, regresyon yakalanmaz.

### Frontend
- `TripTable.tsx` virtualizer'da `getItemKey` yok — 15sn'de bir polling olan tabloda satır kimliği index'e bağlı, veri kayıp/eklenince yanlış satır animasyonu/scroll kayması.
- `use-ai-store.ts` `isOpen` persist ediliyor ama mount'ta `checkStatus()` tetiklenmiyor — panel açık görünüp stale durum gösterebilir.
- `react-hooks/exhaustive-deps` proje genelinde **kapalı** (`eslint.config.js:30-33`) — stale-closure bug'ları hiçbir linter tarafından yakalanmıyor.
- 194 adet `: any` kullanımı, özellikle hata yolu (`(error as any)?.response?.status`) — backend hata şekli hiç tip kontrolünden geçmiyor.
- 429 rate-limit yanıtı hata zarfını (`{error:{...}}`) bypass ediyor (`rate_limit_middleware.py:115-117`), frontend bunu hiç ele almıyor — kullanıcı rate-limit'e takılınca hiçbir geri bildirim almıyor.
- Modallerde `aria-modal`/focus-trap yok — WCAG 2.1 AA ihlali.

### ML/AI
- Feature-schema doğrulaması sadece **sayı** kontrolü yapıyor, isim/sıra değil; `feature_schema_hash` DB'ye yazılıyor ama model yüklenirken hiç okunup karşılaştırılmıyor — sessiz feature-drift mümkün. `ensemble_core.py:443-503`, `save_model:1216-1223`.
- `VEHICLE_AGE_DEGRADATION_RATE` config alanı tamamen ölü kod — hiçbir yerde okunmuyor, gerçek yaş etkisi `entities/models.py`'de hardcoded sabitlerle hesaplanıyor.

### Güvenlik
- Break-glass süper-admin MFA'sız, genel rate-limit'i paylaşıyor. ✅ **KISMEN DÜZELTİLDİ** — bkz. "Uygulanan Düzeltmeler" madde 10 (ayrı sıkı rate-limit eklendi; tam MFA kullanıcı kararıyla ayrı epik olarak bırakıldı).
- Rate-limit middleware slowapi eksikse sessizce devre dışı kalıyor (fail-open). ✅ **DÜZELTİLDİ** — bkz. "Uygulanan Düzeltmeler" madde 11 (prod'da artık fail-closed).
- Failed login / 403 izin reddi `admin_audit_log`'a yazılmıyor — saldırı tespiti zayıf. ✅ **DÜZELTİLDİ** — bkz. "Uygulanan Düzeltmeler" madde 12.
- `docker-compose.yml` `POSTGRES_PASSWORD` fallback'i `change-me`. ✅ **DÜZELTİLDİ** — bkz. "Uygulanan Düzeltmeler" madde 13.
- `ops_bot.py` webhook secret opsiyonel + fail-open; `/durum`,`/uyarilar` komutları kimliksiz erişilebilir, bilgi sızıntısı/recon riski. ✅ **DÜZELTİLDİ** — bkz. "Uygulanan Düzeltmeler" madde 14.

### Observability / Compliance / Scalability / CI-CD
- OpenTelemetry tamamen göstermelik — `TracerProvider` hiç set edilmemiş, `docs/observability.md` Jaeger/Tempo vaadi yanlış.
- PII (ad, telefon, email) plaintext, encryption-at-rest yok.
- Off-site backup default kapalı, otomatik restore-testi yok.
- Prod deploy'da otomatik rollback yok.
- Coverage raporu (htmlcov) 1 aydır güncellenmemiş, yanıltıcı referans.
- DB `max_connections=200`, prod pool ~20/replika → ~9-10 replikadan sonra tükenir, pgbouncer yok.
- Redis tek instans — cache+broker+rate-limit+event-dedup hepsi aynı anda düşer (SPOF).
- nginx tek `backend:8000` upstream'i — gerçek LB/Ingress olmadan yatay ölçek mimari olarak hazır değil.
- OpenAPI şemasının %34'ü (66/196 path) tipsiz — SDK/codegen güvenilmez.

---

## P2 — Orta öncelik

- Plaka validasyonu **3 farklı yerde 3 farklı regex** ile tekrarlanmış (`entities/models.py`, `import_service.py`, `schemas/arac.py`) — sessiz kabul/red tutarsızlığı.
- `vehicles.py`/`trailers.py` `inspection-alerts` ve `fleet-stats` neredeyse birebir kopya — trailers versiyonu muayene sayaçlarını **eksik bırakmış** (aktif veri kaybı, dashboard'da dorse muayene uyarı sayısı hiç hesaplanmıyor).
- `sefer_write_service.py` içinde 2.5s tahmin timeout'u 3 yerde hardcoded literal — biri güncellenip diğerleri unutulursa `coverage_pct` sessizce sapar.
- `PROCESSING/SUCCESS/FAILED` job durumu string'leri merkezi enum olmadan 5+ yerde hardcoded.
- Frontend silme-onay modalları (`VehicleDeleteModal`/`TrailerDeleteModal`) kopya-yapıştır; çoğu domain modal `ui/Modal.tsx`'i kullanmıyor.
- ARIMA fit'i geniş `except Exception` ile moving-average'a düşüyor, `success:True` ile sahte-başarı dönüyor.
- `Arac` yaş hesabı iki ayrı kaynaktan (`yil` vs `uretim_tarihi`) — senkron değilse ensemble ve SeferFuelEstimator farklı `yas_faktoru` kullanır.
- `import_service.py` dış catch tüm hataları "sistem hatası"na çeviriyor — DB-down gibi altyapı sorunları "validasyon hatası" gibi görünüp monitoring alarmı tetiklemiyor.
- `advanced_reports.py`/`preferences.py` ham `str(e)`'yi 500 detail'inde client'a sızdırıyor — bilgi sızıntısı, 2 satırlık fix.
- `route_repo.py` koordinat sorgusu composite/mekânsal index'siz, 4 ayrı B-tree index AND'leniyor.
- `PageView.user_id` FK eksik — diğer tüm audit alanlarının aksine.
- `audit_logger.log_audit_event` Python truthiness kullanıyor (`if old_value else None`) — `0`/`False`/`""`/`{}` gibi geçerli-falsy değerler sessizce audit trail'den düşüyor. `app/infrastructure/audit/audit_logger.py:295-296`.
- KVKK m.11 (erişim/silme hakkı) desteklenmiyor, soft-delete dışında erişim/silme endpoint'i yok.
- `admin_audit_log` sınırsız büyüyor, tamper-evidence yok.
- mypy "soft-baseline" gate (7 hata sabit kabul) teknik borcu donduruyor.
- Webhook yok — entegratörler event'leri yalnız polling ile öğrenebilir.
- **`docs/BUGS_MASTER.md` güncel değil**: "Zero open bugs" iddiası yanıltıcı — en az 2 madde (SEC-008 FK ondelete, job_manager TODO cleanup) kodda zaten fixlenmiş ama dokümanda hâlâ açık/backlog görünüyor; bu durum gelecekteki denetimlerin gerçekten açık olan `MODEL-002`/`MODEL-004` (eksik `updated_at`/`created_at` kolonları), `ARCH-002` (iki paralel sefer-import yolu) ve `MINOR-010` (SSE semaphore TOCTOU) maddelerini "zaten biliniyor, atla" diyerek atlamasına yol açabilir — bu denetimde bağımsız doğrulanmadı, ayrıca incelenmeli.

---

## P3 — Backlog / temizlik

- `app/core/services/`'te 150-260 satırlık aşırı büyük fonksiyonlar (`bulk_add_sefer`, `execute_import`, `_update_sefer_uow` vb.) — validasyon+tahmin+persist tek fonksiyon gövdesinde, test edilebilirlik düşük.
- `frontend/app/` tamamen boş, kalıntı dizin (alt klasörü `models/` de boş) — repo temizliğinde silinmeli.
- `app/domain/services/route_analyzer.py` gerçek ve kullanılan kod (dead code değil) ama CLAUDE.md mimari katman tablosunda hiç tanımlanmamış — dokümantasyon eksikliği, ileride yanlış katmana taşınma riski.
- White-label/branding altyapısı yok (tek marka hardcoded) — ürün kararına bağlı.
- Staging ortamı gerçek altyapı izolasyonuna sahip değil (aynı compose + env override).
- Feature flag'ler env-var+restart seviyesinde, kademeli rollout/kill-switch yok.
- CLAUDE.md'nin i18n bölümü güncel değil — kod zaten `i18next` ile EN/TR desteğine geçmiş.

---

## Tamlık Doğrulama Notları (ek tur sonucu)

Aşağıdaki alanlar ayrıca özel olarak kontrol edildi ve **gerçek bulgu çıkmadığı için kapsam dışı bırakıldı** (yanlış-pozitif riskini azaltmak için burada şeffaflıkla belirtiliyor):
- `tests/` (kök) vs `app/tests/` ayrımı — kasıtlı, ikisi de CI'da koşuyor, orphan değil.
- `app/scripts/`, `scripts/` — destructive script'ler zaten `--confirm` flag'i istiyor.
- `loadtest/` — gerçek Locust kurulumu, p95/hata-oranı eşikli, placeholder değil.
- `cache_manager.py` SecretStr handling — geçmiş regresyon (AUDIT-150) zaten düzeltilmiş, analog bug bulunamadı.
- `admin_roles.py` `yetkiler` mass-assignment — `_assert_no_privilege_escalation` zaten wildcard enjeksiyonunu engelliyor, önceki turun "doğrulanmamış" şüphesi kapatıldı.
- Frontend build artifacts (sourcemap/console.log/dev-flag sızıntısı) — temiz, bulgu yok.

---

## Olumlu Bulgular (dürüstlük adına)

- Migration zinciri temiz: tek head, gerçek `downgrade()` implementasyonları, dokümante gerekçeli destructive migration'lar.
- Money/fuel kolonları doğru tipte (`Numeric`, Float değil); timezone-aware DateTime tutarlı.
- N+1 önleme zaten bilinçli uygulanmış (`sefer_repo.get_all` eager loading, `get_all_with_stats_paged` tek JOIN).
- Raw SQL genelinde parametre bağlama disiplinli; gerçek SQL injection yüzeyi bulunamadı.
- Thread-safety (ensemble model lock), physics_fuel_predictor guard'ları, RAG dimension-mismatch koruması sağlam.
- `openapi.json` CI'da `git diff --exit-code` ile taze tutuluyor, codegen drift riski büyük ölçüde kapatılmış (rate-limit 429 istisnası hariç).
- Frontend test mock disiplini iyi (dış servisleri mock'luyor, komponent iç mantığını değil); zero-mock epic'in FakeUnitOfWork anti-pattern'i artık görünmüyor.
- CI/CD beklenenden olgun: gerçek CD (Trivy CVE tarama, Gitleaks, SSH deploy+smoke test).
- Admin rol/yetki endpoint'i privilege-escalation'a karşı zaten korumalı (`_assert_no_privilege_escalation`).
- WebSocket auth handshake'i sağlam (sadece bağlantı-sayısı limiti eksik).

---

## Önerilen Yol Haritası

1. ~~**P0'ları bu hafta kapat**~~ — ✅ soft-delete kök nedeni (#1, #1b), `yas_faktoru` (#2), round-trip sessiz hata (#6) düzeltildi. Kalan P0'lar (#3 servis katmanı, #4 Celery backfill, #5 OCR timeout, #7 IDOR test skip, #8 dashboard durum çevirisi, #9 object storage) hâlâ açık.
2. **Repository/servis sınır ihlallerini** (`investigations.py`/`locations.py` servis katmanı eksikliği, `core/services` repository bypass) ayrı bir refactor epiği olarak ele alın — büyük yüzey, aceleye getirilmemeli.
3. ~~**Excel formula injection'ı** (export tarafı) acilen kapatın~~ — ✅ export + import tarafı düzeltildi (ayrıca `export_service.py`'de ikinci bir örneği de kapatıldı).
4. **Test suite etiketleme** (integration marker düzeltmesi + skip-as-pass testlerin gerçek assertion'a çevrilmesi) — ucuz, CI'ın gerçekten ne test ettiğine güveni geri kazandırır.
5. **`docs/BUGS_MASTER.md`'yi güncelleyin** — stale "zero open bugs" iddiası gelecekteki denetimleri yanıltabilir; gerçekten açık kalan MODEL-002/004, ARCH-002, MINOR-010 maddelerini bu raporla çapraz doğrulayın.
6. **P1 güvenlik/observability/compliance maddeleri** paralel, görece ucuz iş paketleri.
7. **P2/P3 refactor backlog'u** sprint aralarına dağıtılabilir; plaka validasyon birleştirme ve inspection-alerts/fleet-stats ortaklaştırma en yüksek ROI'li olanlar.
