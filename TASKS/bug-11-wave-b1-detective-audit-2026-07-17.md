# BUG/DEBT TAKİP — İlk 11 dalganın B.1 dedektif denetimi (2026-07-17)

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
borcu).

**DURUM: TÜM BULGULAR (madde 0-4) ÇÖZÜLDÜ (2026-07-17).** Kullanıcı kararı
("dalga 11 den sonrası için yapılacak olanları ayır... ama öncesine ait
işleri en küçük bir hata ve eksik bırakma") üzerine dosya BÖLÜM A (dalga
1-11'e ait borç) / BÖLÜM B (gerçekten dalga-11-sonrası) olarak ayrıldı.
BÖLÜM A'nın TAMAMI bu oturumda kapatıldı — madde 2 (`public.py` sınır
ihlali) de dahil, çünkü kullanıcı düzeltmesiyle o 3 modülün (driver/fuel/
location) hepsinin dalga-11-öncesi tamamlanmış modüller olduğu netleşti.
BÖLÜM B boş çıktı (aşağıya bkz.).

---

## 0. ✅ ÇÖZÜLDÜ (2026-07-16/17) — `ocr.process_belge` Celery task'ı worker'a kayıtlı değildi

**Modül:** `import_excel`. **Bulan ajan:** import_excel denetimi.

`v2/modules/import_excel/infrastructure/tasks.py`'deki `process_belge_ocr`
(`@celery_app.task(name="ocr.process_belge")`) `app/infrastructure/
background/celery_app.py`'nin explicit import listesinde YOKTU — dalga
9'un (`bffa2d4`) atladığı bir kayıt. Celery'de `autodiscover_tasks`
kullanılmıyor; eksik olduğunda Telegram sürücü-bot belge-yükleme akışı
worker'da `NotRegistered` ile sessizce patlıyordu.

**Düzeltme:** `celery_app.py`'ye import eklendi + regresyon testi
(`test_ocr_tasks_coverage.py::test_task_registered_with_worker_via_celery_app_import_list`).
Commit `49b7532`, CI Hard Gates tam yeşil (`gh run 29555563172`).

---

# BÖLÜM A — dalga 1-11'e ait borç (TAMAMI ÇÖZÜLDÜ, 2026-07-17)

## 1. ✅ ÇÖZÜLDÜ — Mimari katman ihlalleri: `domain/` içinde gerçek I/O (3 modül)

- **location** — `LokasyonHydrator` `domain/hydration.py` → `application/
  hydration.py`'a taşındı (davranış aynı, yalnız import path). Tüm
  tüketiciler güncellendi: `public.py`, `application/hydrate_location.py`,
  `api/location_routes.py`, `app/tests/api/test_locations_more2.py`,
  `app/tests/unit/test_lokasyon_hydrator.py`.
- **notification** — `is_user_quiet_now`/`is_within_quiet_hours`
  `domain/quiet_hours.py` → `application/quiet_hours.py`'a taşındı.
  Tüketiciler güncellendi: `public.py`, `application/send_push_to_user.py`,
  `app/tests/unit/test_quiet_hours.py` (patch hedefi dahil).
- **fleet** — `MaintenancePredictor` `domain/maintenance_prediction.py` →
  `application/maintenance_prediction.py`'a taşındı. Yeni ince use-case
  sarmalayıcı eklendi (`application/get_maintenance_predictions.py`:
  `get_all_maintenance_predictions`/`get_maintenance_prediction_for_vehicle`)
  — `api/admin_maintenance_routes.py`'nin `/predictions` +
  `/predictions/{arac_id}` endpoint'leri artık bunlar üzerinden gidiyor
  (cache/audit orkestrasyonu route'ta kaldı, diğer route'larla aynı desen).
  Davranış BİREBİR aynı (path/method/response/yetki). Tüketiciler
  güncellendi: `public.py`, `analytics_executive/application/
  project_cashflow.py`, `reports/application/aggregate_today_triage.py`,
  4 test dosyası (`test_maintenance_predictor.py`, `test_triage_aggregator.py`,
  `test_admin_maintenance_coverage.py` — 4 patch hedefi `mod.
  MaintenancePredictor` → `mod.get_all_maintenance_predictions`/
  `get_maintenance_prediction_for_vehicle`, `reports/CLAUDE.md`,
  `analytics_executive/CLAUDE.md`).

