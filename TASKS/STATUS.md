# STATUS — Modüler Monolit Refaktörü İlerleme Takibi

> **Bu dosya tek gerçek kaynağıdır.** Yeni bir oturumda "kaldığın yerden devam et" dendiğinde, önce bu dosya okunur — plan tamamının yeniden okunmasına gerek yoktur.

## ⚠️ OTURUM HİJYENİ — HER BİRİMDEN SONRA YENİ OTURUM BAŞLAT

**Bu plan tek oturumda bitmez, bitirilmeye ÇALIŞILMAMALI.** Kural:

1. **Bir oturum = en fazla 1 modül (veya 1 FAZ çatı görevi).** Bir modül PR'ı merge olunca, o oturumu KAPAT (yeni pencere / `/clear` / yeni konuşma).
2. **Yeni oturumda ilk mesaj:** *"TASKS/STATUS.md'ye göre kaldığın yerden devam et."* — yeterlidir. Context şişmeden, önceki oturumun ayrıntılarını yeniden anlatmaya gerek kalmadan devam edilir.
3. **Neden:** Uzun süren tek bir oturum (a) context'i şişirip yanıt kalitesini düşürür, (b) bir hata olduğunda geri almayı zorlaştırır, (c) sizin (kullanıcı) takip edebileceğiniz boyuttan çıkar — tam da şikâyet ettiğiniz sorun. Modül-başına oturum, her PR'ı bağımsız gözden geçirilebilir/geri alınabilir tutar.
4. **Onay yükünü azaltmak isterseniz:** tek tek her modülü onaylamak yerine "sıradaki 3 modülü sırayla uygula, her birinden sonra kısa özet ver" gibi toplu talimat da verilebilir — ama yine de her modül ayrı commit/PR olarak kalır (DURMA NOKTASI ilkesi bozulmaz, yalnız onay istemi gruplanır).

---

## FAZ İlerlemesi

| FAZ | Durum | Not |
|---|---|---|
| **FAZ0** — Baseline & rapor modu | ✅ TAMAMLANDI (2026-07-12) | main yeşil, import-linter rapor adımı CI'da; commit `3840de3`,`72a5fe3`,`3e905a8` |
| **FAZ1** — Kod sınırları (17 kalem) | 🟡 DEVAM EDİYOR — 2/17 kalem tamam | Dalga 1 (location+route-simulation) main'de yeşil; dalga 2 (notification) kod tamam+lokal doğrulandı, main'e push bekliyor; sıradaki: dalga 3 (fleet) |
| **FAZ2** — Veri sınırları | 🔲 FAZ1'i bekliyor | |
| **FAZ3** — Dil geçişi | 🔲 FAZ2'yi bekliyor | Bağımsız FAZ, sınır-enforcement ile aynı PR'da olmaz |
| **FAZ4** — Sıkılaştırma & kapanış | 🔲 FAZ3'ü bekliyor | |

## FAZ1 — Modül Dalga Sırası (bağımlılık az→çok)

Her satır bağımsız bir PR/onay/oturum birimidir. Sıradaki modül, bir öncekinin PR'ı merge olmadan başlamaz (görev dosyasının "Giriş kriteri"nde yazılı).

