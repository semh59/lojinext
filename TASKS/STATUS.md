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
| **FAZ1** — Kod sınırları (17 kalem) | 🟡 DEVAM EDİYOR — 5/17 kalem tamam | Dalga 1 (location+route-simulation) main'de yeşil; dalga 2 (notification) main'de yeşil; dalga 3 (fleet) main'de yeşil; dalga 4 (fuel) main'de yeşil; dalga 5 (driver) main'de yeşil; sıradaki: dalga 6 (auth-rbac), yeni oturumda |
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
| 2 | notification | `modules/notification.md` | ✅ main'de yeşil (commit `34e40c8`) |
| 3 | fleet | `modules/fleet.md` | ✅ main'de yeşil (commit `26967c3`) |
| 4 | fuel | `modules/fuel.md` | ✅ main'de yeşil (commit `6721cdb`) |
| 5 | driver | `modules/driver.md` | ✅ main'de yeşil (commit `9206e3f`) |
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
- ⚠️ **[YÜKSEK ÖNCELİK — dalga sırasını BEKLEMESİN]** Connection-pool leak, eşzamanlı gerçek yük altında (Locust, 30 kullanıcı) SQLAlchemy'nin "non-checked-in connection" uyarısı 52 kez üretti (test öncesi 0). App-geneli (taşınmış/taşınmamış modüller ayrımı yok, `/trips/`, `/auth/token`, `/vehicles/`, `/fuel/` hepsinde görüldü) — kod sahibi nihai olarak `platform-infra` (dalga 17) ama canlı-güvenilirlik riski taşıdığı için dalga 17'ye kadar beklenmemeli. Detay + repro + şüpheli kod konumları: `TASKS/bug-connection-pool-leak-under-load.md`. Herhangi bir oturumda, dalga sırası beklenmeden ele alınabilir.

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

## DALGA 2 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-13)

**Push geçmişi:** `eb9464d` (ana taşıma) → CI mypy gate'te kırmızı çıktı (9/7 baseline, `handle_trip_events.py`'deki 2 `subscribe()` çağrısı). Aynı zamanda bağımsız fresh-context denetim ajanı `domain/prioritizer.py`'de B.1 ihlali buldu (DB-sorgulu sınıf domain'de kalmıştı). İkisi `34e40c8` ile düzeltildi, tekrar push edildi. **CI Hard Gates tam yeşil** (`gh run view 29239910485` → `success`, hard-gates 33dk14sn, GHCR build+push 26dk29sn, prod deploy 10sn) — commit `34e40c8` main'in HEAD'i.

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

**Bağımsız denetim (kullanıcı talebiyle, push sonrası):** 2 fresh-context ajan paralel çalıştırıldı — (1) davranışsal regresyon denetimi (eski/yeni kod satır satır) → TEMİZ, hiçbir fark yok; (2) görev-dosyası uyum denetimi → dosya envanteri/taşıma adımları/katman-ihlali/route-mount/stale-referans hepsi PASS, ama 2 gerçek sorun buldu: `NotificationPrioritizer` sınıfı yanlışlıkla `domain/`de kalmıştı (B.1 ihlali, düzeltildi → `infrastructure/prioritizer.py`), STATUS.md push-durumu güncel değildi (düzeltildi). Bu denetim ayrıca CI'nin mypy gate'inde gerçek bir kırmızıyı (9/7 baseline) yakalanmasına giden düzeltme dalgasıyla aynı ana denk geldi.

## DALGA 3 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-13)

**Push geçmişi (3 commit):**
1. `67921c2` — ana taşıma (97 dosya). CI'nin "OpenAPI schema drift check" adımında kırmızı çıktı.
2. `f82b040` — YANLIŞ teşhisle atılan ilk düzeltme denemesi (bkz. "Öne çıkan kararlar/bulgular" altındaki gotcha) — hâlâ kırmızı.
3. `26967c3` — gerçek kök nedenle düzeltildi. **CI Hard Gates tam yeşil** (`gh run view 29270155491` → `success`, hard-gates 32dk46sn dahil OpenAPI drift + Playwright E2E, GHCR build+push 17dk33sn, prod deploy 9sn) — commit `26967c3` main'in HEAD'i.