**Doğrulama:** gerçek Docker container'da tüm import'lar resolve edildi
(`python -c "import ..."` başarılı), ilgili modüllerin testleri koştu:
905 passed / 3 pre-existing environment-caused fail (ORS/api-stub network
gap, bu 3 dalgayla ilgisiz — bkz. aşağıdaki genel doğrulama notu). ruff +
mypy temiz.

## 2. ✅ ÇÖZÜLDÜ — `public.py` sınır ihlali (3 modül: driver/fuel/location)

**Kullanıcı düzeltmesi (2026-07-17):** "Sınır ihlali için dalga-11-öncesi
taşımaya ait ihlalleri düzelt." driver (dalga 5)/fuel (dalga 4)/location
(dalga 1) üçü de tamamlanmış dalga-11-öncesi modüller — bu madde BÖLÜM
A'da kapatıldı.

- **driver** — 14 prod dosyasının import'ları `public.py` üzerinden
  geçecek şekilde güncellendi: `v2/modules/reports/application/
  generate_driver_report.py`, `v2/modules/reports/api/
  advanced_reports_routes.py` (2 yer), `v2/modules/import_excel/
  application/driver_importer.py`, `v2/modules/fuel/domain/
  consumption_prediction.py`, `app/database/repositories/sefer_repo.py`,
  `app/core/services/internal_service.py` (3 yer), `app/services/
  prediction_service.py`, `app/core/ml/ensemble_service.py` (2 yer),
  `app/core/ai/trip_planner.py` (3 yer), `app/core/ai/
  recommendation_engine.py`, `app/core/ai/rag_sync_service.py`,
  `app/core/ai/context_builder.py` (2 yer). Karşılık gelen ~20 test
  patch hedefi de tüketen-modülden `driver.public`'e güncellendi.
  **Bilinçli olarak DOKUNULMADI:** `app/core/container.py` ve `app/
  database/repositories/__init__.py` — bunlar driver'a özgü değil,
  TÜM migrasyona-uğramış modüller için AYNI şekilde `infrastructure/`'dan
  doğrudan repo-class import eden sistemik DI-wiring/legacy-repo-shim
  dosyaları (fleet/fuel/location/anomaly/auth_rbac/analytics_executive
  hepsi aynı desende) — yalnız driver'ı düzeltmek tutarsız/keyfi olurdu.
  Aynı gerekçeyle `v2/modules/reports/infrastructure/repo_access.py`'nin
  `get_sofor_repo` çağrısı da dokunulmadı (arac_repo/yakit_repo/
  analiz_repo ile aynı repo-bundle deseni, `app/core/ai/
  context_builder.py`'nin `yakit_repo` property'si de aynı sebeple
  dokunulmadı — `arac_repo`/`sefer_repo`/`analiz_repo` ile aynı sınıfta,
  aynı desen).
- **fuel** — gerçek tek cross-module tüketici bulundu ve düzeltildi:
  `v2/modules/import_excel/application/yakit_importer.py`
  (`bulk_add_yakit` + `recalculate_vehicle_periods`, artık `fuel.public`
  üzerinden). 3 test patch hedefi güncellendi.
- **location** — `v2/modules/import_excel/application/route_importer.py`
  (`create_location`/`route_key`/`LokasyonCreate`, artık `location.public`
  üzerinden). 2 test patch hedefi güncellendi. `import_excel/CLAUDE.md`'nin
  "hepsi public.py üzerinden" iddiası artık doğru (madde 3'te zaten
  bayat olarak işaretlenmişti, düzeltme bu maddeyle birlikte yapıldı).

**Not:** `.importlinter`'da bu sınırı REPO GENELİNDE enforce eden bir
kontrat henüz yok (FAZ1'in "import-linter baseline→gate" çatı görevi,
`TASKS/STATUS.md` satır 33, hâlâ 🔲) — ama bu 3 modüldeki BİLİNEN somut
ihlal gate'in varlığını beklemeden düzeltildi (kullanıcı kararı).

