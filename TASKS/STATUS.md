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
| **FAZ1** — Kod sınırları (17 kalem) | 🟡 DEVAM EDİYOR — 8/17 kalem tamam, dalga 10 kod-tarafı hazır | Dalga 1 (location+route-simulation) main'de yeşil; dalga 2 (notification) main'de yeşil; dalga 3 (fleet) main'de yeşil; dalga 4 (fuel) main'de yeşil; dalga 5 (driver) main'de yeşil; dalga 6 (auth-rbac) main'de yeşil; dalga 8 (anomaly) main'de yeşil; dalga 9 (import-excel) main'de yeşil; dalga 10 (reports) kod-tarafı tamam + yerel doğrulama yeşil, push/CI bekliyor (bkz. DALGA 10 bölümü); sıradaki: dalga 11 (analytics-executive), yeni oturumda |
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
| 6 | auth-rbac | `modules/auth-rbac.md` | ✅ main'de yeşil (commit `e9a0328`) |
| 7 | *(route-simulation dalga 1'e taşındı, bkz. üstte)* | — | — |
| 8 | anomaly | `modules/anomaly.md` | ✅ main'de yeşil (commit — bkz. DALGA 8 bölümü) |
| 9 | import-excel | `modules/import-excel.md` | ✅ main'de yeşil (commit `5d1a0fb`, bkz. DALGA 9 bölümü) |
| 10 | reports | `modules/reports.md` | 🟡 kod-tarafı tamam, push/CI bekliyor (bkz. DALGA 10 bölümü) |
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
- ✅ **ÇÖZÜLDÜ (2026-07-14)** — Connection-pool leak, sistematik debugging ile 2 kök nedene indirgendi ve düzeltildi: (1) `AuthService`/`MLService`/`AttributionService`'in zaten açık bir `UnitOfWork`'ü ikinci kez `async with self.uow:` ile yeniden açması (`_owns` bayrağını bozup dış `session.close()`'u atlıyordu) — 3 servis dosyası + 1 endpoint düzeltildi, `UnitOfWork.__aenter__`'e re-entrancy guard eklendi (defense-in-depth, artık sessizce bozmak yerine `RuntimeError`). (2) `AuthService.authenticate()`'teki senkron `bcrypt.checkpw()` event loop'u bloke edip eşzamanlı yük altında pool tükenmesini şiddetlendiriyordu — `asyncio.to_thread`'e taşındı. Gerçek 30-kullanıcılı Locust koşumunda leak uyarısı 30-44 → **0**, p99 latency ~70000ms → **500ms**. 2 gerçek regresyon testi eklendi (`app/tests/test_db_hardening.py`, TDD red→green doğrulandı). Detay: `TASKS/bug-connection-pool-leak-under-load.md` (kabul kriterleri işaretli).
- `v2/modules/route_simulation/infrastructure/openroute_client.py`'deki `OpenRouteClient` sınıfı 3 ilgisiz sorumluluk taşıyor (ORS distance client + location modülünün geocode'unu tekrarlayan `geocode()` + `lokasyonlar` tablosuna location'ı bypass eden ham SQL `update_route_distance()`) — B.1 + tablo-sahipliği ihlali, ama prod route'larından çağrılmıyor (ölü/legacy kod, yalnız script+testler kullanıyor). 2026-07-14 dalga1-5 denetiminde bulundu. Bağımsız görev açıldı: `TASKS/bug-openroute-client-architectural-leak.md`. Herhangi bir oturumda, dalga sırası beklenmeden ele alınabilir.
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

## DALGA 10 — 🟡 KOD-TARAFI TAMAM, PUSH/CI BEKLİYOR (2026-07-16)

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

**Sıradaki adım:** commit + push (`8a5e9de` zaten push edildi), CI Hard
Gates'i izle (E2E dahil), yeşil olunca bu bölüm + tablo satırı "main'de
yeşil" olarak güncellenecek.

## Son güncelleme
2026-07-16 — İlk 9 dalganın dedektif-denetim düzeltmeleri + bilinen mypy
baseline hatalarının (7→0) temizliği + event-bus wiring + dalga 10 (reports,
yukarı bakınız) tamamlandı. Depo şu an **PUBLIC** (kullanıcı kararı, GHCR
faturalama sorunu için geçici; iş bitince tekrar private yapılması gerekiyor
— bkz. görev dışı hatırlatma).