**Kapsam:** fleet modülü (15 dosya, 3.632 LOC envanteri) — `araclar`/`dorseler`/`arac_bakimlari`/`vehicle_event_log`/`vehicle_spec_timeline` tablolarının tek sahibi, 31 route (vehicles+trailers+maintenance+admin_maintenance). Detaylar `TASKS/modules/fleet.md` + `v2/modules/fleet/CLAUDE.md`.

**Öne çıkan kararlar/bulgular:**
- `AracService`/`DorseService`/`MaintenanceService` sınıfları kaldırıldı (B.1, location/notification'daki kararla aynı gerekçe) — vehicle/trailer/maintenance use-case'leri bağımsız fonksiyonlara bölündü (`v2/modules/fleet/application/`, 15 dosya).
- TOCTOU plaka-unique-check kilidi (create_vehicle/create_trailer) instance-level'dan modül-level `asyncio.Lock()`'a geçti — davranışsal iyileştirme olarak dokümante edildi (üretim yolunda zaten her request yeni instance/kilit oluşturduğu için önceki hal etkisizdi).
- ARAC_ADDED/UPDATED/DELETED event publish'leri location/notification'daki gibi ölü kod (hiçbir yerde `event_bus.publish()` çağrılmıyor) — tekrar doğrulandı, events.py'de dokümante.
- 🔴 **OpenAPI drift gotcha'sı (2 tur kırmızı, gerçek kök neden bulundu):** dalga 3'ün doğrulama Docker container'ı saatlerdir ayaktaydı ve dosya değişiklikleri `docker cp` ile canlı sürece kopyalanıyordu ama backend process'i (uvicorn, tek seferlik `app` nesnesi) hiç yeniden başlatılmamıştı — bu yüzden `/openapi.json` yanıtı GERÇEKTE eski route tablosunu yansıtıyordu. Bu durum yanlışlıkla "main'de zaten var olan 6 fleet-dışı route committed şemada eksik" teşhisine yol açtı (`f82b040` bu yanlış teşhiyle 6 route ekledi — hâlâ kırmızı kaldı). Gerçek kök neden: `v2/modules/fleet/api/trailer_routes.py`'de route handler'ı `get_trailer_template` olarak bırakılmışken aynı isimde import edilen use-case fonksiyonuyla (`export_trailers.get_trailer_template`) çakışıyordu; Python sessizce ikincisini üstüne yazdığı için route handler `get_trailer_template_endpoint` olarak yeniden adlandırılmak zorunda kalınmıştı — bu GERÇEK bir API-kontrat değişikliğiydi (operationId değişti). Düzeltme: import `as get_trailer_template_usecase` alias'landı, route handler orijinal adını korudu. **Ders:** OpenAPI drift/route-tablosu doğrulaması için container'ı HER ZAMAN yeniden başlat (`docker compose restart backend`) ve şemayı gerçek `node scripts/dump-openapi.mjs` ile üret — Python'da elle `json.dumps(..., separators=(',',':'))` ile yeniden serileştirmek JS'in `JSON.stringify` çıktısıyla bit-bit eşleşmeyebilir (blob hash'i CI'nınkiyle tutmaz), yanlış-pozitif/yanlış-negatif teşhise yol açar.

**Doğrulama (gerçek Docker container + `lojinext_test` DB):**
- `ruff check app v2 tests --select E,F,W,I` → temiz.
- `mypy app/` → 7/7 baseline, regresyon yok.
- `pytest --collect-only`: `app/tests` 6760 test / kök `tests/` 266 test, 0 hata.
- Tam suite (`app/tests`, gerçek DB'ye karşı): 6684 passed + 42 pre-existing ortam-kaynaklı hata (route_simulation/location/notification/redis modülleri — api-stub ağ topolojisi, Redis Sentinel, VAPID, `USE_SEFER_FUEL_ESTIMATOR` env, `.env.example` cwd — dalga 1-2'de zaten dokümante edilmiş kategoriler, `git diff --stat` ile bu dosyaların dalga 3'te DOKUNULMADIĞI doğrulandı). Fleet'e özgü 3 gerçek kırık test bulunup düzeltildi: `test_activity_log.py` (patch target eski endpoint modülüne işaret ediyordu), `test_maintenance_predictions.py` (aynı sorun, `maintenance_service` modülü silinmişti), `test_production_foundation_guards.py` (truthfulness-guard testi silinen `arac_repo.py` yolunu okuyordu — dalga 1'deki aynı sınıf gotcha'nın tekrarı).
- OpenAPI schema drift: nihai halde YOK (yukarıdaki gotcha'da anlatılan 2 turluk düzeltmeden sonra CI'da doğrulandı yeşil).

**Test-dosyası dönüşümü (büyük mekanik iş, ~40 dosya):** Bir fork ajanı ana dönüşümü yaptı ama oturum API limitine takılıp yarıda kesildi (`AracService(arac_service=...)` kalıntıları, `container.arac_service` assertion'ı); ana oturum devraldı, kalanları tamamladı + gerçek DB'ye karşı doğruladı (636/636 + 102/102 + 107/107 pass ayrı batch'lerde).

## DALGA 4 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-14)

**Push geçmişi (4 commit):**
1. `03e14e5` — ana taşıma (78 dosya, 2.434 satır ekleme/2.439 silme). CI'nin "Backend type check (mypy)" adımında kırmızı çıktı (8 hata / 7 baseline).
2. `a90027d` — mypy düzeltmesi: `import_service.py`'nin `bulk_add_yakit`'e geçirdiği `YakitCreate` listesi ile fonksiyonun beklediği `YakitAlimiCreate` tipi arasında nominal bir tip farkı vardı — taşımadan ÖNCE de vardı (`self.yakit_service` untyped constructor param olduğu için mypy görmüyordu), free function'a geçişle görünür oldu. `cast()` ile dokümante edildi, davranış değişmedi (duck-typing zaten çalışıyordu). mypy 7/7 baseline'a döndü ama bu turda "Backend unit tests" adımı repo kökündeki **bağımsız `tests/` klasöründe** (dalga 1'in aynı sınıf gotcha'sı) 2 stale import ile kırmızı çıktı.
3. `d9c4569` — kök `tests/test_fuel_prediction.py` + `tests/unit/test_yakit_service.py` yeni v2 path'lerine dönüştürüldü (`TestYakitService::test_calculation_safety`/`test_service_initialization` kaldırıldı — `YakitTahminService.model` dead constructor attribute'unu test ediyorlardı, free-function tasarımında hiç yok). Bu turda tek bir kalıntı daha çıktı: `test_prediction_service_coverage.py::test_get_prediction_service_singleton` silinen `YakitTahminService`'i patch'liyordu.
4. `6721cdb` — son kalıntı düzeltildi. **CI Hard Gates tam yeşil** (`gh run view 29318319844` → hard-gates `success`, 33dk1sn) — commit `6721cdb` main'in HEAD'i.

**Kapsam:** fuel modülü (13 dosya, ~2.809 LOC envanteri) — `yakit_alimlari`/`yakit_periyotlari`/`yakit_formul` tablolarının tek sahibi, 12 route (fuel+admin_fuel_accuracy). Detaylar `TASKS/modules/fuel.md` + `v2/modules/fuel/CLAUDE.md`.

**Öne çıkan kararlar/bulgular:**
- `YakitService`/`PeriodCalculationService`/`YakitTahminService` sınıfları kaldırıldı (B.1, location/notification/fleet'teki kararla aynı gerekçe). Her üçünün de constructor-injected repo/model parametreleri dead weight'ti (hiçbir metot gövdesi okumuyordu) — free function'lara taşınmadı.
- YAKIT_ADDED/UPDATED/DELETED event publish'leri diğer modüllerdeki gibi ölü kod (`@publishes` yalnız metadata attribute'u set ediyor, gerçek `event_bus.publish()` çağrısı yok) — AMA bu modülde diğerlerinden FARKLI olarak GERÇEK iki abone var (`model_training_handler.py` ML retrain için, `cache_invalidation.py` cache temizliği için) ve ikisi de bugün hiç tetiklenmiyor; taşımadan önce de böyleydi (regresyon değil), events.py'de fleet/location'dan daha yüksek-etkili bir bulgu olarak ayrıca vurgulandı.
- Rolling outlier check (`_check_rolling_outlier`) GERÇEKTEN event yayınlıyor (`ANOMALY_DETECTED`, `@publishes` dekoratörüne bağımlı değil, doğrudan `event_bus.publish()` çağırıyor) — YAKIT_* event'lerinin aksine bu ölü kod DEĞİL.
- trip↔fuel senkron çift (`recalculate_vehicle_periods`'in `sefer_repo` bağımlılığı) bilinçli olarak fuel tarafında bırakıldı — görev dosyasının kararı, trip taşınınca güncellenecek.
- `yakit_alimlari.durum` Türkçe enum'u (`Bekliyor/Onaylandı/Reddedildi`) bu dalgada DEĞİŞTİRİLMEDİ — FAZ3 sözlüğüne not düşüldü.
- OpenAPI şeması yeniden üretildi — kontrat/route tablosunda değişiklik YOK, yalnız route docstring'lerindeki "(Service Layer)" ibaresi kaldırıldığı için diff oluştu (Service sınıfları artık yok).
- 🔴 **mypy latent-bug gotcha'sı (fleet'in OpenAPI-drift gotcha'sıyla aynı sınıf bulgu):** `import_service.py`'nin `bulk_add_yakit`'e `YakitCreate` (schemas.py) listesi geçirmesi ile fonksiyonun tipinin `YakitAlimiCreate` (entities/models.py) beklemesi arasındaki nominal-tip uyuşmazlığı taşımadan ÖNCE de vardı ama `self.yakit_service`'in untyped constructor param olması yüzünden mypy'ye görünmüyordu. Free function'a geçiş bunu ortaya çıkardı. **Ders:** bir servis sınıfını free function'a çevirirken çağıranların untyped `self.<servis>` üzerinden geçirdiği argümanlar birden statik olarak kontrol edilir hale gelir — mevcut (görünmeyen) tip uyuşmazlıkları CI'da yeni "regresyon" gibi görünebilir; kök neden taşımadan önce de var olan bir uyuşmazlıktır, `cast()` ile dokümante edilip düzeltilir (fonksiyonun tipini gevşetmek yerine).
- 🔴 **Kök `tests/` klasörü gotcha'sı tekrarı (dalga 1'de de görülmüştü):** repo kökünde `app/tests/`'ten bağımsız bir `tests/` klasörü var, CI'nın "Backend unit tests" adımı onu da koşuyor; fork'un + ana oturumun `app/tests/` odaklı grep taraması bu klasörü başta kaçırdı (`tests/test_fuel_prediction.py`, `tests/unit/test_yakit_service.py`). 2. turda bulunup düzeltildi.

**Doğrulama (gerçek Docker container + `lojinext_test` DB):**
- `ruff check app v2` → temiz.
- `mypy app/` → 7/7 baseline, regresyon yok (CI'da doğrulandı).
- `pytest --collect-only`: `app/tests` 6751 test / kök `tests/` 264 test, 0 hata.
- Fuel-özgü 27+2 test dosyası (fork + ana oturum bulguları dahil): 493+7+45 = 545 test, hepsi pass (2 skip — OPET api-stub erişilemez, beklenen).
- CI'nın kendi "Backend unit tests" koşumu (nihai, 4. push): 5423 passed, 23 skipped, 1262 deselected — 0 fail.
- OpenAPI schema drift: nihai halde YOK.
- Bir fork ajanı test dönüşümünün büyük kısmını yaptı (18 doğrudan + 12 grep'le bulunan ek dosya = 30 dosya), 1 gerçek prod bug buldu+düzeltti (`import_service.py`'nin Excel yakıt import'u silinen `app.schemas.yakit`'i import ediyordu — `ImportError` riski, canlıya hiç gitmemiş olurdu). Ana oturum kalan 2 tur kırmızıyı (kök `tests/` + `test_prediction_service_coverage.py`) buldu+düzeltti.

## DALGA 5 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-14)

**Push geçmişi (3 commit):**
1. `f2321a1` — ana taşıma (107 dosya, 14 kaynak dosya taşındı/silindi). CI'nin "Backend type check (mypy)" adımında kırmızı çıktı (8 hata / 7 baseline).
2. `f41f74a` — mypy düzeltmesi: `v2/modules/driver/schemas.py`'ye taşınan `SoforResponse.ehliyet_sinifi` (permissive `str`, `@field_validator(mode="before")` ile runtime'da normalize) base class'taki `Literal` alanını override ediyordu — aynı desen taşımadan önce `app/schemas/sofor.py`'de de vardı ve `[mypy-app.schemas.*]` suppress bloğuyla gizleniyordu; yeni konumda o glob'a uymadığı için ortaya çıktı. `[mypy-v2.modules.*.schemas]` genel section'ı eklendi (regresyon değil, config-kapsama boşluğu). Bu turda mypy 7/7'ye döndü ama "Frontend — Unit tests with coverage" adımı kırmızı çıktı.
3. `9206e3f` — **gerçek regresyon** bulundu+düzeltildi: `DriverScoreBreakdown.real-backend.test.tsx` (gerçek backend'e karşı koşan frontend testi) `GET /drivers/{id}/score-breakdown`'da 500 yakaladı — backend log: `Database session not initialized in SoforRepository`. Kök neden: `get_score_breakdown_sofor`/`get_route_profile_sofor`, `uow=None` verildiğinde modül-seviyeli `get_sofor_repo()` singleton'ını (hiçbir zaman session'a bağlanmaz) doğrudan `get_by_id()` için kullanıyordu. Eski kod bu ikisini `Depends(get_sofor_service)` → `SoforService(repo=uow.sofor_repo)` (session-bound, per-request) ile çağırıyordu — free-function migrasyonunda route'lar uow hiç geçirmediği için düştü. Fix: `uow=None` olduğunda artık kendi `UnitOfWork()`'ünü açıp session-bound repo üzerinden `get_by_id` çağırıyor (fonksiyonun geri kalanı zaten bu deseni kullanıyordu). **CI Hard Gates tam yeşil** (`gh run view 29344960332` → hard-gates 25dk29sn, GHCR build+push + prod deploy dahil `success`) — commit `9206e3f` main'in HEAD'i.

**Kapsam:** driver modülü (14 dosya, ~4.5K LOC) — `soforler`/`sofor_ad_soyad_trigram`/`sofor_adaptasyon`/`coaching_deliveries` tablolarının tek sahibi, 17 route (drivers+coaching). Detaylar `TASKS/modules/driver.md` + `v2/modules/driver/CLAUDE.md`.

**Öne çıkan kararlar/bulgular:**
- `SoforService`/`SoforAnalizService`/`SoforDegerlendirmeService` sınıfları kaldırıldı (B.1, location/notification/fleet/fuel'deki kararla aynı gerekçe) — her use-case opsiyonel `uow: UnitOfWork | None = None` parametresi alan bağımsız fonksiyon.
- 3 sınıf istisnası kaldı (`RouteSimulator`/`LokasyonHydrator` ile aynı gerekçe): `DriverCoachingEngine` (Groq/anomali client'ları enjekte eden tek-pipeline), `DriverPerformanceML` (mutable LightGBM model state — `self.is_trained`/`self.feature_importance`), `SoforSeferPDFService` (template-method builder, `PDFReportGenerator`'dan miras).
- SOFOR_ADDED/UPDATED/DELETED publish decorator'ları repo-genelinde tekrarlayan ölü kod bulgusuyla aynı sınıf (fuel/fleet/notification/location) — yeniden doğrulandı, `event_bus.publish()` hiç çağrılmıyor.
- 🔴 **Yeni bulgu (regresyon değil):** `driver.calculate_performance_score` Celery task'ı taşımadan ÖNCE de `celery_app.py`'nin import listesinde yoktu — hiç kayıtlı olmamış, prod'da hiç çalıştırılamamış orphan task. Davranış değişikliği gerektirdiği için import eklenmedi, `v2/modules/driver/CLAUDE.md`'de dokümante.
- `sefer_repo.py`'deki (trip modülü, henüz taşınmadı) 6 driver-özel sorgu bu dalgada TAŞINMADI (trip dalga 14'e bırakıldı, görev dosyasının kararıyla uyumlu) — yalnız import-path düzeltmesi yapıldı (`app.core.ml.driver_route_profile` → `v2.modules.driver.domain.route_profile`).
- 🔴 **score-breakdown/route-profile 500 gotcha'sı (yukarıda anlatıldı, commit `9206e3f`):** free-function migrasyonunda "uow verilmezse modül-singleton repo kullan" tasarım kararı, ORM `get_by_id()` gibi session gerektiren İLK çağrı için yanlıştı (yalnız raw-SQL metotlar için değil — CLAUDE.md'deki "Singleton repos need UoW for raw-SQL methods" gotcha'sı eksikti, ORM çağrıları da aynı şekilde çöküyor). **Ders:** bir per-request DI servisini (`Depends(get_sofor_service)` → session-bound repo) free function'a çevirirken, route'un uow'u YENİ fonksiyona geçirip geçirmediğini kontrol et — geçirmiyorsa fonksiyonun `uow=None` fallback'i kendi `UnitOfWork()` açmalı, bare module-singleton'ı asla doğrudan ORM/raw-SQL çağrısında kullanmamalı.

**Doğrulama (gerçek Docker container + `lojinext_test` DB):**
- `ruff check app v2` → temiz, `ruff format` → temiz.
- `mypy app/` → 6/7 baseline (mypy.ini fix'i sonrası, regresyon yok — CI'da doğrulandı).
- `pytest --collect-only`: `app/tests` + kök `tests/` toplam 7007 test, 0 hata.
- Driver-özgü + dokunulan tüketici test dosyaları (46 dosya) gerçek `lojinext_test` DB'ye karşı: 901/902 pass (1 fail pre-existing/migrasyonla ilgisiz — `test_analysis_and_report.py::test_generate_vehicle_report`, `git stash` ile main'de de aynı hatanın var olduğu doğrulandı).
- `test_sofor_service_coverage.py`'nin `TestGetScoreBreakdown`/`TestGetRouteProfile` sınıfları (13 test) fix sonrası gerçek DB'ye karşı 0-mock'a çevrildi (eski targeted-mock gerekçesi ortadan kalktı) — yalnız clamp-testi DB CHECK constraint'i yüzünden dar bir `get_by_id` patch'i koruyor.
- OpenAPI schema drift: nihai halde YOK (container restart + `dump-openapi.mjs` ile doğrulandı).
- CI'nın kendi "Backend unit tests" + "Frontend — Unit tests with coverage" koşumu (nihai, 3. push): tüm gate'ler `success`.
- İlk iki denemede (bir fork ajanı taşımayı yaptı, context/turn limitine 3 kez takılıp yarıda kesildi — commit/push hiç tamamlanamadı) ana oturum devraldı: kalan test dönüşümünü bitirdi, doğrulamayı tekrarladı, mypy + regresyon bulgularını bulup düzeltti, commit/push/CI-izleme döngüsünü tamamladı.

## Son güncelleme
2026-07-14 — **FAZ1 dalga 5 (driver) TAMAMLANDI ve main'de yeşil** (commit `9206e3f`, CI Hard Gates `success`, hard-gates 25dk29sn + GHCR build/push + prod deploy). OTURUM HİJYENİ: bu oturum kapatılıyor, dalga 6 (auth-rbac) yeni oturumda `TASKS/modules/auth-rbac.md` okunarak, kullanıcı onayı istenerek başlar. Depo şu an **PUBLIC** (kullanıcı kararı, GHCR faturalama sorunu için geçici; iş bitince tekrar private yapılması gerekiyor — bkz. görev dışı hatırlatma).