**Doğrulama:** tüm import'lar gerçek Docker container'da resolve edildi;
driver/fuel/location/import_excel/reports/analytics_executive/ai-katmanı
testleri: 905 passed (bir round'da 4 fail bulundu — `test_import_service_
coverage.py::TestProcessDriverImportExtra::test_happy_path`'in eski
`driver.application.add_sofor.bulk_add_sofor` patch hedefi + 3 geocode
testi — ilki düzeltildi, geocode'lar pre-existing env gap olduğu
doğrulandı, bkz. aşağı). ruff (E,F,W,I) + mypy temiz (310 dosya).

## 3. ✅ ÇÖZÜLDÜ — CLAUDE.md doc-drift (6 modül + analytics_executive)

- **fleet** — event-publish bölümü "canlı" olarak güncellendi.
- **notification** — password-reset akışının gerçekte `infrastructure/
  email_client`'a doğrudan gittiği (public.py'yi atlayarak) düzeltildi.
- **fuel** — YAKIT_* event'lerin artık (2026-07-16'dan beri) outbox
  üzerinden gerçekten tetiklendiği + iki gerçek subscriber'ın artık
  register edildiği güncellendi.
- **driver** + **import_excel** — "henüz taşınmadı" dediği `app/core/
  services/import_service.py`'nin dalga 9'da silindiği, aynı raw-SQL
  bypass deseninin artık `import_excel/application/execute_import.py`'de
  yaşadığı düzeltildi (her iki CLAUDE.md'de).
- **route_simulation/location/fuel** — "Sınıf istisnaları" başlığı 3
  modülün CLAUDE.md'sine de eklendi (RouteSimulator/LokasyonHydrator/
  OpetFuelProvider+LinearRegressionModel, driver/fleet'teki formatla
  tutarlı).
- **analytics_executive** — `_UnitOfWorkContext`'in de 2. (zararsız)
  sınıf olduğu, "tam 1 istisna" iddiasının yanlış olduğu düzeltildi.

## 4. ✅ ÇÖZÜLDÜ — Ölü kod (5 kalem, kullanıcı "Sil" onayladı — hepsi silindi)

- **route_simulation** — `get_route_repo()` factory silindi (RouteRepository
  sınıfı kaldı, UoW üzerinden kullanılıyor); `application/
  get_base_location.py` dosyası tamamen silindi + kendi testleri.
- **route_simulation** — `RouteAnalyzer._aggregate_results` silindi +
  kendi testleri.
- **location** — `infrastructure/repository.py`'deki `get_with_elevation`/
  `get_route_for_prediction`/`get_mesafe` silindi + kendi testleri.
- **anomaly** — tamamen ölü `AnomalyDetectionService`/
  `get_anomaly_detection_service()` (`application/
  detect_statistical_anomaly.py`, tüm dosya) silindi; `public.py`'den
  re-export kaldırıldı; 4 test dosyasındaki kullanımları temizlendi
  (`test_anomaly_detection_service.py` dosyası tamamen silindi;
  `test_runtime_config.py`/`test_core.py`/`tests/test_edge_cases_audit.py`
  ilgili test'leri kaldırdı, AnomalyDetector-tabanlı kanıt korundu). Bu
  silme aynı zamanda isim-çakışan `AnomalyResult`/`AnomalyType`/
  `SeverityEnum` (Pydantic vs. `detect_anomaly.py`'nin dataclass'ı) riskini
  de ortadan kaldırdı.
- **import_excel** — `domain/field_validators.py::validate_location()`
  no-op silindi + kendi testi.

**Doğrulama:** her silme öncesi `grep -r` ile gerçek prod çağıranı
olmadığı TEKRAR doğrulandı. Silme sonrası ilgili modüllerin testleri
gerçek Docker container'da koştu, regresyon yok.

---

# BÖLÜM B — gerçekten dalga-11-sonrası (henüz taşınmamış modüllere ait)

Bu denetim yalnız ilk 11 dalgayı kapsadı — dalga 12+ (ai-assistant,
prediction-ml, trip, admin-platform, shared-kernel, platform-infra) henüz
denetlenmedi/taşınmadı. Bu bölüm **boştur**: denetimde bulunan TÜM
ihlaller (madde 1, 2, 3, 4) dalga-11-öncesi tamamlanmış modüllere aitti.
O dalgalar kendi taşıma planlarında işlenirken benzer B.1/public.py
denetimi o modülün kendi taşıma PR'ının parçası olarak yapılacak.

---

## Genel doğrulama özeti (2026-07-17, oturum sonu)

- **Değiştirilen dosya sayısı:** ~75 (kod + test + CLAUDE.md), 5 dosya
  silindi, 1 yeni dosya eklendi (`fleet/application/
  get_maintenance_predictions.py`), 3 dosya taşındı (`git mv`).
- **Test sonucu (kümülatif, birden fazla hedefli koşum):** 905+ passed,
  0 gerçek fail. Koşum sırasında bulunan TEK gerçek regresyon
  (`test_import_service_coverage.py`'nin eski patch hedefi) düzeltildi.
- **Pre-existing, bu oturumla ilgisiz 3 environment-gap fail** (aynı ad-hoc
  Docker container'ın `api-stub`'a yönlendirilmemiş olması, gerçek ORS API
  bağlantısı arıyor, gerçek internet'e (nominatim.openstreetmap.org)
  düşüyor): `test_lokasyon_service_coverage.py::TestGeocodeViaOpenroute`
  (2 test) + `test_locations_coverage.py::test_geocode_success` — CI'nın
  temiz ortamında (api-stub doğru wire edilmiş) görülmeyecek, dalga 11'in
  kendi CI doğrulamasında da aynı sınıf (route_service ORS testleri) tespit
  edilmişti.
- **ruff (E,F,W,I):** temiz (1 isort-sıralama hatası bulundu, `--fix` ile
  düzeltildi: `notification/public.py`).
- **mypy (`--ignore-missing-imports --no-strict-optional`):** temiz, 310
  dosya.
- **Commit/push:** YAPILMADI — bu dosya + kod değişiklikleri incelenmeyi
  bekliyor, kullanıcı onayı sonrası commit edilecek.

## Bağımsız ikinci doğrulama (koordinatör tarafından, fork'un raporundan sonra)

Fork'un raporu koordinatör (ben) tarafından tekrar, bağımsız olarak
gerçek Docker container'da doğrulandı (fork'un kendi iddiasına güvenmek
yerine):

- **Gerçek regresyon bulundu ve düzeltildi (fork'un kaçırdığı):** 3 dosyada
  isort/import-satırı-uzunluğu ihlali — `v2/modules/location/public.py`
  (hydration import'u yanlış sıradaydı), `app/tests/unit/
  test_maintenance_predictor.py` (2 satır 88 karakteri aşıyordu, `domain`→
  `application` yeniden adlandırmasıyla), `app/core/ai/trip_planner.py`
  (aynı sınıf). Tümü parantezli çok-satır import'a çevrildi, davranış
  değişmedi. Ayrıca `v2/modules/fleet/public.py`,
  `v2/modules/fleet/api/admin_maintenance_routes.py`,
  `v2/modules/location/api/location_routes.py`'de (CI kapsamı dışında,
  yalnız `app/` linteniyor, ama kendi kod hijyenimiz için) aynı sınıf 3
  isort-sıralama düzeltmesi yapıldı.
- **`app/api/v1/endpoints/anomalies.py` ve `test_ai_service.py`'de görünen
  ruff hataları YANLIŞ ALARM çıktı** — bu ad-hoc Docker container'da
  önceki bir session'dan kalma stale dosya kopyalarıydı (git'te
  `anomalies.py` hiç yok — `git ls-files` doğruladı; `test_ai_service.py`
  gerçek working-tree kopyasıyla tekrar sync edilince temiz çıktı).
  Container'daki stale `anomalies.py` silindi.
- **`ruff check app/ --select=E,F,W,I` (CI'nın BİREBİR komutu):** temiz.
- **`ruff check v2/ --select=E,F,W,I`** (CI kapsamında değil ama kendi
  hijyenimiz için kontrol edildi): temiz (düzeltmelerden sonra).
- **`mypy app --ignore-missing-imports --no-strict-optional`:** temiz,
  711 dosya.
- **Tam suite** (`pytest -m "unit or not integration"
  --ignore=tests/integration --ignore=app/tests/integration app/tests/unit
  app/tests/api tests`, CI'nın birebir komutu): **5257 passed, 7 failed**
  — 7'si bu ad-hoc container'a özgü, önceden belgelenmiş ortam-kaynaklı
  hatalar (gerçek Redis Sentinel + `USE_SEFER_FUEL_ESTIMATOR=true`
  prod-tarzı env; dalga 11'in kendi doğrulamasında da AYNI 7 test AYNI
  sebeple fail vermişti — CI'nın temiz ortamında görülmez).
- **Silinen ölü kodun repo genelinde sıfır referansı kaldığı doğrulandı**
  (`grep -rn` ile) — 2 alakasız eşleşme bulundu (`app/core/interfaces/
  repositories.py::ILokasyonRepository.get_mesafe` — hiç implemente
  edilmeyen, pre-existing, kullanılmayan bir ABC arayüzü, bu denetimin
  kapsamı dışında; `app/schemas/sefer.py::validate_location` — sefer
  şemasında alakasız bir Pydantic validator), ikisi de bu oturumun
  sildiği kodla ilgisiz.

**SONUÇ: BÖLÜM A (madde 0-4, madde 2 dahil) tam doğrulanmış şekilde
kapatıldı. Commit/push için kullanıcı onayı bekleniyor.**