| # | Modül/kalem | Görev dosyası | Durum |
|---|---|---|---|
| — | Registry+iskelet+shim deseni (çatı) | `faz1-registry-iskelet-ve-shim.md` | 🔲 |
| — | import-linter baseline→gate (çatı) | `faz1-import-linter-baseline-ve-gate.md` | 🔲 |
| — | Davranışsal mimari testleri (çatı) | `faz1-davranissal-mimari-testler.md` | 🔲 |
| — | Dosya kalite + kısalık gate (çatı) | `faz1-dosya-kalite-ve-kisalik-gate.md` | 🔲 |
| — | Modül CLAUDE.md şablonu (çatı) | `faz1-claude-md-per-module-template.md` | 🔲 |
| 1 | **location + route-simulation** (PİLOT ÇİFTİ — karşılıklı bağımlı 7/1 kenar, birlikte) | `modules/location.md` + `modules/route-simulation.md` | ✅ main'de yeşil (commit `4ebabca`) |
| 2 | notification | `modules/notification.md` | ✅ kod tamam, lokal doğrulama yeşil — main'e henüz push edilmedi |
| 3 | fleet | `modules/fleet.md` | 🔲 |
| 4 | fuel | `modules/fuel.md` | 🔲 |
| 5 | driver | `modules/driver.md` | 🔲 |
| 6 | auth-rbac | `modules/auth-rbac.md` | 🔲 |
| 7 | *(route-simulation dalga 1'e taşındı, bkz. üstte)* | — | — |
| 8 | anomaly | `modules/anomaly.md` | 🔲 |
| 9 | import-excel | `modules/import-excel.md` | 🔲 |
| 10 | reports | `modules/reports.md` | 🔲 |
| 11 | analytics-executive | `modules/analytics-executive.md` | 🔲 |
| 12 | ai-assistant | `modules/ai-assistant.md` | 🔲 |
| 13 | prediction-ml | `modules/prediction-ml.md` | 🔲 |
| 14 | trip (en karmaşık split) | `modules/trip.md` | 🔲 |
| 15 | admin-platform | `modules/admin-platform.md` | 🔲 |
| 16 | shared-kernel (erime) | `modules/shared-kernel.md` | 🔲 |
| 17 | platform-infra (registry finali) | `modules/platform-infra.md` | 🔲 |

**FAZ1 çıkış kriteri:** yukarıdaki 17 kalemin tamamı + import-linter gate main'de 5 ardışık gün yeşil (bkz. `TASKS/README.md`).

## KARAR (2026-07-12) — Hedef klasör v2/'ye değişti
Kullanıcı talebiyle: yeni modül kodu artık `app/modules/<x>/` DEĞİL, **repo kökünde `v2/modules/<x>/`** altında yazılıyor (tek FastAPI process, aynı `app/main.py`'nin import edeceği ayrı bir üst-paket — iki ayrı uygulama değil). Gerekçe: (1) eski dosyalarla iç içe geçmiş shim'ler yerine temiz bir ağaç, (2) "ileri mühendislik" — B.1'in "bir dosya = bir use-case" kuralı bu kez GEVŞETİLMEDEN uygulanıyor (location pilotunda `LokasyonService`'in tek sınıf olarak bırakılması bir istisnaydı; v2'de bu istisna YOK, use-case'ler gerçekten ayrı dosyalara bölünüyor).

**Döngü stratejisi:** Ölçülen 24 karşılıklı-bağımlı modül çiftinden dolayı ("v2 asla eski app/ dosyasına bakmasın" + "bir oturum = bir modül" birlikte imkânsız) — karar: v2 modülleri eski `app/` dosyalarına GEÇİCİ OLARAK import atabilir (okumak/bağımlı olmak sorun değil, kullanıcının netleştirmesi: "eski dosya istemiyorum" = kod O DOSYADA YAŞAMASIN demekti, ona bağımlı olunamaz değil). Sıkı-bağlı çiftler (location↔route_simulation gibi) MÜMKÜN OLDUĞUNCA birlikte taşınır (dalga 1 artık ikisini birden kapsıyor); bu her zaman mümkün olmayabilir (24 çift var, hepsini gruplamak pratik değil) — kalan çiftlerde geçici eski-yol importu kalır, o modül taşınınca güncellenir (location pilotundaki gibi, dokümante edilerek).

**Eski `app/modules/location/` işi (commit d991b6c) geri alındı** (push edilmemişti) — v2/modules/location olarak, use-case'lere düzgün bölünerek yeniden yapılıyor.

**SON-DURUM KARARI (kullanıcı, 2026-07-12):** "İşin sonunda v2 kalacak, v2 dışında bizi bağlayan hiçbir şey olmamalı." Yani: geçiş SIRASINDA v2 modülleri geçici olarak eski `app/` dosyalarına bağımlı olabilir (24 döngüsel bağımlılık için kaçınılmaz — kullanıcı bunu onayladı: "eski koda bakma/bağımlı olma demedim"), AMA tüm 15 modül + shared_kernel + platform-infra (main.py/config.py/database bağlantısı dahil) v2'ye taşındıktan SONRA `app/` dizini TAMAMEN SİLİNİR. Bu, mevcut FAZ4 (sıkılaştırma) görevinin genişletilmiş hedefidir — eski FAZ4 yalnız "shim'leri sil" diyordu, yeni hedef "app/ dizinini komple sil, v2/ tek kalan kod tabanı olsun" (muhtemelen v2/ o noktada repo kökünde kalır veya app/ adını devralır — bu detay FAZ4'te netleşecek, şimdiden karara bağlanmadı).

## Bilinen açık notlar (ileride çözülecek, kapsam dışı bırakılmadı)
- `admin_ws.py` dosya-sahipliği vs route-işlev tutarsızlığı — notification (dalga 2) VE admin-platform (dalga 15) dosyalarında işaretli, dalga 2'de karar verilecek.
- `model_manager.py`'deki 9 kırık raw-SQL sitesi (`model_versions` tablosu yok) — prediction-ml (dalga 13) dalgasında düzeltilecek/temizlenecek, ayrı bug-fix.

## DALGA 1 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-13)

**Son durum (özet):** location + route_simulation (kod-tarafı) main'de, CI Hard Gates tam yeşil (E2E dahil). 3 commit halinde push edildi:
1. `7339088` → `f17d8a3` arası (4 commit, ilk 3'ü push-sonrası kırmızı çıkıp düzeltildi) — location TAM + route_simulation kod/API TAM. Son hâli commit `f17d8a3`, CI run tam yeşil (~60dk).
2. `4ebabca` — B.1 uyum düzeltmesi: `RouteService` sınıfı use-case'lere bölündü (aşağıda detay). CI run tam yeşil (~51dk; ara-sırada 1 alakasız flaky frontend testi çıktı, rerun ile geçti).

**Sıradaki adım:** dalga 2 (notification modülü) — `TASKS/modules/notification.md` dosyasını oku, kullanıcı onayı olmadan BAŞLAMA (DURMA NOKTASI kuralı).

**Ara-not (2026-07-13):** dalga 1'in son (docs-only) commit'i `2698199` push-sonrası CI'da kırmızı çıktı (`trip-service.contract.test.ts` — kendi oluşturduğu şoförle sefer açarken "bulunamadı/pasif" hatası, entity_id uyuşmazlığı). Kod değişikliği içermeyen bir commit olduğu için regresyon şüphesi düşüktü; rerun (`gh run rerun --failed`) ile doğrulandı: **flaky/transient** — ikinci koşumda `success` (run `29225784882`, tamamlanma `2026-07-13T06:31:12Z`). Kök neden araştırılmadı (kapsam dışı bırakıldı, gerekirse ayrı bir flake-avcılığı görevi açılabilir). main şu an yeşil.

### Detaylar (arşiv amaçlı, ilk uygulama süreci)

**✅ location modülü — TAM** (kod + CLAUDE.md + test suite yeniden yazıldı):
- 15 dosya: `application/{create,update,delete,list,analyze,geocode}_location.py` (her biri tek fonksiyon, `LokasyonService` sınıfı YOK), `domain/{route_key,hydration}.py`, `infrastructure/{repository,geocode_providers}.py`, `schemas.py`, `events.py`, `public.py`, `api/location_routes.py`, `CLAUDE.md`.
- Eski 5 location dosyası (`app/api/v1/endpoints/locations.py`, `app/core/services/lokasyon_service.py`, `app/core/services/lokasyon_hydrator.py`, `app/database/repositories/lokasyon_repo.py`, `app/schemas/lokasyon.py`) **TAMAMEN SİLİNDİ** (shim bile yok).
- Tüm çapraz-modül tüketiciler v2'ye güncellendi: `app/api/deps.py`, `app/core/container.py`, `app/api/v1/api.py`, `app/database/repositories/__init__.py`, `app/core/services/import_service.py`, `app/api/v1/endpoints/weather.py`, `scripts/p51_real_world_validation.py`.
- **11 test dosyası** güncellendi/yeniden yazıldı (class-mock → free-function-mock deseni): `test_lokasyon_service.py`, `test_lokasyon_service_coverage.py`, `test_lokasyon_service_more.py`, `test_lokasyon_hydrator.py`, `test_lokasyon_schemas.py`, `test_lokasyon_repo_coverage.py`, `test_locations_coverage.py`, `test_locations_more.py`, `test_locations_more2.py`, `test_locations_api.py`, `test_import_service*.py`, `test_deps_coverage.py`, `test_weather_coverage.py`.

**✅ route_simulation modülü — kod TAM, orkestrasyon+API dahil** (kalan: weather/calibration/validator alt-parçaları eski yolda):
- `infrastructure/{mapbox_client,open_meteo_client,openroute_client,repository}.py`, `domain/{polyline,route_analyzer,segment_simulator,segment_resampler}.py`, `application/{get_route_details,simulate_route}.py` (RouteService/RouteSimulator — cohesive orkestratör sınıfları, `LokasyonHydrator` ile aynı gerekçe), `api/route_routes.py`, `CLAUDE.md`.
- Eski 11 dosya **TAMAMEN SİLİNDİ**: `app/services/route_service.py`, `app/database/repositories/route_repo.py`, `app/core/services/route_simulator.py`, `app/infrastructure/routing/{__init__,mapbox_client,openroute_client}.py` (paket komple), `app/infrastructure/elevation/{__init__,open_meteo_client}.py` (paket komple), `app/core/utils/polyline.py`, `app/domain/services/route_analyzer.py`, `app/core/ml/segment_simulator.py`, `app/core/services/segment_resampler.py`, `app/api/v1/endpoints/routes.py`.
- Tüm tüketiciler güncellendi: `container.py`, `import_service.py`, `sefer_fuel_estimator.py` (P4-5 canlı tahmin pipeline'ı!), `api.py`, location modülünün 2 dosyası, 3 script (`enrich_existing_data.py`, `calibrate_physics.py`, `validate_tractive_offline.py`).
- **~25 test dosyası** güncellendi (import path + patch-target düzeltmesi, çoğu mekanik).

**🔲 route_simulation'da KALAN (route_simulation'ın kendi ileriki dilimi, kapsam dışı bırakılmadı):**
- `weather_service.py`, `route_validator.py`, `openroute_service.py` (geocode wrapper), `route_calibration_service.py`, `app/api/v1/endpoints/{weather,admin_calibration}.py`, `app/core/ml/route_similarity.py` — hâlâ eski `app/` yolunda, v2'nin geçici (dokümante) bağımlılığı.
- `public.py`/`events.py`/`schemas.py` henüz yok — location modülü şu an `application/`'dan doğrudan import ediyor (mimari borç, `route_simulation/CLAUDE.md`'de dokümante).
- `scripts/backfill_route_pairs.py` henüz kontrol edilmedi.

**✅ Kritik bulgu + fix (detective review sırasında):** `app/tests/conftest.py` iki kez (`lokasyon_repo` VE `route_repo` singleton reset satırları) silinen eski modülleri import ediyordu — bu, conftest yüklenemediği için **TÜM 541 test dosyasının** collect edilememesi anlamına geliyordu (yalnız location/route_simulation değil). Düzeltildi + doğrulandı: `docker compose exec backend python -m pytest app/tests --collect-only` → 6765+ test, 0 hata.

**Doğrulama (gerçek Docker container, gerçek pytest koşumu):**
- `app.main` + tüm dokunulan script'ler temiz import ediyor (eski dosyalar container'dan da fiziksel silindi, sadece git'ten değil).
- `ruff check app/ v2/ scripts/` → temiz.
- route_simulation ilgili testler: 122 passed, 0 fail (kalan skip/error'lar `TEST_DATABASE_URL`/`api-stub` servisinin bu ad-hoc ortamda çalışmıyor olmasından — göçle ilgisi yok).
- **main'e push edildi ve CI Hard Gates TAM YEŞİL geçti** (E2E dahil, ~60dk) — commit `f17d8a3`. Push sonrası 3 tur kırmızı çıktı (conftest.py'de gözden kaçan bir satır daha, hiç bilinmeyen ayrı bir kök `tests/` klasörü, dosya-yolu okuyan bir truthfulness-guard testi, endpoint-adı değişikliğinin OpenAPI şemasına sızması) — hepsi bulunup düzeltildi, CI'da doğrulandı.

**✅ B.1 uyum düzeltmesi (2026-07-13, commit `4ebabca`):** `RouteService` sınıfı (get_route_details+get_base_location+analyze_route_difficulty+haversine/segment_distance/analyze_elevation_profile bundle ediyordu — STATUS.md'nin "v2'de bir-dosya-bir-use-case istisnası yok" kararına aykırıydı) 4 dosyaya bölündü: `application/get_route_details.py` (free function), `application/get_route_difficulty.py`, `application/get_base_location.py`, `domain/route_geometry.py` (haversine vb. — hiçbir prod kod çağırmıyor, yalnız kendi testleri). `container.py`/`import_service.py`'deki hiçbir prod kodun çağırmadığı `route_service` property'leri dead-code olarak kaldırıldı (+ 2 test güncellemesi). `RouteSimulator` bölünmedi (tek use-case/tek pipeline, `LokasyonHydrator` ile aynı meşru istisna). ~10 test dosyası class-mock'tan free-function-mock'a çevrildi.

**Yerel/container doğrulama (final):** location testleri 35 passed/0 fail; route_simulation testleri 198 passed/9 fail (9'u `localhost:9000` vs `api-stub:9000` docker-network topoloji sorunu — bilinen, göçle ilgisiz); tam suite (`TEST_DATABASE_URL` ile, `lojinext_user`/`lojinext_pass_2026` kimlik bilgileriyle) 5245 passed/13 failed (13'ü main'de zaten var olan, göçle ilgisiz ortam-kaynaklı hatalar — bkz. aşağıdaki "Bilinen ortam-kaynaklı test hataları").

**CI doğrulama (final, gerçek kaynak):** `gh run list --branch main --limit 1` → commit `4ebabca` için `completed success`, 50dk58sn, tüm gate'ler dahil (Backend unit tests, entegrasyon paketleri, Combined coverage gate %92, OpenAPI schema drift check, Frontend build/lint/typecheck, Playwright E2E).

### Bilinen ortam-kaynaklı test hataları (main'de zaten var, bu dalgayla ilgisiz — CI'da görülmez çünkü CI'nin kendi ortamı bunları etkilemiyor)
Yalnız ad-hoc `docker compose exec backend pytest` ile lokal koşumda görülür, CI'da GÖRÜLMEZ (CI kendi temiz ortamını kurar):
- `test_mapbox_client.py`, `test_route_api.py` (x2), `test_route_service_hybrid.py` (x2) — `api-stub` servisi bu ad-hoc ortamda ayrı bir docker-compose profile'ı gerektiriyor (`docker compose --profile test up -d api-stub`).
- `test_phase4_sefer_integration_helpers.py`, `test_sefer_write_service_prediction_flows.py` (x2) — container'ın `.env`'inde `USE_SEFER_FUEL_ESTIMATOR=true` (production-tarzı) ayarlı, testler `False` varsayıyor.
- `test_event_bus_more.py`, `test_health_service_more.py` — container'da gerçek Redis Sentinel çalışıyor, testler "Redis kapalı" senaryosu bekliyor.
- `test_analysis_and_report.py`, `test_admin_backend_operations.py`, `test_job_manager.py` — location/route_simulation'la alakasız, bağımsız pre-existing sorunlar (araştırılmadı, bu dalganın kapsamı dışı).

## DALGA 2 — kod tamam + lokal doğrulama yeşil, main'e push BEKLİYOR (2026-07-13)

**Kapsam:** notification modülü (13 dosya envanterinden 12'si taşındı — `schemas/telegram.py` incelemede trip/telegram-bot'a ait çıktı, taşınmadı; `admin_ws.py` iki bağımsız route'a bölündü, `/live` notification'a taşındı, `/training` admin_platform'da kaldı). Detaylar `TASKS/modules/notification.md` madde 6 (kabul kriterleri) + `v2/modules/notification/CLAUDE.md`.

**Öne çıkan kararlar/bulgular:**
- `admin_ws.py` görev dosyasının öngördüğü (a)/(b) ikilisi yanlış varsayımdı — dosya gerçekte iki bağımsız WS route'u karıştırıyordu. Paylaşılan `ConnectionManager`+WS-auth `app/infrastructure/websocket/`'e (event_bus ile aynı gerekçeyle gerçek shared-infra) çıkarıldı.
- 🔴 Kritik keşif (regresyon DEĞİL, taşımadan önce de böyleydi): `register_handlers()` hiçbir yerde çağrılmıyor — SEFER_UPDATED/SLA_DELAY event-subscriber pipeline PROD'da hiç tetiklenmiyor, `bildirim_gecmisi`'ne hiç satır düşmüyor. Aynı desen `physics_handler.py`'nin `.register()`'ı için de geçerli — muhtemelen genel bir event-bus başlangıç-kablolama boşluğu. Davranış değişikliği gerektirdiği için kapsam dışı bırakıldı, kullanıcıya raporlandı.
- `NotificationService` sınıfı kaldırıldı (B.1, location'daki `LokasyonService` kararıyla aynı gerekçe) — 4 bağımsız use-case fonksiyonuna + event-subscriber ikilisine (`handle_trip_events.py`) bölündü.
- `push_sender.py` domain(`vapid.py`)/infrastructure(`webpush_client.py`)/application(`send_push_to_user.py`+`send_push_broadcast.py`) olarak 4 dosyaya ayrıştırıldı.

**Doğrulama (gerçek Docker container — C-sürücüsü doluluğu nedeniyle önce Docker kurtarma reçetesi uygulandı, kullanıcı onayıyla, ~87GB geri kazanıldı):**
- `ruff check app v2 scripts` (host kaynağına karşı, temiz `python:3.12-slim` container) → 0 hata.
- `mypy app/` (CI'nin gerçek kapsamı, v2/ hariç) → 7/7 baseline, regresyon yok.
- `pytest --collect-only app/tests` → 6767 test, 0 hata (dalga 1'deki conftest-collect riskiyle aynı sınıf kontrol edildi, temiz).
- Notification'a özgü + dokunulan tüketici test dosyaları, gerçek `lojinext_test` DB'sine karşı: **194/194 pass** (159 unit + 11 integration/N+1/IDOR + 24 kök-`tests/`+consumer regresyon).
- OpenAPI şema drift: YOK (gerçek `dump-openapi.mjs` script'i node container'ıyla çalıştırıldı, `git diff --exit-code frontend/openapi.json` temiz).

**Sıradaki adım:** kullanıcı onayı ile main'e commit+push, CI Hard Gates'i doğrula (dalga 1'deki gibi ilk push sonrası ad-hoc-ortam kaynaklı sürprizlere karşı hazırlıklı ol), sonra dalga 3 (fleet) için yeni oturum.

## Son güncelleme
2026-07-13 — **FAZ1 dalga 2 (notification) kod tamam, lokal doğrulama tam yeşil.** main'e push edilmedi — kullanıcı onayı gerekiyor (OTURUM HİJYENİ: push sonrası bu oturum kapatılacak, dalga 3 yeni oturumda). Depo şu an **PUBLIC** (kullanıcı kararı, GHCR faturalama sorunu için geçici; iş bitince tekrar private yapılması gerekiyor — bkz. görev dışı hatırlatma).
