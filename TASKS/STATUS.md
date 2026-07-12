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
| **FAZ1** — Kod sınırları (17 kalem) | 🔲 BAŞLAMADI | Aşağıdaki dalga sırası |
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
| 1 | **location + route-simulation** (PİLOT ÇİFTİ — karşılıklı bağımlı 7/1 kenar, birlikte) | `modules/location.md` + `modules/route-simulation.md` | 🔲 |
| 2 | notification | `modules/notification.md` | 🔲 |
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

## DALGA 1 — DURUM (2026-07-12, kod+test tamam, henüz commit edilmedi)

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
- location ilgili testler: 35 passed, 0 fail.
- Tam suite `TEST_DATABASE_URL` ile koşuluyor (bkz. en güncel sonuç için conversation).

## Son güncelleme
2026-07-12 — FAZ0 kapandı. FAZ1 dalga 1 (location TAM + route_simulation kod/API TAM, kalan alt-parçalar dokümante edilmiş kapsam) — kod+test tarafı doğrulandı, henüz commit edilmedi. Depo şu an **PUBLIC** (kullanıcı kararı, GHCR faturalama sorunu için geçici; iş bitince tekrar private yapılması gerekiyor — bkz. görev dışı hatırlatma).
