# BUG/DEBT TAKİP — İlk 11 dalganın B.1 dedektif denetimi (2026-07-17)

> **DURMA NOKTASI:** Herhangi bir madde uygulanmadan önce kullanıcı onayı gerekir.

**Bu bir modül taşıma görevi DEĞİL.** FAZ1'in 17 dalga sırasının dışında,
bağımsız bir bulgu-takip dosyası. Kullanıcı talebiyle ("ilk 11 dalgayı
detaylı ve derin kontrol edelim... dedektif gibi denetlesinler") 11
bağımsız sıfır-context ajan (`location`, `route_simulation`,
`notification`, `fleet`, `fuel`, `driver`, `auth_rbac`, `anomaly`,
`import_excel`, `reports`, `analytics_executive` — her modül için bir
ajan) her modülün TÜM dosyalarını B.1 kuralına ("her dosya/sınıf tek
sorumluluk") karşı satır satır denetledi.

**Sonuç özeti:** `auth_rbac` ve `reports` sıfır bulguyla tam temiz çıktı.
Diğer 9 modülde toplam ~30 bulgu (1 GERÇEK BUG, kalan mimari/dokümantasyon
borcu). **GERÇEK BUG aynı oturumda düzeltildi** (bkz. madde 0). Kalan
bulgular bu dosyada takip ediliyor, kullanıcı onayı olmadan uygulanmayacak.

---

## 0. ✅ ÇÖZÜLDÜ (aynı oturumda) — `ocr.process_belge` Celery task'ı worker'a kayıtlı değildi

**Modül:** `import_excel`. **Bulan ajan:** import_excel denetimi.

`v2/modules/import_excel/infrastructure/tasks.py`'deki `process_belge_ocr`
(`@celery_app.task(name="ocr.process_belge")`) `app/infrastructure/
background/celery_app.py`'nin explicit import listesinde YOKTU — dalga
9'un (`bffa2d4`, import_excel'i v2/modules/'e taşıma) atladığı bir kayıt.
Celery'de `autodiscover_tasks` kullanılmıyor, kayıt tamamen bu explicit
import listesine bağlı; eksik olduğunda `.delay()` çağıran gerçek kod
(`app/api/v1/endpoints/internal.py`'nin Telegram sürücü-bot belge-yükleme
akışı) worker'da `NotRegistered` ile sessizce patlıyordu. Testler bunu
yakalayamamıştı çünkü hepsi task fonksiyonunu doğrudan import ediyordu
(worker'ın gerçek yükleme yolunu hiç kullanmıyordu).

**Düzeltme:** `celery_app.py`'ye `import v2.modules.import_excel.
infrastructure.tasks` eklendi. Yeni regresyon testi eklendi
(`test_ocr_tasks_coverage.py::test_task_registered_with_worker_via_celery_app_import_list`
— gerçek `celery_app.tasks` registry'sini kontrol ediyor, TDD red→green
doğrulandı gerçek Docker container'da). `pytest app/tests/unit/test_workers
app/tests/unit/test_infrastructure/test_celery_app_config.py` → 101 passed.

---

## 1. Mimari katman ihlalleri — `domain/` içinde gerçek I/O (3 modül)

Üç modülde aynı desen: "domain/ = saf mantık, I/O yok" kuralına rağmen
gerçek DB/network çağrısı domain/ dosyasında yaşıyor, hiçbiri modülün
kendi CLAUDE.md'sinde "Sınıf istisnaları" olarak dokümante edilmemiş.

- **location** — `domain/hydration.py::LokasyonHydrator.hydrate()`
  gerçek Mapbox+Open-Meteo network çağrısı yapıyor VE ORM state
  mutasyonu yapıyor (satır 89, 115, 121-161). `route_simulation`'ın
  eşdeğeri (`RouteSimulator`) doğru şekilde `application/`'da yaşıyor —
  tutarsızlık. Öneri: `LokasyonHydrator`'ı `application/`'a taşı (sınıf
  istisnasının kendisi meşru — constructor-injected client'lar — sadece
  klasör yanlış).
- **notification** — `domain/quiet_hours.py::is_user_quiet_now()`
  `auth_rbac`'a gerçek DB sorgusu atıyor (`get_preferences` çağrısı,
  kendi `UnitOfWork()` açıyor). `application/send_push_to_user.py`'den
  çağrılıyor — aslında bir application/ use-case'i, domain/'de kalmış.
- **fleet** — `domain/maintenance_prediction.py::MaintenancePredictor`
  `predict_all`/`predict_for_arac`/`_gather_inputs` içinde `UnitOfWork()`
  açıp ham SQL çalıştırıyor. Ayrıca `api/admin_maintenance_routes.py`
  bunu `application/` katmanını hiç atlamadan DOĞRUDAN import edip
  çağırıyor — modülün kendi 31 route'unun geri kalanı hep `application/`
  üzerinden gidiyor, bu 3 endpoint istisna.

**Önerilen aksiyon (kullanıcı onayı gerekir):** Üçü de "taşı" (davranış
değişmez, sadece dosya konumu) — küçük, düşük riskli refactor'lar. Fleet'in
`admin_maintenance_routes.py`'si için ayrıca ince bir `application/`
use-case sarmalayıcısı gerekir (diğer 28 route'la tutarlı olması için).

## 2. `public.py` sınır ihlali — sistemik desen (3 modül)

- **driver** — 14 prod dosyası `public.py`'yi atlayıp `application/`/
  `domain/`/`infrastructure/`'a doğrudan giriyor (liste ajan raporunda).
  `public.py`'nin kendi docstring'i "import-linter ile enforce ediliyor"
  diyor ama `.importlinter`'da `v2.modules.driver` için hiçbir kontrat yok
  — iddia yanlış.
- **fuel** — `public.py`'nin "buradan import edilmeli" iddiasına rağmen
  **sıfır** gerçek tüketici onu kullanıyor; hepsi doğrudan
  `infrastructure.repository`/`application.*`'a giriyor.
- **location** — `import_excel/application/route_importer.py`
  `location/public.py`'yi atlıyor, ama `import_excel`'in kendi CLAUDE.md'si
  "hepsi public.py üzerinden" diyor (yanlış iddia).

**Not:** `.importlinter` repo genelinde yalnız `app.core.services` vs
`app.services` arasında TEK bir kontrat içeriyor — hiçbir `v2.modules.*`
sınırı bugün gerçekten enforce edilmiyor (FAZ1'in "import-linter
baseline→gate" çatı görevi henüz yapılmadı, `TASKS/STATUS.md` satır 33'te
zaten 🔲 işaretli). Bu üç bulgu o çatı görevinin neden gerekli olduğunun
somut kanıtı — ayrı bir refactor değil, muhtemelen o çatı göreviyle
birlikte ele alınmalı.

## 3. CLAUDE.md doc-drift — yanlış/bayat bilgi (6 modül)

- **fleet** — event-publish bölümü hâlâ "ölü kod" diyor; `events.py` ve
  gerçek kod artık olayların CANLI olduğunu gösteriyor (aynı modül
  içinde iki dosya birbirini yalanlıyor).
- **notification** — password-reset akışının `public.py` üzerinden
  gittiği iddiası yanlış; gerçekte `infrastructure/email_client`'a
  doğrudan gidiyor (auth_rbac'ın kendi CLAUDE.md'si doğru anlatıyor).
- **fuel** — YAKIT_* event'lerin "asla tetiklenmiyor" iddiası artık bayat
  (2026-07-16'da düzeltilmiş, `events.py`'nin kendi changelog'u bunu
  doğru anlatıyor — yalnız CLAUDE.md güncellenmemiş).
- **driver** — "henüz taşınmadı" dediği `app/core/services/
  import_service.py` artık hiç yok (dalga 9'da silindi); aynı bypass
  deseni artık `import_excel/application/execute_import.py`'de yaşıyor.
- **import_excel** → **driver** — `driver/CLAUDE.md`'nin aynı bayat
  referansı (yukarıdaki madde ile aynı kök neden, iki modülün
  CLAUDE.md'si de düzeltilmeli).
- **route_simulation/location/fuel** — "Sınıf istisnaları" başlığı ya
  hiç yok ya da tutarsız formatta; gerçek istisnalar (`RouteSimulator`,
  `LokasyonHydrator`, `OpetFuelProvider`) satır-içi yorumla gerekçelendirilmiş
  ama modülün kendi CLAUDE.md'sinde ayrı bir başlık altında değil.

## 4. Ölü kod — dokümante edilmemiş, düşük risk (5 modül)

- **route_simulation** — `infrastructure/repository.py::get_route_repo()`
  factory + `application/get_base_location.py::get_base_location()`
  sıfır gerçek çağıran (yalnız testler).
- **route_simulation** — `domain/route_analyzer.py::RouteAnalyzer.
  _aggregate_results` — `analyze_segments` onu hiç çağırmıyor (inline
  hesaplıyor), yalnız kendi testi çağırıyor.
- **location** — `infrastructure/repository.py`'de 3 metod
  (`get_with_elevation`, `get_route_for_prediction`, `get_mesafe`) sıfır
  prod çağıran.
- **anomaly** — `application/detect_anomaly.py`'deki (dataclass)
  `AnomalyResult`/`AnomalyType`/`SeverityEnum` ile `app/core/entities/
  models.py`'deki (Pydantic) AYNI İSİMLİ ama FARKLI tipler var — ikincisini
  kullanan `AnomalyDetectionService` zaten tamamen ölü kod (dalga 11'de
  `AnalizService` silinince tek tüketicisi gitti), o yüzden şu an çakışma
  riski yok, ama biri diriltilirse `isinstance` uyumsuzluğu sürpriz olur.
- **analytics_executive** — `application/generate_insights.py::
  _UnitOfWorkContext` dokümante edilmemiş 2. sınıf (CLAUDE.md "tam 1
  istisna" diyor) — iş mantığı taşımıyor, zararsız ama sayım yanlış.
- **import_excel** — `domain/field_validators.py::validate_location()`
  no-op passthrough, sıfır prod çağıran.

---

## Önerilen sıradaki adım

Bu bulguların hiçbiri acil değil (madde 0 hariç, o zaten düzeltildi).
Kullanıcı onayıyla ele alınabilecek sıralama önerisi:
1. Madde 3 (CLAUDE.md doc-drift) — en düşük riskli, yalnız dokümantasyon,
   herhangi bir oturumda hızlıca yapılabilir.
2. Madde 4 (ölü kod) — silme veya "bilinçli tutuldu" olarak dokümante
   etme kararı kullanıcıdan gerekir (dalga 11'deki AnalizService/
   DashboardService kararına benzer).
3. Madde 1 (domain/ I/O ihlalleri) — küçük ama gerçek refactor'lar,
   üçü de aynı oturumda ele alınabilir.
4. Madde 2 (public.py sistemik ihlali) — FAZ1'in "import-linter
   baseline→gate" çatı göreviyle birlikte ele alınması muhtemelen daha
   verimli (17 dalganın hepsinde aynı desen olabilir, tek tek modül
   modül düzeltmek yerine gate aktifleştiğinde hepsi birden görünür olur).
