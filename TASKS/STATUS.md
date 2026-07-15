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
| **FAZ1** — Kod sınırları (17 kalem) | 🟡 DEVAM EDİYOR — 7/17 kalem tamam | Dalga 1 (location+route-simulation) main'de yeşil; dalga 2 (notification) main'de yeşil; dalga 3 (fleet) main'de yeşil; dalga 4 (fuel) main'de yeşil; dalga 5 (driver) main'de yeşil; dalga 6 (auth-rbac) main'de yeşil; dalga 8 (anomaly) main'de yeşil; sıradaki: dalga 9 (import-excel), yeni oturumda |
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

## Son güncelleme
2026-07-15 — **FAZ1 dalga 8 (anomaly) TAMAMLANDI, main tam yeşil** (son
commit `7e2a364`, CI Hard Gates `success`). OTURUM HİJYENİ: bu oturum
kapatılıyor, dalga 9 (import-excel) yeni oturumda `TASKS/modules/import-excel.md`
okunarak, kullanıcı onayı istenerek başlar. Depo şu an **PUBLIC** (kullanıcı
kararı, GHCR faturalama sorunu için geçici; iş bitince tekrar private
yapılması gerekiyor — bkz. görev dışı hatırlatma).
