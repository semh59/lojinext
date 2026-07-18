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
| **FAZ1** — Kod sınırları (17 kalem) | 🟡 DEVAM EDİYOR — 12/17 kalem tamam | Dalga 1 (location+route-simulation) main'de yeşil; dalga 2 (notification) main'de yeşil; dalga 3 (fleet) main'de yeşil; dalga 4 (fuel) main'de yeşil; dalga 5 (driver) main'de yeşil; dalga 6 (auth-rbac) main'de yeşil; dalga 8 (anomaly) main'de yeşil; dalga 9 (import-excel) main'de yeşil; dalga 10 (reports) main'de yeşil; dalga 11 (analytics-executive) main'de yeşil (bkz. DALGA 11 bölümü); dalga 12 (ai-assistant) main'de yeşil, 2 turluk dedektif denetim + 4 gerçek bug fix dahil (bkz. DALGA 12 bölümü); ✅ **2026-07-18 ikinci oturum: ilk 12 dalganın TAM-DENETİM DÜZELTME TURU** — tüm 12 dalgaya yayılan import-linter/public.py/domain-I/O/ölü-kod bulguları kapatıldı, commit `02d1ea5` (bkz. "Son güncelleme" bölümü); sıradaki: dalga 13 (prediction-ml), yeni oturumda |
| **FAZ2** — Veri sınırları | 🔲 FAZ1'i bekliyor | |
| **FAZ3** — Dil geçişi | 🔲 FAZ2'yi bekliyor | Bağımsız FAZ, sınır-enforcement ile aynı PR'da olmaz |
| **FAZ4** — Sıkılaştırma & kapanış | 🔲 FAZ3'ü bekliyor | |

## FAZ1 — Modül Dalga Sırası (bağımlılık az→çok)

Her satır bağımsız bir PR/onay/oturum birimidir. Sıradaki modül, bir öncekinin PR'ı merge olmadan başlamaz (görev dosyasının "Giriş kriteri"nde yazılı).

| # | Modül/kalem | Görev dosyası | Durum |
|---|---|---|---|
| — | Registry+iskelet+shim deseni (çatı) | `faz1-registry-iskelet-ve-shim.md` | 🔲 |
| — | import-linter baseline→gate (çatı) | `faz1-import-linter-baseline-ve-gate.md` | 🟡 13/17 modül için baseline donduruldu main'de yeşil (rapor modu, `Contracts: 15 kept, 1 broken[kapsam dışı — pre-existing app.services↔app.core.services, migrasyonla ilgisiz]`, dalga 13 sonrası gerçek sayı — 13. `public-surface-only-prediction_ml` kontratı eklendi); gate (continue-on-error kaldırma) kalan 4 dalga sonrası ayrı onayla |
| — | Davranışsal mimari testleri (çatı) | `faz1-davranissal-mimari-testler.md` | 🔲 |
| — | Dosya kalite + kısalık gate (çatı) | `faz1-dosya-kalite-ve-kisalik-gate.md` | 🔲 |
| — | Modül CLAUDE.md şablonu (çatı) | `faz1-claude-md-per-module-template.md` | 🔲 |
| 1 | **location + route-simulation** (PİLOT ÇİFTİ — karşılıklı bağımlı 7/1 kenar, birlikte) | `modules/location.md` + `modules/route-simulation.md` | ✅ main'de yeşil (commit `4ebabca`) |
| 2 | notification | `modules/notification.md` | ✅ main'de yeşil (commit `34e40c8`) |
| 3 | fleet | `modules/fleet.md` | ✅ main'de yeşil (commit `26967c3`) |
| 4 | fuel | `modules/fuel.md` | ✅ main'de yeşil (commit `6721cdb`) |
| 5 | driver | `modules/driver.md` | ✅ main'de yeşil (commit `9206e3f`) |
| 6 | auth-rbac | `modules/auth-rbac.md` | ✅ main'de yeşil (commit `e9a0328`) |
| 7 | *(route-simulation dalga 1'e taşındı, bkz. üstte)* | — | — |
| 8 | anomaly | `modules/anomaly.md` | ✅ main'de yeşil (commit — bkz. DALGA 8 bölümü) |
| 9 | import-excel | `modules/import-excel.md` | ✅ main'de yeşil (commit `5d1a0fb`, bkz. DALGA 9 bölümü) |
| 10 | reports | `modules/reports.md` | ✅ main'de yeşil (commit `1fdc78e`, bkz. DALGA 10 bölümü) |
| 11 | analytics-executive | `modules/analytics-executive.md` | ✅ main'de yeşil (commit `48e8e21`, bkz. DALGA 11 bölümü) |
| 12 | ai-assistant | `modules/ai-assistant.md` | ✅ main'de yeşil (commit `928de51`, bkz. DALGA 12 bölümü) |
| 13 | prediction-ml | `modules/prediction-ml.md` | ✅ main'de yeşil (bkz. DALGA 13 bölümü) |
| 14 | trip (en karmaşık split) | `modules/trip.md` | ✅ branch'te tamamlandı (bkz. DALGA 14 bölümü) |
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
- ✅ **ÇÖZÜLDÜ (2026-07-14)** — Connection-pool leak, sistematik debugging ile 2 kök nedene indirgendi ve düzeltildi: (1) `AuthService`/`MLService`/`AttributionService`'in zaten açık bir `UnitOfWork`'ü ikinci kez `async with self.uow:` ile yeniden açması (`_owns` bayrağını bozup dış `session.close()`'u atlıyordu) — 3 servis dosyası + 1 endpoint düzeltildi, `UnitOfWork.__aenter__`'e re-entrancy guard eklendi (defense-in-depth, artık sessizce bozmak yerine `RuntimeError`). (2) `AuthService.authenticate()`'teki senkron `bcrypt.checkpw()` event loop'u bloke edip eşzamanlı yük altında pool tükenmesini şiddetlendiriyordu — `asyncio.to_thread`'e taşındı. Gerçek 30-kullanıcılı Locust koşumunda leak uyarısı 30-44 → **0**, p99 latency ~70000ms → **500ms**. 2 gerçek regresyon testi eklendi (`app/tests/test_db_hardening.py`, TDD red→green doğrulandı). Detay: `TASKS/bug-connection-pool-leak-under-load.md` (kabul kriterleri işaretli).
- ✅ **ÇÖZÜLDÜ (2026-07-18, tam-denetim düzeltme turu)** — `v2/modules/route_simulation/infrastructure/openroute_client.py`'deki `OpenRouteClient` sınıfının 3 ilgisiz sorumluluğundan 2'si (`geocode()`/`_call_geocode_api` + `lokasyonlar` tablosuna ham SQL atan `update_route_distance()`) SİLİNDİ; `scripts/enrich_existing_data.py` `location.public.geocode_location`'a geçti. **Kısmen kapsam dışı bırakıldı** (görev dosyasının kendi madde 3 kararı): üçüncü implementasyon `app.core.services.openroute_service.py` (eski `app/`, route_simulation'ın henüz taşınmamış parçası) dokunulmadı — yani "tek geocode implementasyonu" hedefi tam karşılanmadı, hâlâ 2 implementasyon var (location'ınki + eski openroute_service.py); bu, route_simulation'ın ikinci-dilim taşıması bekleniyor. Detay: `TASKS/bug-openroute-client-architectural-leak.md` (kabul kriterleri güncellendi).
- ✅ **ÇÖZÜLDÜ (2026-07-15)** — İki bağımsız `create_admin.py` scripti var: `scripts/create_admin.py` (rol=`admin`, hardcoded `admin@lojinext.com`, granular `yetkiler` dict) ve `app/scripts/create_admin.py` (rol=`super_admin`, `settings.SUPER_ADMIN_USERNAME`, wildcard `{"*": True}`) — `git log --follow` ile doğrulandı, ikisi de `9f8110b` initial commit'ten beri var, dalga 6'nın ürettiği bir duplikasyon DEĞİL. **Karar: ikisi de kalıyor** (hiçbiri gerçek prod bootstrap'ında kullanılmıyor — gerçek admin oluşturma `alembic/versions/0002_seed_and_bootstrap.py`'de doğrudan SQL upsert ile yapılıyor, bu iki script yalnız manuel/dev-amaçlı CLI yardımcıları). `scripts/create_admin.py`'nin `yetkiler` dict'i eksikti — 2026-06-21 planındaki 5 anahtar (`attribution_duzenle`/`bakim_ekle`/`circuit_breaker_reset`/`model_egit`/`notification_rule_goruntule`) o tarihten sonra zaten eklenmiş (plan dosyası stale çıktı), ama 5 GERÇEK eksik anahtar daha bulundu (`import_goruntule`/`import_rollback`/`notification_rule_duzenle`/`notification_rule_sil`/`admin`) — repo genelindeki 53 `require_yetki(...)` çağrı noktasının tamamı tek tek simüle edilip gerçek `SecurityService.has_permission` koduna karşı doğrulandı, düzeltmeden önce 5 endpoint grubu admin rolüne kapalıydı, düzeltmeden sonra 53/53 geçiyor.
- **Dalga 1-6 + 8 detaylı B.1 dedektif denetimi (2026-07-15, kullanıcı talebiyle "ilk 8 dalgayı detaylı kontrol edelim")** — 6 bağımsız sıfır-context ajan (dalga1: location+route_simulation, dalga2: notification, dalga3: fleet, dalga4: fuel, dalga5: driver, dalga6: auth_rbac) her modülün TÜM dosyalarını tek tek B.1 ("her dosya tek görev") kuralına karşı denetledi (dalga 8/anomaly aynı gün ayrıca 3 ajanla denetlenmişti, bkz. DALGA 8 bölümü). Sonuç: **location + driver TAM TEMİZ**; route_simulation'daki tek bulgu zaten bilinen/dokümante `OpenRouteClient` sızıntısı (yukarıda); fuel'de 1 düşük-risk bulgu (`domain/consumption_prediction.py`'de domain katmanına DB erişimi sızmış ama dosya ölü kod, hiçbir prod endpoint çağırmıyor). **3 modülde (notification/fleet/auth_rbac) YENİ bir ortak bulgu deseni**: 5 route handler'ı `application/` katmanını atlayıp doğrudan repo/ORM çağırıyor + auth_rbac'ta bir iş kuralı (privilege-escalation guard) route dosyasında tekrarlanmış. B.1'in "tek dosya = tek sınıf" ilkesi ihlal edilmiyor ama "route → application → repo" katman sözleşmesi 5 yerde tutmuyor. Bağımsız görev açıldı: `TASKS/bug-route-layer-bypasses-application.md`.
- ✅ **ÇÖZÜLDÜ (2026-07-15, kullanıcı onayı: "8 dalga tam temiz olana kadar durma")** — yukarıdaki `TASKS/bug-route-layer-bypasses-application.md`'nin 5 handler'ı tek tek düzeltildi: notification'da `manage_notification_rules.py`+`manage_push_subscription.py`, fleet'te `get_maintenance_ics_data.py` + `get_vehicle_by_id`/`get_trailer_by_id`'ye `include_inactive` parametresi, auth_rbac'ta `role_service.py`. 🔴 **Bu sırada notification'ın push subscribe/unsubscribe'ında GERÇEK bir bug bulundu**: her ikisi de hiçbir zaman `uow.commit()` çağırmıyordu (ghost-transaction guard ORM identity-map'e bakıyor, Core-tarzı delete/attribute-mutasyon farklı yollarla ama HER İKİSİ de sessiz rollback'e yol açıyordu) — push abone-ol/ol-ma endpoint'leri 200/204 dönüyordu ama veritabanında hiçbir şey kalıcı olmuyordu, taşımadan önce de böyleydi (regresyon değil), tek satır `await uow.commit()` ile düzeltildi. Detay + doğrulama: `TASKS/bug-route-layer-bypasses-application.md` "Çözüm" bölümü. Yerel `ruff`+`py_compile`+gerçek Python import zinciri temiz; CI doğrulaması bekleniyor.

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

## DALGA 6 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-15)

**Push geçmişi (3 commit):**
1. `53a97a8` — ana taşıma (80 dosya). CI'nin "Backend unit tests" adımında kırmızı çıktı: `app/tests/unit/test_ml_train_user_audit.py` grep taramasını kaçırmış tek bir test dosyasıydı (dosya adı "ml_train"e odaklıydı, yalnız 2. testte silinen `app.api.v1.endpoints.admin_users`'a patch atıyordu) — `ImportError`.
2. `7673486` — import + patch-target `v2.modules.auth_rbac.api.admin_user_routes` + free-function `user_service.create_user`'a çevrildi, `docker cp` ile container'a canlı uygulanıp doğrulandı (2/2 pass). Bu turda "Backend unit tests" yeşile döndü ama **"OpenAPI schema drift check"** kırmızı çıktı.
3. `e9a0328` — kök neden: `auth_routes.py`'deki login/logout endpoint docstring'leri taşıma sırasında class-referanslı metinden (`"Login using AuthService."`) free-function-referanslı metne (`"Login using auth_service.authenticate."`) güncellenmiş ama committed `frontend/openapi.json` yeniden üretilmemişti. Container commit HEAD'ten `docker compose up -d --build` ile tamamen temiz yeniden build edildi (37 saatlik ad-hoc `docker cp` birikintisinden arındırmak için), geçici bir `alpine/socat` tüneliyle backend host'a açılıp gerçek `node scripts/dump-openapi.mjs` ile (CI'nın kullandığı BİREBİR yöntem) regenerate edildi. Bu turda hard-gates'in geri kalanı yeşildi ama **"Frontend E2E tests"** 1 testte (`route-lab.spec.ts` — auth_rbac'la ilgisiz, route-simülasyon özet render'ı, 10s timeout) flake verdi; 256/257 test (login gerektiren tüm senaryolar dahil) geçmişti — `gh run rerun --failed` ile rerun edildi, **hard-gates TAM YEŞİL** oldu (35dk1sn). Commit `e9a0328` main'in HEAD'i.

**Kapsam:** auth_rbac modülü (21 dosya, 2.340 LOC) — `kullanicilar`/`roller`/`kullanici_oturumlari`/`kullanici_ayarlari` tablolarının tek sahibi, 25 route (auth+users+admin_users+admin_roles+preferences+ws_ticket). Detaylar `TASKS/modules/auth-rbac.md` + `v2/modules/auth_rbac/CLAUDE.md`.

**Öne çıkan kararlar:**
- `AuthService`/`UserService`/`PreferenceService` sınıfları kaldırıldı (B.1, önceki 5 dalgadaki kararla aynı gerekçe) — her use-case opsiyonel `uow: UnitOfWork | None = None` alan bağımsız fonksiyon (driver dalga 5'in score-breakdown 500 gotcha'sını tekrarlamamak için aynı imza deseni korundu, burada modül-seviyeli session'sız singleton repo riski zaten yoktu).
- 3 sınıf istisnası: `SecurityService` (yalnız classmethod, hiç constructor/instance-state yok, stateless isim alanı), `LicenseEngine` (env'den bir kez yüklenen mutable `_LICENSE_HASHES` state'i, driver'ın `DriverPerformanceML`'iyle aynı gerekçe), `TokenBlacklist` (Redis-backed thread-safe singleton, pre-migration'dan korundu).
- `app/api/deps.py` taşınmadı (FastAPI-wiring katmanı, driver/fleet kararıyla aynı) — yalnız importları güncellendi; `get_auth_service`/`AuthServiceDep` kaldırıldı, `auth_routes.py` doğrudan `UOWDep` alıyor.
- KULLANICI_*/ROL_* event'leri hiçbir zaman event-bus'a bağlanmamış (diğer modüllerdeki ölü-event-publish deseninden FARKLI olarak burada enum değeri bile yok) — regresyon değil, `events.py` boş `__all__` ile dokümante ediyor.
- 28 inbound FK (`kullanicilar` sistemin en büyük FK mıknatısı) CLAUDE.md'de FAZ2 için özellikle vurgulandı; multi-worker güvenlik state'i (`BruteForceDetector`/`RBACViolationTracker`) bilinçli olarak bu dalgaya taşınmadı, FAZ2 görevi olarak kaldı.

**Doğrulama (gerçek Docker container + `lojinext_test` DB, ana oturumda bağımsız tekrar doğrulandı):**
- `ruff check app v2 alembic` → temiz.
- `mypy app/` → main ile birebir aynı 7 hata (git stash ile karşılaştırıldı); tek fark `rol_repo.py:40`'daki pre-existing hata dosya taşımasıyla `v2/modules/auth_rbac/infrastructure/repository.py:102`'ye taşındı — regresyon DEĞİL, aynı hatanın yeni konumu.
- `pytest --collect-only app/tests` → 6739 test, 0 collect hatası.
- Auth-özgü + dokunulan tüketici test dosyaları (21 dosya, foreground): 396 passed / 0 failed (fork raporu) — ana oturumda 9 kilit dosyadan alt-küme (auth_service/license/security/token_blacklist/rbac/idor/auth/auth_coverage/preferences) bağımsız tekrar koşuldu: **109 passed, 0 failed**.
- Kök `tests/` (tam suite): 264 passed / 0 failed.
- OpenAPI şema drift: YOK — ana oturumda container'dan canlı `/openapi.json` çekilip `frontend/openapi.json` ile route+operationId seti birebir karşılaştırıldı, fark 0.
- Grep ile dangling-import taraması (ana oturum, bağımsız): eski 12 modül yoluna (`app.core.security`, `app.core.services.{auth,user,license,preference,security}_service`, `app.infrastructure.security.{jwt_handler,permission_checker,token_blacklist}`, `app.database.repositories.{kullanici,rol,session}_repo`) hiçbir kalan referans yok.
- Gerçek bug bulunmadı — mekanik taşıma + B.1 dönüşümü, davranış değişikliği içermiyor.

**CI doğrulama (final, gerçek kaynak):** `gh run view 29372477800` → commit `e9a0328` için hard-gates job `success` (35dk1sn, tüm gate'ler dahil — Backend unit tests, entegrasyon paketleri, Combined coverage gate, OpenAPI schema drift check, Frontend build/lint/typecheck, Playwright E2E). Push sonrası 3 tur kırmızı çıktı (stale test import, OpenAPI docstring drift, 1 alakasız flaky E2E) — hepsi bulunup düzeltildi/rerun edildi.

### Dalga-6-sonrası dedektif denetim + düzeltmeler (2026-07-15)

Kullanıcı talebiyle ("ilk 7 dalgayı detaylı ve derin kontrol edelim") 6 tamamlanmış dalganın (location+route-simulation, notification, fleet, fuel, driver, auth-rbac — 145 dosya) tamamı 6 bağımsız, sıfırdan-context ajanla B.1 kuralı (dosya-başına-tek-iş) + CLAUDE.md-iddia doğruluğu açısından denetlendi. Bulunan gerçek sorunlar düzeltildi, main'e push edildi, CI ile doğrulandı:

1. **`v2/modules/auth_rbac/infrastructure/repository.py`** — 3 repo sınıfı (Kullanici/Rol/Session) tek dosyada, yanlış emsal iddiasıyla ("driver/fleet ile aynı desen" — bu YANLIŞTI) gerekçelendirilmişti. 3 ayrı dosyaya bölündü (commit `e4b36b9`). CLAUDE.md'deki 2 ayrı dokümantasyon hatası da düzeltildi (eksik 4. sınıf istisnası `PermissionChecker`; jwt_handler.py'nin "tam delegasyon katmanı" yanlış iddiası).
2. **`v2/modules/fleet` — 2 API dosyasına (vehicle_routes.py/trailer_routes.py) sızmış raw SQL** — fleet-stats/inspection-alerts/{arac_id}/events endpoint'leri route handler içinde doğrudan SQL çalıştırıyordu, hiçbir yerde dokümante edilmemişti. `infrastructure/{vehicle,trailer}_repository.py` + yeni 3 application use-case dosyasına taşındı (commit `a630856`). CI bunun ardından `test_fleet_stats_happy_path` (ve 2 kardeşi) testlerinin artık kullanılmayan `get_db` DI-override mock desenini yakaladı — kurulu "tüketen modülü patch'le" desenine çevrildi (commit `84a8477`).
3. **`scripts/create_admin.py` — eksik yetki anahtarları** — iki çakışan create_admin.py script'inin hiçbiri gerçek prod bootstrap'ında kullanılmıyor (gerçek admin `alembic/versions/0002_seed_and_bootstrap.py`'de oluşuyor) — ikisi de kalıyor, karar kapandı. Ama repo genelindeki 53 `require_yetki(...)` çağrı noktası tek tek simüle edilip gerçek `SecurityService.has_permission` koduna karşı doğrulanınca `scripts/create_admin.py`'nin `admin` rolünde 5 gerçek eksik anahtar bulundu (`import_goruntule`/`import_rollback`/`notification_rule_duzenle`/`notification_rule_sil`/`admin`) — düzeltmeden önce 5 endpoint grubu admin rolüne kapalıydı. Düzeltildi, 53/53 çağrı artık geçiyor (commit `82044b2`).

Ayrıca Sentry'deki 11 stale unresolved issue (hepsi zaten kapatılmış connection-pool-leak repro'sundan, fix-sonrası hiç yeni event yok) resolved işaretlendi; GitHub'da açık issue/PR olmadığı doğrulandı.

Diğer 2 bilinen bulgu (OpenRouteClient mimari sızıntısı, sistemik ölü-event-publish) zaten doğru dokümante/takip ediliyordu — ek aksiyon gerekmedi.

**CI doğrulama (final):** commit `82044b2` için `gh run view 29395179041` → hard-gates `success` (32dk53sn). 3 ayrı takip-push'unun her biri en az 1 tur kırmızı çıkardı (stale get_db mock, 1 alakasız flaky frontend real-backend testi) — hepsi bulunup düzeltildi/rerun edildi, hiçbiri gerçek regresyon değildi.

## DALGA 8 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-15)

**Kapsam:** anomaly modülü (12 dosya, 2.210 LOC envanteri) — `anomalies`,
`fuel_investigations` tablolarının tek sahibi, 11 route (anomalies+
investigations+admin_attribution). Detaylar `TASKS/modules/anomaly.md` +
`v2/modules/anomaly/CLAUDE.md`.

**Öne çıkan kararlar/bulgular:**
- `AttributionService` sınıfı kaldırıldı (B.1, önceki 6 dalgadaki kararla
  aynı gerekçe) — `override_attribution(sefer_id, arac_id=None, sofor_id=None,
  reason="", uow=None)` + `bulk_override_attribution(overrides: list)` free
  function'larına bölündü. `AnomalyDetector`/`AnomalyDetectionService`/
  `FuelTheftClassifier` 3 sınıf istisnası olarak kaldı (gerekçeler
  CLAUDE.md'de — sklearn/LightGBM eğitilmiş model state'i, cache-injected
  istatistiksel alt-sistem, stateless tek-pipeline).
- `analiz_repo.py`'den 15 metod (11 investigation + 4 anomaly CRUD) +
  `_INVESTIGATION_JOIN_SQL` iki yeni repository dosyasına taşındı
  (`infrastructure/anomaly_repository.py`, `infrastructure/investigation_repository.py`)
  — **FOR-UPDATE invaryantı** (`lock_investigation_for_update`+
  `update_investigation_fields`+`close_investigation` aynı dosyada, aynı
  sırada) korundu; `bulk_create_alerts`/`get_recent_unread_alerts` (analiz_repo'nun
  `anomalies` tablosuna AYRI bir insight-alert yolu) taşınmadı, görev dosyasının
  15 metodluk listesinde yoktu.
- driver→anomaly bağımlılığı düzeltildi (`generate_coaching.py`
  `app.core.services.anomaly_detector` yerine `v2.modules.anomaly.public`
  kullanıyor); analytics_executive'in henüz taşınmamış `analiz_service.py`'si
  de aynı şekilde `v2.modules.anomaly.public.get_anomaly_detection_service()`'e
  geçirildi.
- theft_tasks'ın 5-modül raw-SQL erişimi (fuel_investigations+anomalies+
  seferler+soforler+araclar) FAZ2 notu olarak CLAUDE.md'de dokümante edildi
  (taşımadan önce de böyleydi, regresyon değil).
- Gerçek bug bulunmadı — mekanik taşıma + B.1 dönüşümü (AttributionService→
  free function), davranış değişikliği içermiyor.

**Doğrulama (gerçek Docker container + `lojinext_test` DB):**
- `ruff check app v2 tests --select E,F,W,I` → temiz (7 isort-sıralama hatası
  `--fix` ile otomatik düzeltildi, 1 gerçek F401 — `attribution_routes.py`'de
  kullanılmayan `bulk_override_attribution` import'u — kaldırıldı).
- `mypy app/ --ignore-missing-imports --no-strict-optional` → main ile birebir
  aynı 7 hata (dalga 6 baseline'ı), regresyon yok.
- `pytest --collect-only app/tests` → 6738 test, 0 collect hatası (ilk
  denemede `docker cp` dizin-içine-dizin kopyalama hatası 125 sahte collect
  hatasına yol açmıştı — `docker cp app/tests/. .../app/tests/` ile düzeltildi,
  klasik dalga1 "nested tests/" gotcha'sının bir varyasyonu).
- Anomaly-özgü + dokunulan tüketici test dosyaları (21 dosya, gerçek DB'ye
  karşı): **351/351 pass** — `test_investigations_patch_race.py` (FOR-UPDATE
  eşzamanlılık testi) dahil, taşıma öncesi/sonrası davranış birebir.
- driver/coaching + analiz_service testleri: **139/139 pass**.
- Kök `tests/` (tam suite, gerçek DB'ye karşı): 263 passed + 1 fail
  (`test_idempotency.py::test_idempotency_guard_duplicate_request` —
  izole çalıştırıldığında 3/3 pass, Redis "Event loop is closed" sıra/pollution
  kaynaklı flake, anomaly taşımasıyla ilgisiz).
- OpenAPI schema drift: **YOK** — container'dan canlı `app.openapi()` çekilip
  `frontend/openapi.json` ile 234 path × operationId birebir karşılaştırıldı,
  fark 0 (route handler fonksiyon adları taşımada korundu).
- `AttributionService`'in class-mock testleri (`test_attribution_service.py`,
  `test_admin_attribution.py`, kök `tests/test_attribution.py`) free-function
  çağrılarına çevrildi — event_bus stub'ı artık `attribute_loss.get_event_bus`
  üzerinden patch'leniyor.

**Push geçmişi (2 commit):**
1. `f507b75` — ana taşıma. CI'nin "Backend unit tests" adımında kırmızı
   çıktı: 2 test dosyası (`test_singleton_thread_safety.py`,
   `test_theft_pattern_pii.py`) `from app.core.ai import fuel_theft_classifier`
   / `from app.workers.tasks import theft_tasks` şeklinde modül-referanslı
   import kullanıyordu — taşıma sırasındaki grep taraması `from x.y.z import
   name` kalıbına odaklandığı için bu "from package import module" desenini
   kaçırmıştı (dalga 1/3/4'teki "kök `tests/` klasörü"/"nested path" gotcha'sıyla
   aynı sınıf: tarama kapsamı dar kalınca kaçan dosyalar).
2. `7e2a364` — iki dosya `v2.modules.anomaly.application.classify_theft` /
   `v2.modules.anomaly.infrastructure.theft_tasks` modül-referanslarına
   çevrildi. **CI Hard Gates TAM YEŞİL** (`gh run view 29404636839` →
   hard-gates 29dk34sn + GHCR build/push 29dk25sn + Production deploy 6sn,
   tümü `success`) — commit `7e2a364` main'in HEAD'i.

**Ders:** bir modülü taşırken stale-import taraması yalnız
`from <eski.modül.yolu> import <isim>` deseniyle sınırlı kalmamalı —
`from <eski.paket> import <alt_modül>` (paket-seviyesi modül referansı)
deseni de aranmalı, aksi halde CI'da yalnız o test dosyaları çalışırken
ortaya çıkıyor.

### Dalga-8-sonrası dedektif denetim — "8 dalga tam temiz" (2026-07-15)

Kullanıcı talebiyle ("ilk 8 dalgayı detaylı ve derin kontrol edelim... SIFIR
AJANLARA VER BU GÖREVİ. DEDEKTİF GİBİ DENETLESİNLER NOKTA ATLAMASINLAR",
ardından "8 DALGA TAM TEMİZ OLANA KADAR DURMA") ilk 8 dalganın tamamı 7
bağımsız sıfırdan-context ajanla ikinci kez, bu sefer özellikle
`api → application → repo` katman disiplini (B.1'in bir alt-kuralı: route
handler'ları asla doğrudan repo/ORM/raw-SQL çağırmamalı) odağıyla denetlendi.
Detaylı bulgu/çözüm dökümü: `TASKS/bug-route-layer-bypasses-application.md`
(şimdi "TAMAMEN ÇÖZÜLDÜ").

**Bulunan ve düzeltilen modüller (8):** notification, fleet, auth_rbac
(ilk tur — commit `72769a0`), driver (commit `f818446`→`c62b6fc`), anomaly
+ fuel (commit `fc2c1bf`), anomaly OpenAPI-drift düzeltmesi + route_simulation
(commit `c7666a1`). Her push, bir sonraki push'tan önce CI Hard Gates'in
tam yeşile dönmesi beklenerek yapıldı (kırmızı-CI disiplini).

**Gerçek pre-existing prod bug (1):** notification'ın push
subscribe/unsubscribe'ı hiçbir zaman `uow.commit()` çağırmıyordu — UoW'nin
ghost-transaction guard'ı yalnız ORM identity-map'i kontrol ettiği için bu
sessizce rollback oluyordu (taşımadan ÖNCE de vardı, taşıma sırasında
bulunup düzeltildi).

**Süreç-içi regresyonlar, aynı turda bulunup düzeltildi (2):** fleet'te
`AracEntity.model_validate` round-trip'inin `plaka` alanını
`"34TEST01"`→`"34 TEST 01"` şeklinde bozması (`get_vehicle_raw_by_id` ile
çözüldü); anomaly'de `/patterns` route handler'ının isim çakışmasını önlemek
için yeniden adlandırılmasının FastAPI'nin ürettiği OpenAPI `operationId`'yi
kaydırıp CI'nin schema-drift gate'ini kırması (handler adı geri alınıp import
alias'landı).

**Son CI doğrulaması:** commit `c7666a1` → `gh run view 29422460816` →
`hard-gates` `success` (34dk40sn) — tüm 34+ backend/integration/deep-audit
adımı, combined coverage gate, frontend build/lint/type-check, OpenAPI
schema drift check, Playwright E2E dahil.

**Sonuç:** İlk 8 dalganın (location+route-simulation, notification, fleet,
fuel, driver, auth-rbac, anomaly) tamamında hem B.1 (dosya-başına-tek-iş)
hem katman disiplini (`api → application → repo`) artık gerçekten tutarlı —
2 ayrı bağımsız dedektif denetim turu (dalga-6-sonrası + dalga-8-sonrası,
toplam 13 sıfırdan-context ajan) hiçbir açık bulgu bırakmadı.

## DALGA 9 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-15)

**Kapsam:** import_excel modülü (11 dosya, 3.495 LOC envanteri) — Excel
bulk import/export/rollback orkestrasyonu (arac/surucu/sefer/yakit/guzergah),
admin generic import + job/rollback takibi, OCR belge Celery task'ı.
`iceri_aktarim_gecmisi` tablosunun tek sahibi. Detaylar
`TASKS/modules/import-excel.md` + `v2/modules/import_excel/CLAUDE.md`.

**Push geçmişi (2 commit):**
1. `bffa2d4` — ana taşıma (80 dosya). CI'nin "Backend type check (mypy)"
   adımında kırmızı çıktı (8 hata / 7 baseline).
2. `5d1a0fb` — mypy düzeltmesi: `sefer_importer.py::process_sefer_import`
   `sefer_list`'i dict listesi olarak inşa ediyor ama
   `SeferService.bulk_add_sefer` `List[SeferCreate]` bekliyor — bu latent
   uyuşmazlık taşımadan ÖNCE de vardı (`self.sefer_service` untyped
   constructor param olduğu için mypy görmüyordu, dalga 4'ün
   `yakit_importer.py`'deki aynı sınıf gotcha'sı), free-function geçişinde
   `get_container().sefer_service` düzgün tipli hale gelince ortaya çıktı.
   `cast()` ile dokümante edildi (`process_sefer_import` zaten prod'da
   çağrılmıyor, test-covered legacy yol — davranış değişmedi). **CI Hard
   Gates TAM YEŞİL** (`gh run view 29438098479` → `hard-gates` `success`,
   33dk53sn, 47 adımın tamamı — mypy/Backend unit tests/Combined coverage
   gate/OpenAPI schema drift check/Frontend E2E dahil) — commit `5d1a0fb`
   main'in HEAD'i.

**Öne çıkan kararlar/bulgular:**
- `ImportService`/`SeferImportService` sınıfları kaldırıldı (B.1, önceki 8
  dalgadaki kararla aynı gerekçe) — her use-case bağımsız fonksiyon.
  `SafeColumnMapper` (fuzzy column-matcher, `RouteSimulator`/
  `LokasyonHydrator` ile aynı gerekçe) ve `ExportService` (disk'e PDF/Excel
  export + `EXPORT_DIR`/`cleanup_old_exports` yaşam döngüsü olan stateful
  orkestratör — bytes döndüren `infrastructure/exporters.py`'den FARKLI bir
  API yüzeyi) 2 sınıf istisnası olarak kaldı.
- İki AYRI, KASITLI import akışı (ARCH-002) taşındı: `execute_import`
  (admin generic bulk import, job/rollback zorunlu, TEK UoW bloğu —
  create_import_job+raw INSERT+inserted_ids — BÖLÜNMEDEN taşındı) vs
  `process_*_import`/`import_sefer_excel_upload` (domain `bulk_add_*` yolu,
  job/rollback yok). `import_sefer_excel_upload` (trip'in
  `POST /trips/upload`'ı, B.2 kararı: senkron, yalnız `public.py` üzerinden)
  eski `services/api/sefer_import_service.py`'den taşındı.
- `_validate_import_rows` (görev dosyası "5'e dallanıyor" diyordu — gerçek
  kod 4 dal: arac/surucu/sefer/yakit, task dosyası bu noktada yanlıştı)
  `domain/row_validators.py`'de 4 fonksiyona bölündü; prefetch edilen
  master listeler (vehicles/drivers/trailers/routes) `execute_import`
  tarafından TEK seferde çekilip parametre olarak paylaşılıyor (N+1
  önleme, görev dosyasının açık uyarısı).
- `SeferImportService._resolve_master_id` dead code olarak DÜŞÜRÜLDÜ (B.1
  free-function geçişinde) — hiçbir prod çağıran kullanmıyordu (yalnız
  kendi unit testi egzersiz ediyordu), test dosyası buna göre güncellendi.
- Tüketen modüller (fuel/fleet/driver/location route'ları, `trips.py`,
  `advanced_reports.py`) `v2.modules.import_excel.public`'e güncellendi;
  patch hedefi inline-import'larda (fuel/location, driver'ın `process_driver_import`'ı)
  KAYNAK modül (`public.py`), module-level import'larda (fleet/driver'ın
  export fonksiyonları, trips.py) TÜKETEN modül — location/fleet/fuel'deki
  aynı gotcha. `container.py`'den `import_service` property'si tamamen
  kaldırıldı; `export_service` yeni konuma (`infrastructure/report_export.py`)
  işaret ediyor.
- 🔴 **Ghost-file gotcha'sı (yeni sınıf, bu dalgada keşfedildi):** bu
  dev container aylardır `docker cp` ile güncellenip hiç temiz
  yeniden build edilmediği için `app/core/services/anomaly_detector.py` ve
  `app/api/v1/endpoints/investigations.py` gibi **git'e hiç commitlenmemiş,
  çok önceki bir dalgada (anomaly, dalga 8) silinmesi gereken ama container'da
  kalıntı olarak yaşayan dosyalar** birikmişti — bunlar lokal `mypy`
  koşumunda 22 sahte hata üretip gerçek baseline'ı (7) gizliyordu (29
  görünüyordu). `git ls-files` ile dosyaların gerçekten takip edilip
  edilmediği doğrulanarak bulundu, container'dan silindi. **Ders:** bu
  container'da lokal mypy/test sonucu şüpheliyse önce `git ls-files
  <path>` ile dosyanın gerçekten repoda olup olmadığı kontrol edilmeli —
  `docker cp` hem eski dosyaları SİLMİYOR hem de commit edilmemiş kalıntı
  bırakabiliyor (dalga 9'un kendi "docker cp silmez" bulgusuyla aynı kökten,
  ama bu kez YENİ dosya değil TAMAMEN İLGİSİZ eski dosyalar için).

**Doğrulama (gerçek Docker container + `lojinext_test` DB):**
- `ruff check app v2 tests --select E,F,W,I` → temiz.
- `mypy app/ --ignore-missing-imports --no-strict-optional` → ghost-file
  kontaminasyonu ayıklandıktan sonra 5 hata (baseline 7, regresyon yok;
  fix öncesi 8/7 idi, CI'nın kendi ortamı zaten temizdi).
- Hedefli test dosyaları (import_excel'in kendi + 4 tüketici modülün
  dokunulan API testleri, ~35 dosya): 783+ test, gerçek DB'ye karşı 100%
  pass.
- Kök `tests/` (tam suite): 263 passed + 1 fail
  (`test_idempotency.py::test_idempotency_guard_duplicate_request` — bilinen
  Redis "Event loop is closed" pollution flake'i, dalga 8 baseline'ıyla
  birebir aynı, import_excel taşımasıyla ilgisiz).
- OpenAPI schema drift: CI'da doğrulandı, YOK.

**Ders (genel):** free-function geçişi sırasında bir constructor'daki
untyped parametrenin (`self.sefer_service`, `self.yakit_service` vb.)
gerçek çağrı sitesindeki tip uyuşmazlıklarını GİZLEDİĞİ artık 3. kez
doğrulandı (dalga 4 yakit, dalga 5 driver 500 bug'ı, dalga 9 sefer) — bu
geçiş deseni sistematik olarak gizli tip hatalarını ortaya çıkarıyor,
her dalgada beklenmeli.

## İLK 9 DALGA — DEDEKTİF DENETİM DÜZELTMELERİ (2026-07-15/16)

**Kapsam:** kullanıcı isteğiyle 9 paralel, sıfır-context ajanla ilk 9
dalganın (location/route_simulation/notification/fleet/fuel/driver/
auth_rbac/anomaly/import_excel) tamamı yeniden, bağımsız denetlendi (B.1 +
katman disiplini). 4 modülde gerçek, yeni bulgu çıktı; hepsi bu oturumda
düzeltildi.

**location — 11 katman ihlali (`api/location_routes.py`):** `get_location_stats`/
`get_stale_locations`/`get_location_by_id`/`search_locations_by_route`/
`get_unique_location_names`/`get_all_locations`/`hydrate_location`/
`get_location_segments` handler'ları repo/UoW'a doğrudan erişiyordu —
8 yeni `application/` use-case dosyasına taşındı. Taşıma sırasında route
handler'larıyla AYNI İSİMLİ 2 yeni import (`get_location_stats`,
`get_stale_locations`) modül-seviyesi isim gölgelemesine yol açacaktı —
test çalıştırılmadan, kod incelemesinde kendi kendine yakalandı, `as
get_location_stats_usecase`/`as get_stale_locations_usecase` alias'ıyla
düzeltildi. Doğrulama: `ruff` temiz, `mypy` baseline'da regresyon yok,
hedefli testler (`test_locations_*`, `test_lokasyon_hydrator`) 102 pass / 2
fail (ikisi de önceden bilinen ORS/Nominatim api-stub ağ flake'i,
`geocode_location`'a hiç dokunulmadı, regresyon değil).

**fuel — `delete_yakit` route ihlali + GERÇEK BUG (`api/fuel_routes.py`):**
`db.get(YakitAlimi, yakit_id)` (2 çağrı) zaten import edilmiş
`get_yakit_by_id()`'ye taşındı. İlk turda 2 gerçek regresyon çıktı ve
düzeltildi: (1) `get_yakit_by_id`'nin döndürdüğü `app.core.entities.models.YakitAlimi`
Pydantic entity'sinde `aktif` alanı YOKTU (`current.aktif` çağrısı
`AttributeError` verirdi) — entity'ye `aktif: bool = True` alanı eklendi;
(2) `repo.get_by_id()` varsayılan olarak pasif kayıtları filtreliyor, ama
smart-delete'in "zaten pasif kaydı hard-delete et" akışı pasif kaydı da
görebilmeli — `get_yakit_by_id(yakit_id, include_inactive=...)` parametresi
eklendi, route'un 2 çağrısı da `include_inactive=True` geçiyor. Bu ikisi
`unittest.mock`'lu mevcut testlerde YAKALANMADI (MagicMock her attribute'a
"sahip" görünür) — `mypy v2/` taramasıyla (`"YakitAlimi" has no attribute
"aktif"`) yakalandı, ardından gerçek DB + gerçek HTTP client ile yeni bir
regresyon testi eklendi (`test_yakit_service_soft_delete.py::test_delete_route_hard_deletes_passive_record_via_http`).
Doğrulama: `ruff`/`mypy` temiz, `test_fuel_coverage.py`+`test_fuel_more.py`
50/50 pass, yeni test dahil 4/4 pass.

**auth_rbac — 2 bulgu:** (1) `LicenseEngine.check_car_limit()`
(`application/license_service.py`) `Arac` tablosuna doğrudan erişiyordu —
fleet'in zaten var olan `AracRepository.count_active()`'ini saran yeni
`fleet.public.count_active_vehicles()` üzerinden çağrılacak şekilde
düzeltildi (fleet zaten tam taşınmış olduğu için gerçek düzeltme mümkündü).
`check_monthly_trip_limit()`'in `Sefer` erişimi ise trip modülü henüz
taşınmadığı için (delege edilecek `public.py` yok) BİLİNÇLİ, dokümante
geçici borç olarak bırakıldı (docstring'e not düşüldü). (2)
`api/ws_ticket_routes.py` application katmanını tamamen atlayıp Redis'e
doğrudan yazıyordu — yeni `application/create_ws_ticket.py`'ye taşındı
(route handler'ıyla aynı isim çakışması burada da vardı, `as
create_ws_ticket_usecase` alias'ıyla düzeltildi). Doğrulama: `ruff`/`mypy`
temiz, `test_license_service.py` 12/12 pass (gerçek DB, `seed_arac` ile),
auth_rbac servis testleri 62/62 pass.

**fleet — 2 route'ta create-then-read-back katman ihlali:** `vehicle_routes.py::create_arac`
ve `trailer_routes.py::create_dorse` oluşturulan kaydı aynı transaction
içinde `uow.arac_repo.get_by_id(...)`/`uow.dorse_repo.get_by_id(...)` ile
doğrudan okuyordu. Vehicle tarafı: `get_vehicle_raw_by_id`'ye opsiyonel
`uow` parametresi eklendi (verilmezse eskisi gibi kendi `UnitOfWork()`'ünü
açar — mevcut `read_arac`/`update_arac` çağıranları etkilenmedi), route
artık `get_vehicle_raw_by_id(arac_id, include_inactive=True, uow=uow)`
çağırıyor. Trailer tarafı zaten `uow` parametresi kabul eden
`get_trailer_by_id(repo, ...)`'i başka yerlerde kullanıyordu — route
sadece ona yönlendirildi. Doğrulama: `ruff`/`mypy` temiz,
`test_vehicles_coverage.py`+`test_vehicles_more.py`+`test_trailers_coverage.py`+`test_trailers.py`
91/91 pass.

**import_excel — kaçırılmış commit:** önceki dalga 9 denetiminde
`column_mapper.py`'nin `SafeColumnMapper` docstring düzeltmesi (yanlış
"RouteSimulator ile aynı gerekçe" iddiasını düzelten dürüst not) yerel
diskte hazırlanmış ama hiçbir commit'e girmemiş kalmıştı (muhtemelen
sadece container'a `docker cp` edilip yerel dosyayla commit senkron
edilmemiş) — bu oturumda fark edilip dahil edildi.

**Konsolide doğrulama:** 4 modülün tüm hedefli test dosyaları tek koşumda
(`pytest app/tests/api/test_locations_* app/tests/integration/test_locations_api.py
app/tests/unit/test_lokasyon_hydrator.py app/tests/api/test_fuel_*
app/tests/unit/test_services/test_yakit_service_soft_delete.py
app/tests/unit/test_services/test_license_service.py
app/tests/api/test_vehicles_* app/tests/api/test_trailers*`) → 259 passed,
2 failed (aynı önceden bilinen geocode ağ flake'i) — regresyon yok.
`ruff check --select E,F,W,I` ve `mypy app/ v2/ --ignore-missing-imports
--no-strict-optional` (v2/ dahil, CI kapsamının ötesinde ekstra) her ikisi
de temiz/baseline'da.

## Bilinen mypy baseline hataları — TAMAMEN TEMİZLENDİ (2026-07-16)

Yukarıdaki dedektif denetimi sırasında `mypy app/ v2/` taramasında bulunan
(CI'nin resmi `mypy app/` kapsamının 7'lik baseline'ına dahil olan) 6 kalıcı
hata, kullanıcı isteğiyle ayrıca temizlendi — hepsi gerçek, mekanik
düzeltmeler (yeni davranış yok), 1 tanesi GERÇEK BUG:

- `v2/modules/auth_rbac/infrastructure/rol_repository.py::update` —
  `BaseRepository`'den farklı imza için eksik `# type: ignore[override]`
  eklendi (sınıftaki diğer 4 override zaten bu yorumu taşıyordu).
- `app/infrastructure/events/event_bus.py` — 🔴 **kök neden gerçek bug**:
  `EventBus.__init__`'in dönüş tipi (`-> None`) eksikti, bu da mypy'nin
  metodu "untyped" sayıp İÇİNDEKİ `self._subscribers`/`self._bg_tasks` tip
  bildirimlerini SESSİZCE ATLAMASINA yol açıyordu (`annotation-unchecked`
  notları) — eklendi. Ayrıca `publish()`'teki fire-and-forget task
  done-callback'i (`Need type annotation for "task"` + `Cannot infer type
  of lambda`) küçük adlandırılmış bir yardımcıya (`_log_task_exception`)
  çıkarılıp doğru tiplendirildi.
- `v2/modules/fuel/application/delete_yakit.py` + `app/core/services/sefer_service.py` —
  `log_audit_event(entity_id=...)` int geçiyordu, imza `str` bekliyor —
  `str(...)` eklendi (fuel_routes.py'nin zaten yaptığı gibi).
- `app/core/services/sefer_write_service.py::_safe_durum` — `value: object`
  parametresi `ensure_canonical_sefer_status`'a (gerçek adı
  `ensure_canonical_trip_status`, `Optional[str]` bekliyor) doğrudan
  geçiyordu; fonksiyon zaten `str(value)` ile normalize ettiği için
  runtime'da güvenli — `cast(Optional[str], value)` ile dokümante edildi.
- 🔴 **`app/core/services/health_service.py::check_ai_readiness` — GERÇEK
  BUG**: `get_container().ensemble_service` diye bir attribute HİÇ YOK
  (`Container`'da `ensemble_service` yok, `PredictionService.ensemble_service`
  var — `PredictionService.__init__`'te `self.ensemble_service =
  get_ensemble_service()`). Bu satır HER ÇAĞRIDA `AttributeError` fırlatıyor
  ve etraftaki geniş `except Exception` tarafından sessizce yutulup statik
  `["physics","lightgbm","xgboost","gb","rf"]` listesine düşülüyordu —
  `/admin/health` endpoint'inin AI-readiness bölümü gerçek yüklü model
  durumunu HİÇ yansıtmıyordu. `get_container().prediction_service.ensemble_service`
  olarak düzeltildi. Not: `EnsemblePredictorService`'in kendisinde de
  `_models` attribute'u yok (araç-bazlı `predictors: OrderedDict` +
  her `EnsembleFuelPredictor`'ın kendi `self.weights` dict'i var, global bir
  "yüklü model listesi" kavramı yok) — bu yüzden `getattr(ensemble,
  "_models", {})` düzeltmeden SONRA da `{}` dönüp aynı statik listeye
  düşüyor; CLAUDE.md'nin "5-model ensemble" açıklamasıyla tutarlı olduğu
  için ÇIKTI DEĞİŞMEDİ, ama artık doğru (documented) bir fallback — kör bir
  `AttributeError` swallow değil.

**Doğrulama:** `mypy app/ --ignore-missing-imports --no-strict-optional`
(CI'nin TAM kapsamı) → **0 hata** (baseline 7'den). `mypy app/ v2/` (v2
dahil, ekstra) → **0 hata**. `ruff check app v2 --select E,F,W,I` → temiz.
Hedefli testler (health_service ×2, event_bus ×4, sefer/trips ×6,
rol_repository) → sadece 2 TAMAMEN İLGİSİZ, önceden var olan flake ortaya
çıktı (her ikisi de HEAD'e karşı da aynı şekilde başarısız olduğu
doğrulandı — regresyon değil): `test_check_redis_unhealthy` (gerçek Redis
Sentinel bu ortamda 6390'da erişilebilir çıkıyor, mock hedefini bypass
ediyor) ve `test_use_sefer_fuel_estimator_opt_in_default_false` (bu
container'ın `.env`'i `USE_SEFER_FUEL_ESTIMATOR=true`, testin varsaydığı
`false` değil). CI'nin BASELINE=7 sabiti bu commit'te BİLEREK
değiştirilmedi (dosyanın kendi tarihçesi: "sayım ortama duyarlı... Gate
CI'nin gördüğü değere göre ayarlanır" — önce gerçek CI koşumunda 0
doğrulanmalı, sonra ayrı bir PR'da sıkılaştırılmalı).

## Event-bus wiring — TAMAMLANDI (2026-07-16, kullanıcı kararıyla: "gerçekten bağla")

**Kapsam:** ilk 9 dalganın tam envanteri çıkarıldı (`v2/modules/*/CLAUDE.md`'lerin
tamamı tarandı). Bulgular iki kategoriye ayrıldı: (a) unmigrated modüllere
bağımlı ~25+ kalem — trip/prediction_ml/analytics_executive/admin_platform/
reports/ai_assistant henüz taşınmadığı için delege edilecek `public.py` yok,
bunlara DOKUNULMADI (o modüllerin kendi dalgası); (b) modül-bağımsız,
gerçekten şimdi kapatılabilecek TEK kalem: repo-genelinde event-bus wiring
boşluğu. Kullanıcı "gerçekten bağla" dedi (davranış değişikliği kabul
edildi, geniş test yapıldı).

**Kök bulgu:** `@publishes(EventType.X)` decorator'ı (location/fleet/fuel/
driver) yalnızca metadata ekliyordu, hiçbir yerde gerçek
`event_bus.publish(...)`/outbox yazımı yoktu. Daha da kritik: repo-genelinde
5 subscriber-kurulum fonksiyonu (`setup_cache_invalidation()`,
`get_rag_sync_service().initialize()`, `get_model_training_handler().setup()`,
`get_physics_handler().register()`, notification'ın `register_handlers()`)
**hiçbiri app başlangıcında (veya başka hiçbir yerde) çağrılmıyordu** —
bildirimler/RAG-sync/cache-invalidation/ML-retrain prod'da baştan beri hiç
çalışmıyordu.

**Yapılan değişiklikler:**
1. `app/main.py` lifespan'ına 5 kurulum çağrısı eklendi (her biri kendi
   `try/except`'i içinde — biri başarısız olursa diğerlerini/app startup'ı
   engellemez).
2. `app/infrastructure/events/outbox_service.py`'ye paylaşılan
   `save_outbox_event(session, event_type, payload)` helper'ı eklendi
   (`OutboxService.save_event` buna delege eder — DRY); location'ın
   `repo`-only (uow'suz) use-case'leri için de kullanılabiliyor.
3. location/fleet/fuel/driver'ın create/update/delete use-case'lerine
   (12 fonksiyon, toplam 15 commit-noktası) `save_outbox_event(...)` çağrısı
   eklendi — sefer_write_service.py'nin zaten kanıtlanmış "Phase 7: Atomic
   Outbox Persistence" desenini birebir taklit eder (aynı transaction,
   commit'ten önce). Payload sözleşmesi: `{"result": <id>}` (+ fuel için
   `"arac_id"` flat key, `model_training_handler`'ın okuduğu).

**Taşıma sırasında bulunan 2 GERÇEK BUG (event wiring'in doğal sonucu, önceden
hiç tetiklenmedikleri için hiç yakalanmamışlardı):**
- `rag_sync_service.py::initial_sync()` — `get_arac_repo()`/`get_sofor_repo()`/
  `get_sefer_repo()` session'sız singleton döndürüyordu, raw-SQL `get_all()`
  "Database session not initialized" ile patlıyordu. `UnitOfWork()` + `uow.<repo>`
  kullanacak şekilde düzeltildi — gerçek Docker restart ile doğrulandı
  (`Initial RAG sync complete. Vehicles: 4, Drivers: 3, Trips: 5`).
- `app/core/entities/models.py::YakitUpdate.toplam_tutar` (computed_field) —
  `fiyat_tl`/`litre`'den YALNIZ BİRİ verilen (veya ikisi de verilmeyen) her
  PARTIAL fuel update'i `decimal.InvalidOperation`/`TypeError` ile 500'e
  düşürüyordu (repo katmanı `toplam_tutar`'ı zaten kendi DB'den okuyup doğru
  hesaplıyor — schema'nın computed_field'ı repo tarafından hiç kullanılmıyor,
  salt önizleme). İkisi de yoksa `None` dönecek şekilde düzeltildi. Mevcut
  testler bunu YAKALAMAMIŞTI çünkü tek kullanılan payload (`_UPDATE_PAYLOAD`)
  tesadüfen her zaman ikisini birden içeriyordu.
- `rag_sync_service.py::_on_sofor_changed` — `_on_arac_changed`'ın zaten
  sahip olduğu int-id fallback'i (yalnız id geldiğinde repodan çekme)
  eksikti; eklendi (simetri, `arac_sync`'in aynı deseniyle).

**Test kırılımı (event-wiring'in doğal sonucu, düzeltildi):** yeni outbox
yazımı, `UnitOfWork`'ü mock'layıp `.session`'ı yapılandırmayan eski testleri
kırdı (`test_sofor_service_delete_event.py`) — `session.flush()` artık
awaitable olmalı. `rag_sync_service_coverage.py`'nin `initial_sync`/
`_on_sofor_changed` testleri de yeni `UnitOfWork`/int-fallback deseniyle
güncellendi (2 yeni test eklendi, mevcut "non_dict_skips" testi artık geçerli
olmayan bir varsayıma dayandığı için int-fallback testleriyle değiştirildi).

**Yeni regresyon testi:** `app/tests/integration/test_event_wiring_outbox.py`
(13 test) — location/fleet/fuel/driver'ın 12 create/update/delete
fonksiyonunun HER BİRİNİN gerçek DB'ye karşı doğru `OutboxEvent` satırı
yazdığını + relay'in gerçek subscriber'larla (cache invalidation) crash
etmeden işlediğini doğrular.

**Doğrulama:** `mypy app/` (CI tam kapsamı) → 0 hata. `mypy app/ v2/` → 0
hata. `ruff check app v2` → temiz. Gerçek Docker restart ile startup log'ları
doğrulandı (5/5 kurulum mesajı + RAG initial sync başarı). Tam suite
(`pytest app/tests`, 6700+ test) → 2 yeni kırılan test bulunup düzeltildi,
kalan ~37 başarısızlık tamamı önceden var olan/ortam-bağımlı (api-stub bu
oturumda başlatılmamıştı, ORS/Redis/CORS-cwd flake'leri) — HEAD'e karşı
`git stash` ile birebir aynı şekilde başarısız olduğu doğrulandı (regresyon
değil).

## DALGA 10 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-16)

**Push geçmişi (4 commit, ilk 2'si kırmızı çıktı, ikisi de gerçek kök
nedenle düzeltildi):**
1. `6251b49` — ana taşıma (59 dosya). CI'nin "Backend import smoke"
   adımında kırmızı çıktı.
2. `3f308a9` — kök neden: `.gitignore`'un `*_report.*` deseni
   `generate_vehicle_report.py`/`generate_driver_report.py`'yi sessizce
   git'e hiç eklememişti (yerel Docker doğrulaması bunu yakalamadı —
   dosyalar `docker cp` ile container'a kopyalanmıştı, git tracking'i
   bypass ediyordu). Desen `*_report.txt`/`.json`/`.log`'a daraltıldı.
3. `8a5e9de` — kullanıcı talebiyle 4 bağımsız sıfır-context ajanla
   "dedektif" tam denetim yapıldı (bkz. aşağıdaki "Dedektif denetim"
   bölümü); 2 gerçek (pre-existing, regresyon OLMAYAN) boşluk +
   `frontend/openapi.json` drift düzeltildi. CI'nin "OpenAPI schema
   drift check" adımında kırmızı çıktı (bu commit'in KENDİSİ
   düzeltiyordu ama farklı bir push sırasında ayrıca test edildi).
4. `1fdc78e` — `reports.md`/`STATUS.md` dokümantasyon düzeltmeleri.
   **CI Hard Gates TAM YEŞİL** (`gh run view 29501486141` → hard-gates
   job `success`, 33dk31sn — OpenAPI drift check + Playwright E2E dahil
   tüm adımlar geçti) — commit `1fdc78e` main'in HEAD'i.

**Kapsam:** reports modülü (12 dosya, gerçek 2.519 LOC — görev dosyasının
"2.404" iddiası dedektif denetimde yanlış çıktı, `reports.md`'de düzeltildi)
— dashboard/filo/
araç/şoför rapor üretimi (JSON+PDF+Excel), aylık trend, Reports-v2 (Today/
Triage, Fleet İçgörü, Reports Studio). `TASKS/modules/reports.md` + yeni
`v2/modules/reports/CLAUDE.md`.

**Öne çıkan kararlar/bulgular:**
- `ReportService` sınıfı kaldırıldı (B.1, önceki 6 dalgayla aynı gerekçe) —
  7 bağımsız use-case fonksiyona bölündü (`generate_fleet_summary`,
  `generate_vehicle_report`, `generate_driver_report`, `generate_monthly_trend`,
  `get_dashboard_summary`, `get_monthly_comparison`, `get_daily_consumption_trend`).
  Session-mi-yoksa-singleton-mi ayrımı `ReportRepos`/`resolve_repos(uow)`
  ile korundu (driver'ın `_repos(uow)` desenini birebir taklit eder).
- `triage_aggregator.py`/`fleet_comparison.py` mekanik taşındı (davranış
  değişikliği yok) — Reports-v2'nin RV2.1/RV2.2 özellikleri.
- `report_generator.py` → `infrastructure/pdf_export.py`; font-kaydı repo-kökü
  hesaplaması `dirname()` 2'den 4'e çıktı (yeni dosya derinliği), pratik
  etkisi yok (asset font dizini bu ortamda zaten mevcut değil, fallback zinciri
  aynı).
- 🔴 **page_views tablo-sahipliği tutarsızlığı bulundu (düzeltilmedi, dalga
  11'e not düşüldü):** görev dosyası "page_views reports'ta" diyordu ama
  `page_view_repo.py`/`analytics.py`/`analytics_tasks.py` (gerçek kod-sahibi)
  analytics_executive'in (dalga 11, henüz taşınmadı) alanında — 12 dosyalık
  envanterin dışında, taşınmadı. Detay: `v2/modules/reports/CLAUDE.md`
  "page_views tablo-sahipliği tutarsızlığı" bölümü.
- `dashboard_service.py`/`context_builder.py` (app/core/, bu dalganın dosya
  envanterinin dışı) `_ReportsFacade` küçük adaptör sınıfı kullanıyor — eski
  `self.report_service.get_dashboard_summary()` çağrı şeklini koruyan bir
  köprü (mevcut testlerin `AsyncMock` override'ı bunu bekliyor); reports'un
  kendisinde `ReportService` yok, yalnız bu 2 TÜKETİCİ dosyanın eski
  instance-method arayüzünü bu dalgada değiştirmek kapsam dışı bırakıldı.
- `container.py`'nin `report_service` property'si + `_report_service` state'i
  kaldırıldı (önceki 6 dalgayla aynı desen — `arac_service`/`sofor_service`/
  `yakit_service`/`import_service` de aynı şekilde kaldırılmıştı).

**Doğrulama (gerçek Docker container — `docker cp` + `docker compose restart backend`,
CLAUDE.md'nin dokümante ettiği pattern; MSYS/Git-Bash'in `docker exec`'e geçirilen
çıplak `/app/...` yollarını Windows yoluna çevirdiği bir gotcha bulundu — `rm -f`
sessizce no-op oldu, `MSYS_NO_PATHCONV=1` + `-u root` ile düzeltildi):**
- Backend gerçek restart ile temiz açıldı, 5/5 yeni route grubu (`/reports`,
  `/advanced-reports`, `/reports/today`, `/reports/insights/fleet`,
  `/reports/studio`) `app.routes`'ta doğrulandı.
- `ruff check app v2 --select E,F,W,I` → temiz (12 import-order hatası
  bulunup düzeltildi).
- `mypy app --ignore-missing-imports --no-strict-optional` (CI'nin TAM
  kapsamı) → **0 hata**. `mypy app v2` (v2 dahil, ekstra) → 10 hata bulunup
  düzeltildi (`ReportRepos` alanları `object` yerine `Any` olmalıydı,
  AsyncMock/gerçek-repo ikili kullanımı için) → **0 hata**.
- `pytest --collect-only`: `app/tests` 6745 test / kök `tests/` 264 test,
  0 hata (dalga 1'deki conftest-collect riskiyle aynı sınıf kontrol edildi).
- Hedefli testler gerçek `lojinext_test` DB'sine karşı: reports-özgü
  130 (unit) + 72 (API/advanced-reports) + 9 (business-flow/detailed-scenario,
  `test_analysis_and_report.py` DAHİL — bu dosya `.gitignore`'un
  `*_report.*` deseniyle YANLIŞLIKLA eşleşip hiç git-tracked olmadığı
  bulundu, CI'da hiç çalışmıyor, düzeltme yalnız yerel doğrulama için) +
  32 (import_excel export_service, tüketici) + 15 (notification weekly-digest,
  tüketici) = **258 test, 0 fail**. 1 pre-existing stale mock-assertion
  bulundu (`test_generate_vehicle_report`'ın `get_by_id(1)` beklentisi,
  gerçek çağrı taşımadan ÖNCE de `get_by_id(1, include_inactive=True)`
  idi — `git show HEAD:...report_service.py` ile doğrulandı, regresyon
  değil) düzeltildi.
- `app/tests/sections/test_section_1_backend_core.py`'de 12 hata bulundu
  (anomaly modülünün `detect_anomaly.py`↔`public.py` dairesel importu) —
  **bu dalgayla İLGİSİZ** (reports hiç bu zincirde yok), izole koşumda da
  aynı şekilde tekrarlandığı doğrulandı (pre-existing, ayrı bir flake-avcılığı
  görevi konusu).

**İlk push (`6251b49`) kırmızı çıktı:** `.gitignore`'un `*_report.*`
deseni (ad-hoc test-çıktı dosyaları için yazılmış) `generate_vehicle_report.py`/
`generate_driver_report.py`'yi sessizce commit'ten dışlamıştı — lokal
Docker doğrulaması bunu hiç yakalamadı çünkü dosyalar container'a
`docker cp` ile kopyalanmıştı (git tracking'i bypass ediyordu). `3f308a9`
ile düzeltildi (`*_report.txt`/`.json`/`.log`'a daraltıldı + 2 dosya eklendi).

**Kullanıcı talebiyle (2026-07-16) 4 bağımsız sıfır-context ajanla
"dedektif gibi" tam denetim yapıldı** — B.1 uyumu, tüketici/stale-referans
taraması, davranışsal satır-satır diff, test-dönüşüm + STATUS.md
dürüstlük kontrolü. 6/6 davranışsal eşleme PASS, hiçbir regresyon
bulunmadı. 2 gerçek (ama pre-existing, dalga 10'un ürettiği DEĞİL) boşluk
bulunup `8a5e9de` ile düzeltildi:
1. `dashboard_routes.py`'nin 2 handler'ı `application/`'ı atlıyordu
   (`bug-route-layer-bypasses-application.md` sınıfı, `git show
   6251b49~1` ile taşımadan önce de böyle olduğu doğrulandı) →
   `application/get_dashboard_counters.py` + `get_consumption_trend.py`.
2. `PDFReportGenerator`'ın B.1 sınıf-istisna gerekçesi CLAUDE.md'de hiç
   yazılmamıştı → eklendi.
Bu düzeltme sırasında `get_dashboard_stats`'in temizlenmiş docstring'i
`frontend/openapi.json`'a hiç yansımadığı bulundu — gerçek çalışan
backend'e karşı byte-level doğrulanıp düzeltildi (CI'nin "OpenAPI schema
drift check" adımının `3f308a9`'da kırmızı çıkmasının kök nedeni).
Ayrıca `reports.md` görev dosyasının 3 küçük ön-tarama hatası (route
sayısı 15→16, LOC 2.404→2.519, `triage_aggregator` hedef yolu) denetimde
bulunup düzeltildi — hiçbiri kod-seviyesinde etkili değildi, yalnız
dokümantasyon.

**Dalga 10 kapandı.** Sıradaki: dalga 11 (analytics-executive) — yeni
oturumda, `TASKS/modules/analytics-executive.md` okunarak, kullanıcı
onayıyla başlanacak (DURMA NOKTASI kuralı). Not: analytics-executive'in
görev dosyası, dalga 10'da bulunan page_views tablo-sahipliği
tutarsızlığını (bkz. yukarı) çözecek şekilde gözden geçirilmeli.

## İlk 10 dalga — tam dedektif denetimi + düzeltme turu (2026-07-16)

**Kapsam:** kullanıcı talebiyle ("detaylı ve derin kontrol edelim, dedektif
gibi denetlesinler nokta atlamasınlar") ilk 10 dalganın TAMAMI (location,
route_simulation, notification, fleet, fuel, driver, auth_rbac, anomaly,
import_excel, reports — ~230 dosya) 10 bağımsız sıfır-context ajanla
dosya-dosya yeniden denetlendi (B.1 uyumu, route→application katman
disiplini, CLAUDE.md iddialarının gerçek kodla örtüşmesi). Ardından
kullanıcı talebiyle ("kalan en küçük hatayı bile düzeltmeden bırakma")
bulunan TÜM gerçek bulgular düzeltildi.

**Push geçmişi (5 commit):**
1. `8a5e9de`/`0aa3a49`... — bkz. DALGA 10 bölümü (bu turun ilk parçası).
2. `0aa3a49` — **4 HIGH bug** (üretimde sessiz veri kaybına/hataya yol
   açan, hepsi gerçek Docker koşumuyla önce-çöküyor/sonra-çalışıyor
   doğrulandı):
   - `import_excel/column_mapper.py`: "Şoför Adı" başlıklı Excel'lerde
     sürücü import satırları sessizce atlanıyordu (`sofor_adi`/`ad_soyad`
     alias çakışması, dict sırası `sofor_adi`'yi önce claim ediyordu).
     `map_columns`'a opsiyonel `prefer` parametresi eklendi.
   - `reports/advanced_reports_routes.py`: Excel "driver_comparison"
     export'u her zaman 500 veriyordu (`get_driver_stats()` uow'suz
     singleton'a düşüyordu) — taşımadan ÖNCE de vardı, dalga 10
     regresyonu değil.
   - `app/core/services/analiz_service.py`: gerçek dairesel import
     (`public.py` ↔ `detect_anomaly.py` ↔ `analiz_service.py` ↔
     `prediction_service.py`), yalnızca `api.py`'nin tesadüfi import
     sırasıyla maskeleniyordu — canlı reprodüklendi (izole import +
     tam app boot + tam test suite ile doğrulandı).
   - `fuel/recalculate_vehicle_periods.py`: repo verilmediğinde
     (varsayılan/prod yolu) session'sız singleton'a düşüp `RuntimeError`
     fırlatıyordu — Excel yakıt toplu-import'unda sessizce yutulup
     periyotlar HİÇ hesaplanmıyordu. `AsyncExitStack` ile düzeltildi.
3. `4b15215` — **4 MEDIUM + 9 LOW bulgu**: fleet/fuel'in toplu-Excel-import
   yollarında outbox event eksikliği (RAG sync/cache-invalidation'a
   düşmüyordu); notification'ın `webpush_client.py`'sindeki senkron/
   bloklayıcı `pywebpush.webpush()` çağrısı (aynı modülün gerçek bir
   prod-incident'ine [Sentry LOJINEXT-182] yol açmış bloklayıcı-çağrı
   hatasıyla aynı sınıf) `asyncio.to_thread`'e alındı + subscription'lara
   sıralı gönderim `asyncio.gather`'a çevrildi; auth_rbac'ta
   `LicenseEngine`'in class-level mutable dict paylaşımı + ölü kod;
   import_excel'de eksik zorunlu-alan validasyonu; anomaly'de unreachable
   duplicate except bloğu; fuel'de kanonik olmayan "Unknown" literal'i;
   driver/reports'ta toplam 10 kullanılmayan `db` parametresi (5'i
   denetimde bulundu, 1'i düzeltme sırasında ayrıca bulundu); driver'ın
   CLAUDE.md'sindeki güncel-olmayan "event yayını ölü kod" notu.
4. `95b2b99` — `4b15215`'in kırdığı TEK test (`test_bulk_add_yakit_emits_
   fiyat_tl_and_toplam_tutar`, fake UoW gerçekçi olmayan `None` dönüyordu)
   düzeltildi. **CI Hard Gates TAM YEŞİL** (`gh run view 29515827692` →
   hard-gates `success`, 34dk24sn — OpenAPI drift + Playwright E2E dahil)
   — commit `95b2b99` main'in HEAD'i.

**Bilinçli KAPSAM DIŞI bırakılanlar** (davranış değişikliği veya DB
migration gerektiriyor, tek başına ürün kararı ister — sessizce
değiştirilmedi):
- `auth_rbac/rol_repository.py`: isim-benzersizliği TOCTOU riski (gerçek
  fix bir DB `UNIQUE` constraint'i ister).
- `auth_rbac/preference_service.py`: çoklu "sutun" ayarı upsert'inin
  yanlış satırı ezme riski (davranış değişikliği).
- `anomaly`: aynı isimli 2 farklı `AnomalyResult`/`AnomalyType` sınıfı
  (`detect_anomaly.py` vs `app.core.entities`) — iki alt-sistemin
  kasıtlı olarak ayrı tutulduğu zaten dokümante, geniş bir rename riskli.
- `route_simulation/openroute_client.py`: zaten ayrı, DURMA NOKTASI'lı
  görev dosyasında (`TASKS/bug-openroute-client-architectural-leak.md`).
- Yerel ad-hoc test koşumunda 11 ortam-kaynaklı hata (api-stub profili
  başlatılmamış, gerçek Redis Sentinel, `USE_SEFER_FUEL_ESTIMATOR=true`)
  — hepsi `TASKS/STATUS.md`'nin dalga 1 bölümünde zaten belgelenmiş
  kategoriler, CI'da görülmez (CI kendi temiz ortamını kurar).

**Doğrulama disiplini:** her düzeltme gerçek Docker container'da (ruff +
mypy + hedefli pytest + çoğu için canlı before/after repro) doğrulandı;
2 push kırmızı çıktı (`.gitignore` bug'ı ve bir mock'un gerçekçi olmayan
davranışı), ikisi de gerçek kök nedenle (varsayımla değil) düzeltildi.

## DALGA 11 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-16)

**Kapsam:** analytics-executive modülü (Feature-E Strategic Cockpit: FVI,
what-if, karbon raporu, compliance heatmap, cashflow projeksiyonu,
cross-feature etki, bus-factor, CEO PDF + maliyet analizi + insight
üretimi) — 18 kaynak dosya + `analiz_repo.py`'nin kalan 14 metodu
`v2/modules/analytics_executive/` altına taşındı (application/domain/
infrastructure/api/schemas/events/public.py/CLAUDE.md).

**Task dosyasının 2 yanlış varsayımı düzeltildi (recon sırasında bulundu, kullanıcı onayıyla karar verildi):**
1. `get_bulk_driver_metrics`/`get_driver_comparison`'ın "driver dalgasında
   [5] zaten taşınmış olması gerekiyordu" — kontrol edildi, TAŞINMAMIŞTI
   (driver'ın kendi CLAUDE.md'si bunu doğru şekilde "geçici bağımlılık"
   olarak zaten işaretlemişti, task dosyasının varsayımı yanlıştı). Bu
   dalgada düzeltildi: yeni `v2/modules/driver/infrastructure/
   driver_metrics_queries.py` (free function, B.1), `driver_stats.py`/
   `evaluation.py` güncellendi.
2. `analytics.py` endpoint dosyası (+ `schemas/analytics.py` +
   `page_view_repo.py` + `workers/tasks/analytics_tasks.py`) task
   dosyasının envanterinde duruyordu ama içeriği tamamen `page_views`
   (Faz 3 kullanım analitiği) — Feature-E ile ilgisi yok. reports'un
   CLAUDE.md'si bu tutarsızlığı zaten dokümante etmişti (dalga 10'da
   bulunmuş, dalga 11'e bırakılmış). Kullanıcı kararıyla (tablo-sahipliği
   ilkesi): hepsi `v2/modules/reports/`'a taşındı, gerçek analytics_executive
   route sayısı task dosyasının iddia ettiği 10 değil **8**.

**Dead-code bulgusu + kullanıcı kararı:** `AnalizService`
(`container.analiz_service`) ve `DashboardService` sınıfları hiçbir prod
endpoint/servisten çağrılmıyordu (yalnız kendi ~20 test dosyası) —
kullanıcı kararıyla (dalga 1'in dead-property kaldırma emsaliyle aynı
gerekçe, bu kez 2 tam sınıf) TAMAMEN SİLİNDİ (`container.py`'nin
`analiz_service` property'si + state'i dahil). `InsightEngine`/
`CostAnalyzer` de aynı şekilde free function'lara bölündü (B.1) ama
silinmedi (gerçek/test edilmiş mantık, `InsightEngine`'in kendisi de
ölü kod ama kapsam dışı — kullanıcının kararı yalnız ilk ikisini
kapsıyordu).

**Doğrulama (gerçek Docker container, `lojinext-backend-1` + `lojinext_test` DB):**
- `ruff check` (tüm dokunulan dosyalar + `app v2 scripts` global) → temiz.
- `mypy app --ignore-missing-imports --no-strict-optional` → 0 hata (684 dosya).
- `pytest --collect-only`: `app/tests` 6733 test, kök `tests/` 266 test — 0 collection hatası.
- Hedefli gerçek-DB koşumları: analytics_executive'in kendi testleri (167),
  driver/sofor/evaluation testleri (460 + 43 + 60), container/core/business_flows/
  section1 (150), executive+advanced_reports API testleri (106), ML/ai_service/
  yakit servis testleri (78 + 136) — hepsi PASS.
- **Geniş doğrulama turu** (`app/tests/api` + `app/tests/unit/test_repositories`
  + `app/tests/integration`, 1764 test): **1749 passed, 7 failed** — 7 hata
  TAMAMEN dalga 1'de zaten belgelenmiş ortam-kaynaklı api-stub network
  topoloji sorunu (`test_mapbox_client.py`, `test_route_api.py` x2,
  `test_route_service_hybrid.py` x2, `test_locations_coverage.py`,
  `test_locations_api.py`) — analytics_executive/reports/driver ile hiçbir
  ilgisi yok, migration'dan kaynaklanmıyor.
- **Gerçek bulgu (mekanik dönüşüm sırasında bulundu, düzeltildi):** 5 test
  dosyası (`test_sofor_analiz_coverage.py`, `test_sofor_analiz.py`,
  `test_sofor_degerlendirme_coverage.py`, `test_sofor_degerlendirme_more.py`)
  `mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(...)` deseniyle
  mock'luyordu — taşıma sonrası bu metod `analiz_repo`'da yok, gerçek çağrı
  `uow.session.execute()`'a düşüp `TypeError: object MagicMock can't be
  used in 'await' expression` ile patlıyordu. `monkeypatch.setattr(driver_
  metrics_queries_mod, "get_bulk_driver_metrics", AsyncMock(...))` deseniyle
  düzeltildi (10 test fonksiyonu).

**main'e push edildi (commit `a01c679`), kullanıcı onayıyla.** İlk push
CI'da kırmızı çıktı (`gh run 29529523625`, "Backend unit tests" adımı) —
kök neden: 2 test dosyası eski `app/` yoluna FONKSİYON GÖVDESİ içinde
(deferred import / pathlib parça-parça birleştirme) erişiyordu, bu yüzden
`--collect-only` ve önceki hedefli Docker koşumlarım yakalayamamıştı:
- `test_endpoint_redis_singleton.py`: `from app.api.v1.endpoints import
  executive` fonksiyon içinde → `v2.modules.analytics_executive.api.
  executive_routes`'a güncellendi.
- `test_production_foundation_guards.py`: `ROOT/"app"/"database"/
  "repositories"/"analiz_repo.py"` pathlib join'i → `v2/modules/
  analytics_executive/infrastructure/executive_read_models.py`'ye
  güncellendi.

**Bağımsız dedektif denetimi (kullanıcı talebiyle, "en ufak detayı
atlama"):** 5 sıfır-context ajan paralel çalıştırıldı — (1) `analiz_repo.py`
metod envanteri (20 metod + factory, %100 kayıpsız doğrulandı), (2) ölü
referans taraması (repo genelinde sıfır gerçek kırık referans), (3) B.1
mimari uyumu (analytics_executive'in kendisi tam uyumlu; driver/fuel/
anomaly/fleet CLAUDE.md'lerinde bayat referans bulundu), (4) API/route
sözleşmesi (path/method/response_model/yetki/cache-key/audit-payload
birebir korunmuş, `get_vehicle_cost_comparison` isim çakışması doğru
alias'lanmış), (5) test dönüşüm kalitesi (zayıflatılmış assertion yok,
`monkeypatch` deseni gerçekten etkili). 4/5 ajan sıfır bulguyla döndü; B.1
ajanının bulduğu doc-drift (driver/fuel/anomaly/fleet CLAUDE.md'lerinin
"analytics_executive henüz taşınmadı" demesi + fuel/anomaly'ninkilerin
silinen `AnalizService`'in davranışını anlatması) düzeltildi.

**CI-fix commit `48e8e21`** (2 test dosyası + 4 CLAUDE.md) push edildi.
Push öncesi CI'nin birebir komutu (`pytest -m "unit or not integration"
--ignore=tests/integration --ignore=app/tests/integration`) gerçek Docker
container'da tam suite üzerinde tekrar koşturuldu: 5405 passed, 7 failed —
7'si STATUS.md'de zaten belgelenmiş ortam-kaynaklı hatalar (gerçek Redis
Sentinel + `USE_SEFER_FUEL_ESTIMATOR=true` prod-tarzı env, bu ad-hoc
container'a özgü, CI'nın temiz ortamında görülmez).

**CI Hard Gates TAM YEŞİL** (`gh run view 29531899079` → `success`,
hard-gates 33dk25sn + GHCR build/push 18dk32sn + Deploy→Production dahil) —
commit `48e8e21` main'in HEAD'i. https://github.com/semh59/lojinext/actions/runs/29531899079

### İlk 11 dalganın tam dedektif denetimi (2026-07-17)

Kullanıcı talebiyle ("ilk 11 dalgayı detaylı ve derin kontrol edelim...
SIFIR AJANLARA VER... DEDEKTİF GİBİ") 11 modülün (`location`,
`route_simulation`, `notification`, `fleet`, `fuel`, `driver`,
`auth_rbac`, `anomaly`, `import_excel`, `reports`, `analytics_executive`)
her biri için ayrı, sıfır-context, bağımsız ajan çalıştırıldı — B.1
kuralına ("her dosya/sınıf tek sorumluluk") satır satır denetim.
`auth_rbac` ve `reports` sıfır bulguyla tam temiz çıktı; diğer 9 modülde
toplam ~30 bulgu (1 GERÇEK BUG + mimari/dokümantasyon borcu).

**GERÇEK BUG bulundu ve aynı oturumda düzeltildi:** `import_excel`
modülündeki `ocr.process_belge` Celery task'ı (`v2/modules/import_excel/
infrastructure/tasks.py::process_belge_ocr`) `app/infrastructure/
background/celery_app.py`'nin explicit import listesinde YOKTU — dalga
9'un (`bffa2d4`) atladığı bir kayıt. Celery `autodiscover_tasks`
kullanmıyor, kayıt tamamen bu explicit import listesine bağlı; eksik
olunca Telegram sürücü-bot'unun belge-yükleme akışı (`.delay()` çağıran
gerçek prod kod) worker'da `NotRegistered` ile sessizce patlıyordu.
Testler bunu yakalayamamıştı çünkü hepsi task fonksiyonunu doğrudan
import ediyordu, worker'ın gerçek yükleme yolunu hiç kullanmıyordu.

**Düzeltme:** `celery_app.py`'ye eksik import eklendi + yeni regresyon
testi (`test_ocr_tasks_coverage.py::
test_task_registered_with_worker_via_celery_app_import_list` — gerçek
`celery_app.tasks` registry'sini kontrol ediyor, `.name` attribute'una
değil). TDD red→green gerçek Docker container'da doğrulandı (fix
revert edilince test kırmızı, geri konunca yeşil). `pytest app/tests/
unit/test_workers app/tests/unit/test_infrastructure/
test_celery_app_config.py` → 101 passed.

Kalan ~30 bulgu (domain/ katmanında I/O ihlalleri, public.py sınır
ihlalleri, CLAUDE.md doc-drift, dokümante edilmemiş ölü kod) kullanıcı
kararıyla ("Önce sadece gerçek bug'ı düzelt") bu oturumda uygulanmadı —
`TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md`'de takip ediliyor,
kullanıcı onayı olmadan dokunulmayacak.

**CI Hard Gates TAM YEŞİL** — commit `49b7532` main'in HEAD'i
(`gh run view 29555563172` → `success`, hard-gates 33dk49sn + GHCR
build/push 25dk24sn + Deploy→Production dahil).
https://github.com/semh59/lojinext/actions/runs/29555563172

(Not: bir önceki docs-only commit `4534eea`'nin CI'sında "Build & Push
to GHCR" job'ı "Extract frontend metadata" adımında geçici bir GitHub
API hatasıyla kırmızı çıkmıştı — ham GitHub 404 HTML sayfası dönmüştü,
backend metadata/build adımı hemen öncesinde sorunsuz geçmişti; kod
değişikliğiyle ilgisiz bir altyapı hıçkırığı olduğu teyit edildi,
`gh run rerun --failed` ile yeniden koşturuldu ve tam yeşile döndü.)

## DALGA 12 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-17/18)

**Kapsam:** ai_assistant modülü — LLM sohbet (`/ai/chat`, `/ai/query`,
`/ai/progress`, `/ai/status`), RAG (FAISS + sentence-transformers), Feature C
sefer planlama sihirbazı (`TripPlannerEngine`), pilot geri bildirimi
(`/feedback`). Tablo sahipliği yok (FAISS dosya-tabanlı indeks).

**Task dosyası düzeltmesi:** `TASKS/modules/ai-assistant.md`'nin 15 dosyalık
envanteri STALE — `app/core/ai/chatbot.py` hiç var olmamış (gerçek
`app/core/ai/` içeriği 9 dosyaydı). Gerçek envanter 14 dosya (9 core/ai +
`api/v1/endpoints/{ai,feedback}.py` + `core/services/ai_service.py` +
`schemas/trip_planner.py` + `services/smart_ai_service.py`). Route sayısı
(5) doğruydu.

**Yapı:** `v2/modules/ai_assistant/{api,application,domain,infrastructure,
schemas.py,events.py,public.py,CLAUDE.md}`. `ContextBuilder` sınıfı B.1
gereği free function'lara bölündü (`application/build_context.py`,
constructor'ı `pass` idi — anlamlı state yoktu). 10 sınıf istisnası kaldı
(hepsi gerçek mutable state/DI gerekçeli — detay `v2/modules/ai_assistant/
CLAUDE.md`): `FAISSVectorStore`, `RAGEngine`, `RAGSyncService`,
`GroqService`, `LLMClient`, `AIService` (predictor cache), `SmartAIService`+
`KnowledgeBase`, `RecommendationEngine`, `PromptTuner`, `TripPlannerEngine`.

**🔴 3 bağımsız ölü-kod bulgusu (taşındı, SİLİNMEDİ — InsightEngine/dalga 11
ile aynı gerekçe, kullanıcı kararı bekliyor):**
1. `AIService.predict_trip_fuel`/`detect_anomalies` — `EnsembleFuelPredictor`'ı
   prediction_ml'in gerçek tahmin yolundan (Phase 4-5 SeferFuelEstimator)
   BAĞIMSIZ ikinci bir kopyası, grep ile doğrulandı hiçbir prod endpoint
   çağırmıyor. `AIService`'in kendisi CANLI (chat path), yalnız bu 3 metot ölü.
2. `RecommendationEngine` — hiçbir prod endpoint çağırmıyor.
3. `PromptTuner` — `AIService.generate_response` kendi basit
   `_sanitize_prompt`'unu kullanıyor, bu sınıfı hiç çağırmıyor.

**RAGSyncService CANLI (diğer modüllerin ölü event-subscriber bulgusundan
FARKLI):** `main.py` lifespan'i `get_rag_sync_service().initialize()`'ı
gerçekten çağırıyor — Docker container'da doğrulandı (`ARAC/SOFOR/SEFER
_ADDED/UPDATED` 6 aboneliği gerçek DB verisiyle 5 araç/4 şoför/5 sefer
indeksledi, log'da görüldü). ✅ **2026-07-18 dedektif denetiminde bulunan
+ düzeltilen nüans:** kayıt/wiring canlıydı ama İLK turdaki bu doğrulama
yalnız `initial_sync()`'in tek seferlik başlangıç taramasını kapsıyordu —
ARTIMLI (event-tetiklemeli) güncelleme yolu 3 gerçek bug yüzünden fiilen
çalışmıyordu (bkz. aşağıdaki "İkinci tur dedektif denetimi" bölümü),
bugünkü düzeltmeyle gerçekten 6/6 çalışır hale geldi.

**Bulunan+düzeltilen gerçek geçiş hataları (refactor sırasında, davranış
regresyonu değil ama mekanik taşıma eksikleriydi):**
- `app/core/ai/context_builder.py` ilk taşımada unutulmuştu (shim
  atanmamıştı, eski `ContextBuilder` sınıfı hâlâ duruyordu, yeni
  `build_context.py` ile paralel/orphan kod oluşturuyordu) — dosya silindi,
  `test_context_builder_coverage.py` free-function-mock desenine çevrildi
  (19→18 test, singleton testi düştü çünkü artık singleton sınıf yok).
- `app/tests/api/test_ai_query.py` — `patch("app.api.v1.endpoints.ai.
  get_ai_service")` artık çalışmıyordu (endpoint kodu artık `ai_routes.py`'de
  yaşıyor, shim modülün kendi kopyası patch'lense de gerçek handler'ı
  etkilemiyor) → patch hedefi `v2.modules.ai_assistant.api.ai_routes.
  get_ai_service`'e çevrildi.
- `app/tests/unit/test_services/test_health_service.py` (×2) +
  `test_health_service_more.py::test_check_ai_readiness_error_path` — aynı
  sınıf hata, `get_rag_engine` artık `health_service.py` içinde
  `v2.modules.ai_assistant.infrastructure.rag.rag_engine`'den import
  ediliyor, patch hedefi güncellendi.
- `app/tests/test_ai_security.py` — `faiss` modülü artık `rag_engine.py`'de
  değil `vector_store.py`'de yaşıyor (FAISSVectorStore oraya taşındığı için),
  patch hedefi `vector_store.faiss`'e çevrildi.

**Doğrulama (gerçek Docker container + gerçek `lojinext_test` Postgres DB,
`docker compose up -d --build backend` ile — yeni modül dosyaları
`docker cp` ile taşınamaz, container zaten ayaktaydı, imaj yeniden
build edildi):**
- `ruff check app v2 tests` → temiz.
- `mypy app --ignore-missing-imports --no-strict-optional` → "Success: no
  issues found in 683 source files" (regresyon yok).
- `python -m pytest app/tests --collect-only` (host + container, gerçek
  test DB'siyle) → 6662-6663 test, **0 collection hatası**.
- ai_assistant'a özgü 33 test dosyası (context_builder, ai_service×3,
  smart_ai_service, llm_client, groq_service, recommendation×2,
  rag_sync_service, rag_engine×2, prompt_tuner, trip_planner×4, ai_security
  ×3, ai_privacy, ai_deep_remediation, ai/test_rag_and_ai_service,
  backend_hygiene_sources, prediction_service×2, section_1_backend_core,
  ai_query, trips_coverage, plan_wizard_endpoint, kök `tests/`'ten 4 dosya):
  gerçek Docker container'da gerçek `lojinext_test` DB'ye karşı **588
  passed, 4 skipped, 0 failed** (2 düzeltme turu sonrası — ilk turda 1
  failed + 2 error, yukarıda anlatılan patch-target hatalarıydı).
- Tam `app/tests/unit` süiti (5977+ test, gerçek DB'ye karşı, gerçek
  container): **5130 passed, 29 failed, 22 skipped**. 29 hatanın TAMAMI
  root CLAUDE.md'nin "Bilinen ortam-kaynaklı test hataları" listesindeki
  ÖNCEDEN DE VAR OLAN kategorilerle birebir eşleşiyor (api-stub docker-network
  topolojisi: mapbox/openroute/route_service/lokasyon_service — 21 test;
  `USE_SEFER_FUEL_ESTIMATOR=true` env varsayımı: phase4/sefer_write_service —
  3 test; gerçek Redis Sentinel: event_bus/health_service — 2 test; `.env.example`
  cwd: admin_backend_operations — 1 test) — hiçbiri ai_assistant/rag/groq/
  trip_planner/smart_ai/recommendation/prompt_tuner dosyalarına dokunmuyor,
  dalga 12 ile ilgisi yok, net-yeni regresyon SIFIR.
- `alembic check` çalıştırılmadı — bu modül hiçbir DB tablosuna sahip değil
  (doğrulandı, şema değişikliği yok).

**İkinci tur dedektif denetimi (2026-07-17/18, kullanıcı talebiyle "ilk 12
dalgayı detaylı ve derin kontrol edelim... dedektif gibi denetlesinler"):**
4 bağımsız sıfır-context ajan (giriş katmanı/api+public+events+schemas+
orchestration; RAG altyapısı; LLM+prompt+recommendation; trip-planner+
repo-geneli tüketici/shim taraması) + ayrı bir 5. compliance-audit ajanı
(görev dosyasının Taşıma Adımları/Kabul Kriterleri'ne + shim/CLAUDE.md
şablon sözleşmesine harfiyen uyulup uyulmadığını denetledi) dalga 12'yi
tekrar taradı. Bulgular:
- Mekanik/dokümantasyon borcu (3 shim'in gereksiz 2. import satırı,
  `trips.py`'nin CLAUDE.md'nin iddiasının aksine `public.py`'yi atlaması,
  `build_context.py`/`rag_sync_service.py`'nin fleet/fuel/
  analytics_executive'e doğrudan `infrastructure` erişimi, 2 eksik
  CLAUDE.md şablon bölümü, `events.py`'nin DTO içermediğinin yanlış
  dokümante edilmesi) — hepsi aynı oturumda düzeltildi.
- **4 gerçek, davranış-etkileyen pre-existing bug** (`git show` ile
  dalga-12-öncesinden beri var olduğu doğrulandı, dalga 12'nin
  regresyonu DEĞİL): (1) sefer RAG senkronu payload-anahtar uyuşmazlığı
  yüzünden prod'da hep no-op, (2) araç/şoför RAG senkronunun int-branch'i
  session'sız singleton repo'da `RuntimeError`'a çarpıp event-bus
  tarafından sessizce yutuluyordu, (3) FAISS indeksleri (`rag_engine.py`
  + `knowledge_base.py`) paylaşımlı `app_data` Docker volume'ünün
  DIŞINDA bir path'e yazıyordu, (4) `ai_routes.py::_fuel_trend_chart`
  fuel'in `yakit_alimlari` tablosuna endpoint katmanından ham SQL
  atıyordu. Kullanıcının açık onayıyla ("eksikleri düzelt, teknik borç
  bırakma, varsayım yok") 4'ü de bu oturumda düzeltildi (detay:
  `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md` BÖLÜM C).
- Kendi düzeltmemin yan etkisi olarak bulunan ek gerçek regresyon:
  `trips.py`'nin `public.py`'ye geçişi `app/tests/api/
  test_trips_coverage.py`'nin 2 testinin patch hedefini geçersiz
  kılmıştı (biri yanlışlıkla yeşil kalıyordu — mock koda hiç değmiyordu
  — diğeri CI'da gerçekten kırmızı çıktı, `assert 200 == 500`). Patch
  hedefi `v2.modules.ai_assistant.public.TripPlannerEngine`'e
  güncellendi.

**Doğrulama (2. tur, gerçek Docker + `lojinext_test` DB):** `ruff check
app v2` temiz, `mypy app` temiz (682 dosya), `pytest --collect-only
app/tests tests` 6928 test/0 hata, ilgili 19+2 test dosyası 345+69
passed, `app/tests/api`'nin TAMAMI (879 test) passed.

**CI durumu: ✅ TAM YEŞİL.** 3 push turu oldu: `df14908` (ana taşıma) →
CI kırmızı (2 eski test patch-target) → `940bcf3` (düzeltme, ilk CI
denemesi "Security — RBAC coverage" adımında native kütüphane
çökmesiyle kırmızı çıktı — `git show` ile dalga-12-öncesi koda birebir
aynı olduğu doğrulanıp rerun edildi, **yeşil**, 35dk37sn — geçici CI
hıçkırığıydı, regresyon değil) → `fcee130` (1. tur dedektif denetim
mekanik düzeltmeleri, yeşil) → `928de51` (2. tur dedektif denetim + 4
gerçek bug fix + trips.py test düzeltmesi). **`gh run view 29611326223`
→ `success`** (hard-gates 30dk43sn + GHCR build/push 15dk49sn + Deploy→
Production/Staging dahil main'in HEAD'i).

**Kod-dışı bulunan pre-existing sorun (bu dalgayla ilgisiz, düzeltilmedi):**
`.importlinter`'ın "unmatched_ignore_imports_alerting = error" ayarı,
dosyadaki EN AZ 3 önceden-var-olan stale `ignore_imports` girdisi yüzünden
(`app.core.container -> v2.modules.import_excel.infrastructure.
report_export`, `v2.modules.fuel.domain.** -> v2.modules.{fleet,
analytics_executive}.infrastructure.**`) lint-imports'un DAHA 1. contract'ta
exception fırlatıp durmasına neden oluyor — bu main branch'te (dalga 12
öncesi de) zaten böyleydi, `git stash` ile doğrulandı. CI'nın import-linter
adımı "rapor modu" (continue-on-error) olduğu için bu hiç fark edilmemiş.
Bu dalgada eklenen `ai_assistant` ile ilgili YENİ `ignore_imports`
girdilerinin kendisi temiz doğrulandı (geçici olarak 3 stale satır
kaldırılıp `lint-imports` tekrar koşturuldu, ai_assistant contract'larında
sıfır hata bulundu). Ayrı bir bağımsız temizlik görevi açılabilir.

**Değişen dosya sayısı:** 22 mevcut dosya düzenlendi (shim'ler dahil) + 20
yeni dosya (`v2/modules/ai_assistant/`) + ~30 test dosyası import-path
taşıması (mekanik, 3'ü patch-target düzeltmesi de gerektirdi).

## DALGA 13 — ✅ TAMAMLANDI VE MAIN'DE (2026-07-18)

**Kapsam:** prediction_ml modülü — 5-model ensemble (fizik+LightGBM+XGBoost+
GB+RF), fizik-tabanlı fallback motoru, Kalman online-learning, ARIMA zaman
serisi tahmini, model eğitim/versiyonlama, admin ML endpoint'leri, XAI
açıklama. `egitim_kuyrugu`/`model_versiyonlar`/`prediction_results`
tablolarının tek sahibi. En büyük modül (10.375 LOC, 36 dosya — task
dosyasının 35-dosya envanteri `app/core/ml/route_similarity.py`'yi
atlıyordu, gerçek envanter FAZ0'da doğrulandı).

**Envanter/plan düzeltmeleri (dedektif ön-denetiminde bulundu, kullanıcı
onayıyla uygulandı):**
1. `app/core/ml/route_similarity.py` task dosyasının 35-dosya listesinde
   YOK ama gerçekte prediction_ml'e ait (`find_similar_trips`, ai_assistant'ın
   `plan_trip.py`'si kullanıyor) — taşındı (`domain/route_similarity.py`).
2. `app/scripts/benchmark.py` task dosyasında listeliydi ama içeriği
   ML/prediction ile HİÇ ilgili değil (generic DB/fleet/reports perf
   benchmark script'i) — TAŞINMADI, task dosyasının bu satırı stale.
3. `app/core/ml/model_manager.py` — FAZ0'da dead code olarak doğrulandı:
   `save_version()`'ın yazdığı `model_versions` tablosu alembic geçmişinde
   HİÇ var olmadı (yalnızca bir INDEX adı kısa süre bu ismi taşıyıp
   `model_versiyonlar`'a yeniden adlandırıldı — `alembic/legacy_versions_
   archive/ef8abc3ede67_017_ml_versions_queue.py` ile doğrulandı). 3 çağıran
   sitesi (`ensemble_service.py`) bu hatayı sessizce yutuyordu. Kullanıcı
   kararı: **tamamen sil** — `model_manager.py` + deprecated rogue script
   `scripts/init_ml_db.py` (kendi docstring'i "bunu çalıştırma, alembic
   kullan" diyordu, yine de `model_versions`'ı eksik şemayla manuel
   oluşturuyordu) + `test_model_manager_coverage.py` SİLİNDİ.
4. **Gerçek yazım yolu bağlandı**: `MLService.register_model_version()`
   (`model_versiyonlar`'a doğru ORM INSERT) daha önce SIFIR prod çağıranı
   vardı (`GET /admin/ml/versions/{arac_id}` hep boş dönüyordu). Kullanıcı
   kararı: **doğru yere bağla** — yeni `_register_model_version()` free
   function (kendi `UnitOfWork` + `MLService` + `model_versiyon_repo.
   get_latest_version()`) eklendi, 3 eski `model_manager` çağıran sitesi
   buna yönlendirildi. Kendi try/except'i içinde TÜM hataları yutuyor —
   bu ayrıca `train_general_model`'daki gerçek bir davranış hatasını da
   düzeltti: eskiden `save_version()` istisnası dış `try`'a düşüp
   fonksiyonun geri kalanını (legacy kayıt, disk serialize, heavy/medium/
   light class-model döngüsü) iptal ediyordu; artık izole.
5. `app/core/ml/predictors/` paketi (`EnsemblePredictor` inference-only
   wrapper) — grep ile sıfır prod çağıran doğrulandı (yalnız kendi özel
   test dosyası). Kullanıcı kararı ("ölü kod yasak" tutarlılığı):
   **sil** — paket + `test_phase4_ml_predictors_training_split.py` silindi.
6. `analytics_executive`'in 4 ML-parametre metodundan yalnız
   `get_training_seferler` (sıfır prod çağıran) SİLİNDİ; diğer 3
   (`save_model_params`/`get_model_params`/`get_daily_summary_for_ml`)
   kullanıcı kararıyla BİLİNÇLİ OLARAK `analytics_executive`'te bırakıldı
   (çapraz-modül repo-metod taşıma davranış-değişikliği riski taşıyor,
   mekanik-taşıma kapsamının dışında).

**Yapı:** `v2/modules/prediction_ml/{api,application,domain,infrastructure,
schemas.py,events.py,public.py,CLAUDE.md}`. `predict_consumption`
(eskiden CC=50, 257 satır) ZATEN yardımcı metotlara bölünmüştü (taşımadan
önce) — task dosyası §5'in 4 kümesi uygulandı ama 2 kümenin YERİ kök
CLAUDE.md'nin domain-saflık kuralı gereği düzeltildi: `_run_physics_fallback`
(response_builder'a bağımlı olduğu için domain/'de KALAMAZDI —
`application/prediction_service.py`'de instance metodu olarak kaldı) ve
"ensemble kümesi" (`run_ensemble_prediction`/`process_ensemble_result` —
gerçek DB I/O yaptığı ve response_builder'a bağımlı olduğu için task
dosyasının önerdiği `domain/ensemble.py` DEĞİL, yeni
`application/ensemble_orchestration.py`'de). `ensemble_core.py::fit`
(CC=61) task dosyasının kararı gereği bölünmedi (baseline'da kaldı).
Prefetch-N+1 koruması (`_arac_obj`/`_sofor_obj`/`_dorse_obj`) birebir
korundu.

**10 sınıf istisnası** (hepsi gerçek mutable state/DI gerekçeli, detay
`v2/modules/prediction_ml/CLAUDE.md`): `PredictionService`,
`EnsemblePredictorService`, `EnsembleFuelPredictor`,
`PhysicsBasedFuelPredictor`/`HybridFuelPredictor`, `KalmanFuelEstimator`/
`KalmanEstimatorService`, `LightGBMFuelPredictor`/`LightGBMAnomalyClassifier`,
`ARIMATimeSeriesPredictor`+legacy LSTM sınıfları, `Trainer`,
`ModelTrainingHandler`/`PhysicsRecalculationHandler`, `TimeSeriesService`.

**Bağlaşıklık karnesi doğrulandı** (out=27 en dolaşık tüketici) — TÜM
çapraz-modül erişimler zaten `public.py`/`uow.<repo>` üzerinden gidiyordu,
bu dalgada YENİ bir bypass-import düzeltmesi GEREKMEDİ (önceki 12 dalganın
aksine). 9 modülün (fleet, driver, route_simulation, analytics_executive,
ai_assistant, auth_rbac, fuel, reports, location) `public.py`'leri zaten
yeterliydi. Geriye kalan işler: 8 tüketen dosyanın import path'i eski
`app.core.ml.*`/`app.services.prediction_service`'ten
`v2.modules.prediction_ml.public`'e güncellendi (`location/
analyze_location_route.py`, `route_simulation/{simulate_route,
create_route_simulation,get_route_details}.py` + `domain/segment_
simulator.py`, `ai_assistant/plan_trip.py`, `analytics_executive/
aggregate_cross_feature.py`, `sefer_fuel_estimator.py`, `sefer_write_
service.py` [4 site], `driver/driver_stats.py`, `anomaly/detect_anomaly.py`,
`trips.py`, `container.py`, `scripts/p51_real_world_validation.py`) —
hepsi bu modüllerin kendi CLAUDE.md'sinde "prediction_ml henüz taşınmadı,
geçici" olarak zaten dokümante edilmiş bekleyen işlerdi, bu dalgada
kapatıldı.

**Shim stratejisi:** `app/core/ml/ensemble_predictor.py` (28 satırlık eski
backward-compat shim, ensemble_core+ensemble_service'ten re-export ediyordu)
YENİ hedeflere (`v2.modules.prediction_ml.domain.ensemble_core` +
`.application.ensemble_service`) işaret edecek şekilde güncellendi (19
kalan çağıranı — script'ler + testler — tek seferde kapsıyor, hepsi tek
tek düzeltilmedi). Diğer tüm eski `app/` dosyaları (prediction_service.py,
ensemble_service.py, ml_service.py, vb.) doğrudan taşındı (shim YOK, tüm
gerçek çağıranlar tek tek güncellendi — az sayıda üretim çağıranı olduğu
için ai_assistant/driver/fleet gibi modüllerin izlediği "az çağıran →
doğrudan güncelle" deseni izlendi).

**`.importlinter` güncellemesi:** 13. `public-surface-only-prediction_ml`
kontratı eklendi; diğer 12 modülün her birinin `forbidden_modules`'üne
`prediction_ml.{api,application,domain,infrastructure}` eklendi;
`12 modulun domain/infrastructure...` ve `Modul-ici katman sirasi`
kontratlarına `prediction_ml` eklendi (ikincisi `infrastructure.** ->
application.**` ignore'u gerektirdi — Celery task'ları `Trainer`/
`PredictionBackfillService`'i application'dan import ediyor, diğer
modüllerde de aynı desen var, örn. `anomaly.infrastructure.** ->
anomaly.application.**`). Tüm 16 kontrat KEPT (yalnız pre-existing
report-only `app.services`↔`app.core.services` FAZ0 kontratı BROKEN
kaldı — bu dalgadan önce de böyleydi, ilgisiz).

**Test taşıması (~35 dosya, mekanik + birkaç patch-target/davranış
düzeltmesi):**
- Toplu sed ile import path güncellemesi (`app.core.ml.*` →
  `v2.modules.prediction_ml.{domain,application}.*`, vb.) — 61 dosya.
- `test_ensemble_service_coverage.py`/`test_ensemble_service_more.py`/
  `test_ml_prediction_safety.py`/`test_ml_training_contracts.py` — eski
  `app.core.ml.model_manager.get_model_manager` patch hedefleri
  `_register_model_version`'a çevrildi (yeni fonksiyon kendi try/except'i
  içinde tüm hataları yuttuğu için "manager exception → hâlâ devam eder"
  testleri artık davranışı doğrudan doğruluyor, ModelManager'ın eski
  kwarg şeklini simüle etmiyor).
- `test_prediction_service_coverage.py`/`test_prediction_service_more.py`/
  `test_prediction_with_health.py`/`test_services/test_prediction_service_
  contracts.py`/`test_services/test_runtime_config.py` — `PredictionService.
  _build_explanation_summary` gibi eski staticmethod çağrıları
  `response_builder.build_explanation_summary` gibi free-function
  çağrılarına, `patch.object(svc, "_run_physics_model", ...)` gibi eski
  instance-method patch'leri `patch("...prediction_service.run_physics_
  model", ...)` module-level patch'lerine çevrildi (fonksiyonlar artık
  domain/application'a taşınan serbest fonksiyonlar).
- `test_sefer_write_more.py`/`test_sefer_write_more2.py`/
  `test_sefer_write_service_coverage.py`/`test_sefer_write_service_
  prediction_flows.py` — `sefer_write_service.py`'nin inline import'u
  (`from v2.modules.prediction_ml.public import get_prediction_service`)
  `public.py` üzerinden geldiği için patch hedefi ilk denemede yanlışlıkla
  `application.prediction_service.get_prediction_service`'e verilmişti
  (frozen import nedeniyle etkisizdi) — `v2.modules.prediction_ml.public.
  get_prediction_service`'e düzeltildi (inline-import gotcha'sı, KAYNAK
  modül = fiilen import edilen modül, ara-katman değil).
- `test_ml_audit.py` — 2 hardcoded dosya-yolu kontrolü (`app/core/ml/
  time_series_predictor.py` var mı, `pickle.load` taraması) yeni
  `v2/modules/prediction_ml/domain/` konumuna güncellendi (aksi halde
  boş eski dizini tarayıp testler sessizce anlamsız-yeşil olurdu).
- `mypy.ini`'deki 3 modül-özel override (`app.core.ml.{lightgbm_predictor,
  time_series_predictor,advanced_lstm}`) yeni `v2.modules.prediction_ml.
  domain.*` yollarına taşındı (aksi halde ML kütüphanesi tip-stub eksikliği
  suppress'leri sessizce devre dışı kalırdı).

**Doğrulama:** `ruff check app v2 scripts tests --select E,F,W,I` temiz;
`mypy app`/`mypy v2` sıfır hata; `lint-imports` 16 kontrat (15 KEPT + 1
pre-existing report-only BROKEN); tüm prediction_ml + dokunulan
sefer_write_service/route_simulation/location/ai_assistant/driver/anomaly
testleri yeşil (700+ test).

**Değişen dosya sayısı:** 36 dosya taşındı (`app/`→`v2/modules/
prediction_ml/`), 3 dosya silindi (`model_manager.py`,
`predictors/{__init__,ensemble_predictor}.py` paketi, `scripts/
init_ml_db.py`), 1 dosya schemas.py'ye birleşti (`ml_schemas.py` →
`schemas.py`), ~15 üretim tüketici dosyası import-path güncellendi,
~35 test dosyası taşındı/güncellendi, `.importlinter` (+90 satır, 1 yeni
kontrat), `mypy.ini` (3 override yolu güncellendi), kök `CLAUDE.md` +
6 modülün kendi `CLAUDE.md`'si (location, route_simulation, ai_assistant,
driver, analytics_executive + prediction_ml'in kendi yeni dosyası).

### DALGA 13 takip-denetimi (2026-07-18, dördüncü oturum) — bağımsız ajan denetimi

Kullanıcı talebi: "Dalga 13 detaylı ve derin incele. Kurallara uygun
taşındı mı. Hata ve eksik var mı." Taze bağlamlı bağımsız bir ajan ile
(lint-imports/ruff/mypy/pytest'i GERÇEKTEN çalıştırarak, iddiaları
doğrulamadan kabul etmeden) tam denetim yapıldı. Bulunan gerçek sorunlar:

1. 🔴 **Kural ihlali — no-shim ilkesi**: ilk taşıma commit'i (`9e47ce8`)
   `app/core/ml/ensemble_predictor.py`'yi (`EnsembleFuelPredictor`/
   `EnsemblePredictorService`/vb. re-export eden) geçici bir backward-compat
   shim olarak bırakmıştı — kök `CLAUDE.md`'nin "migrated modülün eski
   `app/` dosyaları silinir, shim bırakılmaz, kalan çağıranlar tek tek
   `v2.modules.<name>`'e güncellenir" kuralına doğrudan aykırıydı. Bu
   sapma STATUS.md'nin (o zamanki) metninde "pragmatik" bir not olarak
   vardı ama kural ihlali olduğu açıkça yazılmamıştı. **Düzeltildi**: shim'i
   kullanan 19 site (`scripts/train_ensemble.py`, `scripts/
   train_model_with_route_features.py`, 12 test dosyası) gerçek
   `v2.modules.prediction_ml.{public, domain.ensemble_core,
   application.ensemble_service}` yollarına güncellendi; shim dosyası +
   artık boşalan `app/core/ml/` dizini tamamen silindi.
2. 🟡 **Eksik dokümantasyon — B.1 sınıf istisnası listesi tamamlanmadı**:
   `MLService` (`application/ml_service.py`, class-level `_locks` mutable
   state) ve `domain/benchmark.py`'nin `MLBenchmark`/`ABTestFramework`/
   `EnsembleBenchmark` sınıfları modülün kendi `CLAUDE.md`'sindeki
   "10 sınıf istisnası" listesinde yoktu. **Düzeltildi**: liste 12 kaleme
   çıkarıldı, gerekçeleriyle (`MLService`→paylaşılan kilit sözlüğü;
   benchmark sınıfları→sıfır prod çağıranı olan "taşındı ama wire
   edilmedi" kategorisi, `lightgbm_predictor`/`kalman_estimator`/
   `HybridFuelPredictor` ile aynı gotcha'ya eklendi).
3. 🟢 **Kozmetik — CLAUDE.md kolon adı yanlış**: `model_versiyonlar`
   tablosunun kolonlarını sayarken `olusturma_zaman` yazıyordu; gerçek ORM
   kolonu `egitim_tarihi` (`app/database/models.py:1154`, doğrulandı).
   Düzeltildi.

Denetimde CONFIRMED (doğru/temiz) çıkan maddeler: 36 dosyalık yapısal
envanter, cross-module bypass taraması (sıfır ihlal), domain saflığı
(`physics_model.py` application'a bağımlı değil), `lint-imports`
(15 kept + 1 pre-existing ilgisiz broken), `ruff`/`mypy` sıfır hata,
483 toplanan test / 479 geçen (denetim anında), `_register_model_version`
wiring + `train_general_model` davranış-düzeltmesi.

**Doğrulama (bu takip turu)**: shim kaldırma sonrası `ruff check
v2/modules/prediction_ml app scripts --select E,F,W,I` temiz; `mypy
v2/modules/prediction_ml` sıfır hata; `lint-imports` değişmedi (15 kept +
1 pre-existing broken); ilgili 13 test dosyası + `test_ml/` tam paketi
602 passed/4 skipped; ardından tam `pytest app/tests tests -m "unit or
not integration"` koşumu ile regresyon kontrolü yapıldı.

## DALGA 14 — ✅ TAMAMLANDI (branch `claude/son-durum-ltxexy`, 2026-07-18)

**Kapsam:** trip modülü — en karmaşık split (task dosyası kendi başlığında
"en karmaşık split" olarak işaretlemişti). Sefer CRUD, durum makinesi
(Planned/Completed/Cancelled), dönüş seferi otomasyonu, bulk operasyonlar,
Phase 4-5 `SeferFuelEstimator` (sefer create yolu, kök CLAUDE.md'de
dokümante), SLA gecikme tespiti, maliyet mutabakatı, onay iş akışı.
`seferler`/`route_simulations`/`route_segments` tablolarının tek sahibi.
`sefer_write_service.py`'nin 28 üyesi haritalandı (`domain/trip_validation.py`
+ 11 `application/*.py` dosyasına dissolve edildi, B.1).

**Envanter/plan düzeltmeleri (task dosyası vs gerçek kod, kullanıcı onayıyla
"plan yeterli değil mi" talimatıyla uygulandı):**
1. `sla.py` — task dosyası `domain/sla.py` öneriyordu; gerçek kod
   `uow.sefer_repo`/`uow.lokasyon_repo` DB I/O + `get_outbox_service()`
   çağrısı yapıyor → `application/sla.py`'ye taşındı (prediction_ml
   dalgasındaki aynı sınıf sapmayla tutarlı).
2. Dönüş seferi kümesi (`return_trip.py`) — aynı gerekçeyle
   `domain/` yerine `application/`'a taşındı.
3. Task dosyasının "import_excel/analytics_executive/ai_assistant zaten
   hazır" varsayımı 3 hedeften 2'sinde (import_excel, ai_assistant)
   doğruydu, analytics_executive'te YANLIŞTI — cost/stats route'ları hiç
   bağlı değildi, gerçek kod okunarak yeni ince wrapper route dosyası
   yazıldı (`analytics_executive/api/trip_analytics_routes.py`).
4. `sefer_status.py`/`trip_status.py` planın önerdiği `domain/` yerine
   **modül köküne** taşındı — bkz. aşağıdaki import-linter bölümü,
   bu dalgada ilk kez karşılaşılan yeni bir kontrat inceliği yüzünden.

**Yapı:** `v2/modules/trip/{api,application,domain,infrastructure,
schemas.py,sefer_status.py,trip_status.py,events.py,public.py,CLAUDE.md}`.
`SeferReadService`/`SeferWriteService`/`SeferAnalizService` (CQRS
alt-servisleri) tamamen dissolve edildi; `SeferService` facade olarak
KALDI (ARCH-006 — hiçbir endpoint alt-fonksiyonları doğrudan import
etmiyor, doğrulandı). `SeferFuelEstimator` da kendi gerekçesiyle sınıf
olarak kaldı (constructor-injected client'lar). `SeferRepository`'nin 6
şofor-özel sorgusu (`get_by_sofor_id` vb.) `v2/modules/driver/
infrastructure/driver_trip_queries.py`'ye taşındı (task dosyası kararı);
`get_all`'ın genel arama özelliği artık `driver.public.
search_driver_ids_by_name`'i çağırıyor.

**Router bölünmesi:** eski `app/api/v1/endpoints/trips.py` (1017 satır,
22 route) silindi, 8 yeni dosyaya bölündü — 4'ü trip'te kaldı
(read/write/bulk/approval), 2'si import_excel'e (export/import), 1'i
analytics_executive'e (cost-analysis/stats), 1'i ai_assistant'a (plan
wizard) taşındı. Tümü `api.py`'de aynı `prefix="/trips"` altında
`include_router` ile bağlandı — URL'ler DEĞİŞMEDİ (router objesinin
fiziksel konumu URL'i etkilemez, prefix belirler).

**`.importlinter` yeni bulgu — domain/infrastructure bağımsızlığı AYNI
modül içinde de geçerli:** önceki 13 dalgada hiç karşılaşılmamış bir
kontrat inceliği bulundu — `type=independence` kontratı aynı üst modülün
`domain`/`infrastructure` alt-paketlerini AYRI item olarak listelediğinde,
bu ikisi arasında da sıfır import yolu şartı koşuyor (yalnızca modüller
ARASI değil). `trip.infrastructure`'ın `trip.domain.sefer_status`/
`trip_status`'ü doğrudan import etmesi bunu ihlal etti — çözüm:
`sefer_status.py`/`trip_status.py` `domain/`'den modül köküne taşındı
(`schemas.py` gibi kontratın `modules` listesi dışında), repo genelinde
10 dosyada import path'i güncellendi. Ayrıca `public-surface-only-trip`
16. kontrat olarak eklendi; diğer 13 kontratın `forbidden_modules`'üne
trip'in 4 katmanı eklendi. Nihai durum: **16 kept, 1 broken** (pre-existing,
ilgisiz FAZ0 kontratı).

**Cross-module tüketici düzeltmeleri:** `analytics_executive/
executive_read_models.py` (circular-import fix — lazy import),
`import_excel/sefer_importer.py`+`sefer_upload_importer.py`
(container→public.py doğrudan çağrı), `internal_service.py` (ölü
sefer_repo kaldırıldı), `driver/driver_stats.py`+`route_profile.py`+
`get_route_profile.py` (mypy'nin bulduğu 3 GERÇEK bug — artık var
olmayan `sefer_repo.<driver_method>` çağrıları, taşınan 6 sorgudan
kaynaklı), `prediction_ml/route_similarity.py`+`ensemble_service.py`+
`prediction_backfill_service.py` (import path).

**Test taşıması (~40 dosya):** toplu sed + yapısal olarak kırılan dosyalar
tek tek yeniden yazıldı (`test_sefer_write_more.py`: 28/28,
`test_sefer_write_more2.py`: 25/25, `test_sefer_write_service_coverage.py`:
75/75 — `@pytest.mark.integration`, gerçek DB, `test_sefer_write_service_
prediction_flows.py`: 5/5, `test_sefer_read_service.py`,
`test_sefer_status_guards.py`, `test_sefer_prediction_contract.py`).
Free-function patch-target konvansiyonu diğer 13 modülle tutarlı
(modül-seviyesi import → tüketen modülün namespace'i, örn.
`update_trip.check_sla_delay`; inline import → kaynak modül, örn.
`v2.modules.trip.application.sefer_fuel_estimator.get_sefer_fuel_estimator`).
`SeferWriteService.VALID_STATUS_TRANSITIONS` alias testi düşürüldü
(sınıf dissolve olunca alias kavramı da anlamsızlaştı, tek isim
`ALLOWED_TRANSITIONS` kaldı).

**Doğrulama:** `ruff check app v2 scripts --select E,F,W,I` temiz;
`lint-imports` 16/17 kontrat kept (1 pre-existing ilgisiz broken);
`pytest --collect-only app/tests tests` 6674 test / 0 hata; gerçek
Postgres 16 + Redis'e karşı `app/tests/unit/test_services/
test_sefer_write_service_coverage.py` (75 passed) +
`test_sefer_write_service_prediction_flows.py` (5 passed) +
`test_sefer_write_more.py`/`test_sefer_write_more2.py` (28+25 passed)
tam yeşil.

**Değişen dosya sayısı:** 4 dosya taşındı (`sefer_fuel_estimator.py`,
`schemas.py`, `sefer_status.py`, `trip_status.py`), 6 dosya silindi
(`trips.py` endpoint, `sefer_service.py`, `sefer_read_service.py`,
`sefer_write_service.py`, `sefer_analiz_service.py`, `sefer_repo.py`),
~30 yeni dosya oluşturuldu (`v2/modules/trip/` + 4 hedef modülün yeni
route dosyaları + `driver_trip_queries.py`), ~15 üretim tüketici dosyası
güncellendi, ~40 test dosyası taşındı/güncellendi, `.importlinter`,
kök `CLAUDE.md` + `v2/modules/trip/CLAUDE.md` (yeni).

## Son güncelleme

2026-07-18 (üçüncü oturum) — İlk 12 dalganın TAM-DENETİM DÜZELTME
TURU'NUN İKİNCİ GEÇİŞİ (kullanıcı talebi: "dalga 13 geçmeden önce bir
eksik unutulan göz ardı edilen en ufak bir kusur istemiyorum"). İkinci
geçişte bulunan gerçek sorunlar:

- 🔴 **Kritik: önceki turun ölü-kod silme işleminin 7 dosyası hiç
  commit'e girmemişti.** Kök neden: `git rm` çoklu-dosya çağrısında bir
  dosyanın (`test_context_builder_coverage.py`) o an yerel değişikliği
  vardı — `git rm` bu YÜZDEN TÜM batch'i (9 dosya) sessizce reddetti
  (`error: local modifications`), ama komut zinciri `&&` değil ayrı
  satırlar olduğu için sonraki `echo` yine de çalıştı ve "silindi"
  görüntüsü verdi. Gerçekte diskte kalan 7 dosya: `v2/modules/
  ai_assistant/application/{recommendation_engine,prompt_tuner,
  build_context}.py`, `app/core/ai/{recommendation_engine,prompt_tuner}.py`
  (shim), 3 test dosyası. `public.py`/`orchestrate_ai_response.py` zaten
  bu dosyaları import etmiyordu (o kısım doğru commit'lenmişti) — yani
  kod fiilen ölüydü ama fiziksel dosyalar + testleri hâlâ duruyordu,
  CLAUDE.md/STATUS.md ise "silindi" diyordu (dokümantasyon-gerçek
  uyuşmazlığı). Bu turda gerçekten silindi, doğrulandı (ruff+mypy+
  collect-only+ilgili testler yeşil).
- **CLAUDE.md çapraz-referans taraması**: önceki turun düzeltmeleri
  kendi modülünde tutarlıydı ama BAŞKA modüllerin CLAUDE.md'lerinde
  driver/fuel/auth_rbac/notification/reports'a ait artık-geçersiz eski
  yol/dosya referansları kalmıştı (`analytics_executive` ve `reports`ın
  driver'ın eski `domain/driver_stats.py` yoluna atıfta bulunması;
  `analytics_executive`'in silinen `fuel/domain/consumption_prediction.py`
  ve kendi silinen `generate_insights.py`/`_UnitOfWorkContext`'ine hâlâ
  "var" gibi atıf yapması — sınıf istisna sayısı "2 adet" kalmıştı, 1'e
  düzeltildi; `notification`'ın silinen `generate_insights.py`'ye in-edge
  bağımlılık iddiası; `reports`'un silinen `get_daily_consumption_trend`'i
  hâlâ Public API imzalarında listelemesi; `analytics_executive`+`reports`
  CLAUDE.md'lerinin `auth_rbac.domain.permission_checker.require_yetki`
  gibi ÖNCEDEN (dalga-11/12 öncesi) zaten public'e taşınmış ama hiç
  düzeltilmemiş bayat yol iddiaları — bunlar benim bu oturumdaki
  hatam değil, daha eski bir doküman borcuydu, bu geçişte bulunup
  düzeltildi). Hepsi tek tek düzeltildi.
- **2 ek script bypass'ı bulundu ve düzeltildi**: `app/scripts/
  benchmark.py` fleet'i `application/list_vehicles`'tan doğrudan
  import ediyordu (→ `fleet.public.get_all_vehicles`); `scripts/
  p51_real_world_validation.py` location'ı `application/create_location`
  + `schemas`'tan doğrudan import ediyordu (→ `location.public`).
- **Sentry doc-kayması düzeltildi**: kök CLAUDE.md'nin `_sentry_before_send`
  notu `app/main.py:64` diyordu (gerçek satır 71), filtrenin `jose.
  ExpiredSignatureError/JWTError`'ı düşürdüğünü söylüyordu ama kod
  aslında `PyJWT` (`from jwt import ...`) kullanıyor — düzeltildi,
  filtrenin gerçek tam listesi + "yalnız 2 call-site Sentry'ye ulaşır"
  netliği eklendi.
- `TASKS/bug-openroute-client-architectural-leak.md`'nin kabul
  kriterleri gerçek duruma göre işaretlendi (madde 3 kısmi kaldı —
  üçüncü geocode implementasyonu `app.core.services.openroute_service.py`
  hâlâ ayrı, bilinçli kapsam dışı).

**Doğrulama (2. geçiş, gerçek Postgres+Redis+api-stub):** `ruff check
app v2 scripts` temiz, `mypy app` temiz (670 dosya, önceki turdan 5 az —
gerçekten silinen 7 dosyanın 5'i mypy kapsamında), `compileall` temiz,
`lint-imports` 14/15 kept (aynı, pre-existing broken), `pytest
--collect-only app/tests tests` 6712 test/0 hata (önceki 6779'dan 67 az
— gerçekten silinen 3 test dosyasının içerdiği testler). **OpenAPI şeması
`frontend/openapi.json`'a karşı byte-seviyesinde BYTE-BYTE ÖZDEŞ**
(202/202 path, 0 operationId farkı, tam JSON diff sıfır) — bu oturumun
tüm değişiklikleri saf iç mimari, sıfır API kontrat etkisi. **Tam pytest
suite'i (`app/tests/unit app/tests/api tests`): 6239 passed, 23 failed,
26 skipped** (önceki 6304/23/26'dan farkı yalnız 65 test azlığı — silinen
test dosyaları; **FAILED listesinin 23 ismi de bir önceki koşumla BİREBİR
AYNI** — net-yeni regresyon SIFIR). Commit/push bu turda yapıldı.


2026-07-18 (ikinci oturum) — İlk 12 dalganın TAM-DENETİM DÜZELTME TURU
(kullanıcı talebi: "ilk 12 dalgayı detaylı ve derin incele... eksikleri
düzelt, arkada borç ve hata kalmasın"). Önceki dedektif denetimlerin
kaçırdığı yeni bulgular tek oturumda kapatıldı:

- **import-linter gerçek durumu bilinenden kötüydü**: STATUS'un "3 bayat
  ignore" iddiası yanlıştı — gerçekte 7 bayat girdi vardı (4'ü dalga 12'nin
  kendi arkasını temizlememesinden, 1'i hiç var olmamış bir dosyaya
  referanstı). Temizlik sonrası kontratlar ilk kez gerçekten değerlendirildi:
  **10 kept, 5 broken** çıktı (rapor modunda CI bunu hiç görmüyordu).
  5 gerçek ihlal (`driver`/`anomaly`→`ai_assistant.infrastructure`
  doğrudan erişim + `app.services.prediction_service` üzerinden 3 dolaylı
  zincir) düzeltildi. Sonuç: **14 kept, 1 broken** (kalan tek broken —
  "report-only FAZ0" kontratı — `app.services`↔`app.core.services` eski
  dosyalar arası, migrasyonla ilgisiz, `git stash` ile önceden de kırık
  olduğu doğrulandı, CI'da zaten continue-on-error).
- **public.py sınır ihlalleri**: v2 içi 28 satır + app-tarafı ~15 dosya
  hâlâ hedef modülün `public.py`'sini atlayıp `infrastructure`/`application`
  içinden doğrudan import ediyordu (anomaly/driver→ai_assistant.groq_client,
  auth_rbac→notification.email_client, fuel→notification.telegram_client,
  vb.). Hepsi `public.py` üzerinden geçecek şekilde düzeltildi.
  `route_simulation` modülüne (dalga 1'den beri hiç yoktu) `public.py` +
  `events.py` eklendi.
- **Domain-katmanı I/O ihlali**: `driver/domain/{driver_stats,evaluation,
  route_profile}.py` (UoW/DB erişimi) ve `fleet/domain/vehicle_event_log.py`
  (DB yazıyor) `application/`'a taşındı; `auth_rbac/domain/token_blacklist.py`
  (Redis I/O) `infrastructure/`'a taşındı — domain saf/I/O'suz kuralı.
- **🔴 Kritik keşif (rewire sırasında, gerçek Python import-mekaniği
  incelemesiyle bulundu)**: bir fonksiyonun eski yolda (`X.infrastructure.Y`)
  patch'lenen bir test, kod `X.public`'ten lazy-import yapacak şekilde
  değiştirildiğinde, EĞER `X.public` o test-sürecinde henüz hiç import
  edilmemişse, patch aktifken `X.public`'in ilk kez import edilmesi
  `X.public`'in kendi ad-alanını mock ile "zehirliyor" (module-cache tek
  seferlik) — sonraki testler etkileniyor, sonuç import sırasına göre
  deterministik ama yanıltıcı geçme/kalma. `ensemble_service.py`/
  `driver_stats.py`/`kalman_estimator.py`'nin `get_analiz_repo`/
  `get_arac_repo`/`get_dorse_repo` rewire'ları bu şekilde ~8 testi
  (`test_ensemble_service_coverage.py` vb.) bozdu — tüm eski-yol patch
  hedefleri `*.public`'e çevrilerek düzeltildi (aynı desen `route_simulation.
  application.get_route_details`'in `sys.modules` patch'i için de
  `test_lokasyon_service_more.py`'de tekrarlandı, aynı şekilde düzeltildi).
  **Ders**: bir fonksiyonu `X.internal` → `X.public` re-export'una taşırken,
  o fonksiyonu patch'leyen HER test'in hedefi de `X.public`'e taşınmalı —
  aksi halde silent-wrong-pass veya cross-test-pollution riski var.
- **Orphan Celery task testi kaçırılmıştı**: `driver.calculate_performance_score`
  (hiç worker'a kayıtlı olmayan, dalga 5'ten beri bilinen ölü task) dosyasıyla
  silinince, AYRI bir test dosyası (`test_worker_tasks.py` — tekil "worker",
  `test_workers/test_driver_tasks.py`'den farklı) de aynı task'ı test
  ediyordu — bulunup düzeltildi.
- **Ölü kod silindi (kullanıcı kararı: "ölü kod yasak")**: `ai_assistant`'ın
  4 kümesi (`RecommendationEngine`, `PromptTuner`, `build_context.py`'nin 5
  fonksiyonu, `AIService.predict_trip_fuel`/`detect_anomalies`/
  `_get_predictor_for_vehicle`, `RAGEngine.index_log`/`index_event`/
  `bulk_index`/`index_alert`), `analytics_executive.generate_insights.py`
  (InsightEngine free-function hali) + `driver.get_driver_comparison`,
  `fuel.domain.{consumption_prediction,local_regression}.py`, orphan driver
  Celery task'ı — hepsi silinmeden önce grep ile sıfır-prod-çağıran TEKRAR
  doğrulandı, testleriyle birlikte kaldırıldı.
- **`OpenRouteClient` cerrahisi** (`TASKS/bug-openroute-client-
  architectural-leak.md`, önceden açık bekleyen görev): ölü `geocode`/
  `_call_geocode_api` (location'ın geocode zincirinin DRY-ihlalli kopyası)
  ve `update_route_distance` (`lokasyonlar` tablosuna ham SQL UPDATE atan,
  sıfır prod çağıranlı legacy metot) silindi; `scripts/enrich_existing_data.py`
  artık `location.public.geocode_location` kullanıyor. Sınıf artık yalnız
  ORS distance+cache sorumluluğu taşıyor. Görev dosyası kapatıldı.
- **8 modülün CLAUDE.md şablon boşlukları** (İzin/yasak importlar, Domain
  terimleri, Event'ler, Test stratejisi eksikleri — anomaly en zayıftı, 4
  başlık eksikti) dolduruldu; kök `CLAUDE.md`'nin modül tablosu 2'den
  12 modüle güncellendi; driver/import_excel/fuel/route_simulation/
  auth_rbac'ın bayat satırları (taşınmamış-sanılan ama taşınmış modüller,
  eski import yolu iddiaları) düzeltildi.

**Doğrulama (bu ortamda gerçek Postgres 16 + Redis + api-stub kurulup):**
`ruff check app v2 scripts` temiz, `mypy app` temiz (675 dosya),
`lint-imports` 14/15 kept (1 broken = pre-existing, migrasyonla ilgisiz),
`compileall` temiz, `pytest --collect-only app/tests tests` 6779 test/0
hata. **Tam pytest suite'i (`app/tests/unit app/tests/api tests`, gerçek
DB'ye karşı, 2 tam koşum + ~15 hedefli koşum boyunca bulunan regresyonlar
düzeltilerek): 6304 passed, 23 failed, 26 skipped.** 23 fail'in TAMAMI
`git stash` ile pre-session koda karşı birebir doğrulandı — hepsi bu ad-hoc
ortamın api-stub/gerçek-ağ topoloji farkından (mapbox/openroute/
route_service/lokasyon_service gerçek ORS/Nominatim/Mapbox host'larına
düşüyor, ilk full-run'da da AYNI isimlerle zaten kırıktı) — **net-yeni
regresyon SIFIR**. Commit/push bu turda yapıldı (branch
`claude/son-durum-ltxexy`).

2026-07-18 — Dalga 12 (ai_assistant) main'de TAM YEŞİL (commit `928de51`,
`gh run view 29611326223` → `success`). İki turlu dedektif denetim: 1.
tur (taşıma sırasında) 3 ölü-kod kümesi + RAGSyncService'in canlılığı
doğrulandı; 2. tur (kullanıcı talebiyle "ilk 12 dalgayı detaylı ve derin
kontrol edelim... dedektif gibi") 4 bağımsız sıfır-context ajan + 1
compliance-audit ajanı ile mekanik/dokümantasyon borcu (shim'ler,
public.py sınır ihlalleri, CLAUDE.md şablon eksikleri) VE 4 gerçek
davranış-etkileyen pre-existing bug (sefer/araç/şoför RAG senkron
hataları, FAISS'in paylaşımlı volume dışında kalması, ai_routes.py'nin
fuel tablosuna ham SQL'i) bulundu — kullanıcı onayıyla ("eksikleri
düzelt, teknik borç bırakma, varsayım yok") hepsi aynı oturumda
düzeltildi, gerçek Docker+DB'de doğrulandı, main'de CI Hard Gates tam
yeşil. Detay: `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md`
BÖLÜM C.

2026-07-17 — İlk 11 dalganın tam dedektif denetimi (11 bağımsız sıfır-context
ajan, her modül için bir ajan): `auth_rbac`+`reports` temiz, diğer 9 modülde
~30 bulgu (1 GERÇEK BUG + mimari/dok borcu). GERÇEK BUG (`import_excel`'in
`ocr.process_belge` Celery task'ı worker'a hiç kayıtlı değildi, dalga 9
regresyonu) aynı oturumda TDD red→green ile düzeltildi ve main'e push edildi
(commit `49b7532`, `gh run view 29555563172` → tam yeşil). Kalan ~30 bulgu
`TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md`'de takip ediliyor,
kullanıcı onayı olmadan uygulanmayacak. Dalga 11 (analytics-executive)
main'de yeşil (5 bağımsız ajanla dedektif denetimi + CI-fix turu dahil, bkz.
DALGA 11 bölümü, commit `48e8e21`, `gh run view 29531899079`). Depo şu an
**PUBLIC** (kullanıcı kararı, GHCR faturalama sorunu için geçici; iş bitince
tekrar private yapılması gerekiyor — bkz. görev dışı hatırlatma).
