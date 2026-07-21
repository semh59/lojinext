# Modül: route_simulation

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

İki koordinat çifti arası rota geometrisi + segment-bazlı fizik/yakıt
simülasyonu. İki sağlayıcı: OpenRouteService (ORS, birincil) ve Mapbox
Directions (hibrit fallback + segment-mode kaynağı). `route_paths`,
`route_simulations`, `route_segments` tablolarının tek sahibi.

NE YAPMAZ: lokasyon CRUD'u (location modülünün işi), yakıt tahmin ML
modeli (prediction_ml — bu modül yalnız `v2.modules.prediction_ml.public.
PhysicsBasedFuelPredictor`'ı tüketir), hava durumu (weather_service.py
henüz bu modüle taşınmadı).

**DURUM (dürüst, 2026-07-18 tam-denetim düzeltmesi sonrası)**:
`application/`+`api/`+`domain/`+`infrastructure/` dolu; `public.py` ve
`events.py` 2026-07-18'de eklendi — diğer modüller (location) ve app-tarafı
tüketiciler (`sefer_fuel_estimator.py`, scriptler) artık `public.py`
üzerinden import ediyor (eski "public'i yok" borcu kapandı). `schemas.py`
hâlâ yok (route şemaları api/route_routes.py içinde — modülün dış şema
tüketicisi yok).
`weather_service.py`, `route_validator.py`, `openroute_service.py`
(geocode wrapper), `route_calibration_service.py`, `admin_calibration.py`
endpoint'i henüz v2'ye taşınmadı — eski `app/` yolunda kalıyor.
`route_similarity.py` bu modüle AİT DEĞİLDİ — task dosyasının stale
envanterinde route_simulation'a bağlıymış gibi görünse de gerçekte
prediction_ml'in bir parçası (`domain/route_similarity.py`, dalga 13'te
taşındı, ai_assistant'ın `plan_trip.py`'si kullanıyor).

## Public API (public.py imzaları — 2026-07-18'den beri VAR)

```python
# application/get_route_details.py — TEK use-case, free function (B.1 uyumlu)
get_route_details(start_coords, end_coords, use_cache=True, include_details=False) -> dict

# application/get_route_difficulty.py
get_route_difficulty(ascent, descent, distance_km) -> str

# application/simulate_route.py
RouteSimulator, get_route_simulator()
  .simulate(cikis_lon, cikis_lat, varis_lon, varis_lat, ton=15.0, arac_yasi=5,
            target_length_km=0.5, vehicle=None) -> Optional[SimulationResult]
# (Sınıf olarak kaldı — TEK use-case/tek pipeline, LokasyonHydrator ile aynı
# gerekçe: constructor yalnız mapbox_client/elevation_client DI'sini tutuyor.)

# application/create_route_simulation.py (dalga-1-6+8 B.1 dedektif denetiminde eklendi, 2026-07-15)
create_route_simulation(db, simulator, *, lokasyon_id, arac_id, cikis_lon, cikis_lat,
                         varis_lon, varis_lat, ton, arac_yasi, segment_length_m,
                         current_user_id) -> RouteSimulation  # segments eager-loaded
get_route_simulation_by_id(db, simulation_id) -> RouteSimulation  # raises 404

# domain/route_geometry.py — RouteService'ten ayrıştırılmış, hiçbir prod kod
# çağırmıyor (yalnız kendi testleri); route_analyzer.py'nin kendi haversine'i
# asıl canlı yolda kullanılan.
haversine(lon1, lat1, lon2, lat2) -> float
segment_distance(coordinates, start_idx, end_idx) -> float
analyze_elevation_profile(geometry) -> dict

# domain/
PolylineDecoder.decode(polyline_str) -> list[tuple[float, float]]
RouteAnalyzer / route_analyzer.analyze_segments(geometry_points, extras, reference_distance_m) -> dict
GradeClass, assign_grade_class(grade_pct) -> GradeClass
SegmentInput, SegmentOutput, SegmentSummary, simulate_segment(), simulate_route()
resample_segments(segments, coords, target_length_km=0.5)

# infrastructure/
MapboxClient, get_mapbox_client()
OpenRouteClient, get_route_client()
OpenMeteoElevationClient, get_elevation_client()
RouteRepository, get_route_repo(session=None)          # route_paths (ORS cache)
SimulationRepository(session=db)                        # route_simulations + route_segments

# api/route_routes.py
router  # POST /analyze, POST /simulate, GET /simulate/{id}
```

**Önemli**: `RouteService` sınıfı YOK (2026-07-13'te bölündü — STATUS.md'nin
"v2'de bir-dosya-bir-use-case istisnası yok" kararıyla uyumlu hâle
getirildi). `container.route_service`/`import_service.route_service`
property'leri de hiçbir prod kod tarafından çağrılmadığı için kaldırıldı
(dead code).

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar)

1. **`RouteSimulator`** (`application/simulate_route.py`) — tek-cohesive
   pipeline: Mapbox Directions → segment_resampler → elevation → simulate,
   constructor-injected client bağımlılığı (Mapbox/Open-Meteo client'ları).
   CRUD-benzeri bir servis değil, `LokasyonHydrator`/`DriverCoachingEngine`
   ile aynı gerekçe kategorisi.
2. **`OpenRouteClient`** (`infrastructure/openroute_client.py`) —
   ✅ **2026-07-18'de temizlendi** (`TASKS/
   bug-openroute-client-architectural-leak.md`): ölü `geocode`/
   `_call_geocode_api` (location'ın geocode zincirinin DRY-ihlalli
   kopyası) ve `update_route_distance` (`lokasyonlar` tablosuna —
   location'ın tek sahipliği — ham SQL UPDATE atan, sıfır prod çağıranlı
   legacy metot) SİLİNDİ; `scripts/enrich_existing_data.py` artık
   `location.public.geocode_location`'ı kullanıyor. Sınıf artık yalnız
   ORS distance + cache sorumluluğu taşıyor (Redis/in-memory cache
   metotları `get_distance`'ın parçası, ayrı sorumluluk değil).

## Yayınladığı / dinlediği event'ler

Yok — bu modül event-bus üzerinden hiçbir şey publish/subscribe etmiyor
(senkron çağrı + DB persist üzerinden konuşuyor).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **location** (senkron): `LokasyonHydrator` (location/application/hydration.py)
  bu modülün `MapboxClient`/`OpenMeteoElevationClient`/`resample_segments`'ini
  doğrudan import eder — sefer create anında güncel trafik/elevation lazım,
  event-gecikmesi kabul edilemez.
- **prediction_ml** (taşındı, dalga 13): `domain/segment_simulator.py` ve
  `application/simulate_route.py`/`create_route_simulation.py`
  `v2.modules.prediction_ml.public`'ten `VehicleSpecs`/`PhysicsBasedFuelPredictor`/
  `FuelPrediction` alır (2026-07-18: eski `app.core.ml.physics_fuel_predictor`
  bypass'ı kapandı). `get_route_details.py` de `public.get_prediction_service`
  kullanıyor.
- **route_validator** (senkron, geçici): `RouteService` ve `OpenRouteClient`
  `app.core.services.route_validator.RouteValidator`'ı eski yoldan
  kullanıyor (henüz v2'ye taşınmadı).
- **admin_platform** (taşındı, dalga 15, ileri yön): `OpenRouteClient`/
  `MapboxClient` `v2.modules.admin_platform.public.get_integration_secret`
  kullanıyor (eskiden `app.core.services.integration_secrets`'ten,
  admin_platform dalgasında güncellendi).

## Şema & tablo sahipliği

`route_paths` (RouteRepository — ORS cache), `route_simulations` +
`route_segments` (segment-mode simülasyon persist, `/simulate` endpoint'i).
Kolon adları `total_km`/`total_l`/`total_eta_sec`/`avg_l_per_100km` —
`distance_km`/`duration_min` DEĞİL (bkz. root CLAUDE.md gotcha'sı).

## Modüle özel iş kuralları & gotcha'lar

- ✅ **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu, `TASKS/bug-route-layer-bypasses-application.md` sınıfının en
  büyük tekrarı)** — `api/route_routes.py::simulate_route`/
  `get_route_simulation` ~90 satırlık ORM persist/query mantığını
  (lokasyon/araç çözümü, `RouteSimulation`/`RouteSegment` INSERT,
  `selectinload` eager-reload) route içinde doğrudan çalıştırıyordu —
  `route_simulations`/`route_segments` o zamana kadar hiçbir repository'ye
  sahip değildi. Yeni `infrastructure/simulation_repository.py`
  (`SimulationRepository`) + `application/create_route_simulation.py`.
  Eager-reload deseni (MissingGreenlet gotcha'sı — commit-sonrası lazy
  `sim.segments` erişimi async engine altında patlıyordu) BİREBİR
  korundu. Mekanik taşıma, davranış değişikliği yok.
- **Mapbox `road_class` annotation YOK**: Directions API'de `road_class`
  parametre olarak istenirse 422 döner. Bunun yerine
  `step.intersections[*].mapbox_streets_v8.class`'tan
  `_reconcile_segment_road_classes` ile reconcile edilir (~99.9% doluluk).
- **Mapbox SecretStr maskeleme bug-fix'i**: `settings.MAPBOX_API_KEY`
  `SecretStr` — doğrudan URL param'a koyulursa `str()` "**********" üretir.
  `MapboxClient.__init__` `.get_secret_value()` ile çözer (hem SecretStr
  hem plain str güvenli).
- **Open-Meteo/Mapbox 429 retry pattern'i**: `Retry-After` header'ı varsa
  onu kullan, yoksa 1.5s bekle, TEK retry. 5xx/network hataları
  `with_async_retry` (3 deneme exponential backoff) kapsar; 4xx anında
  None/exception döner, retry boşa gitmez.
- **Directions cache 24h TTL** (`_MAPBOX_DIRECTIONS_CACHE_TTL_S`): traffic
  değişken olduğu için elevation'ın (30 gün TTL) aksine kısa tutulur.
- **`get_route_details`'te ORS→Mapbox hibrit fallback**:
  `RouteValidator.validate_and_correct` anomali (`is_corrected=True`)
  bulursa VE `settings.MAPBOX_API_KEY` varsa Mapbox'a geçilir; delta
  eşikleri (`ROUTE_DIST_DELTA_*_PCT`) aşılırsa log uyarısı (fail değil).
- **`RouteAnalyzer.analyze_segments`**: repodaki en karmaşık fonksiyon
  (CC≈56) — ORS'in steepness/waycategory/waytype extras'ını tek sweep'te
  kesiştirip granular+aggregate+ratio+distribution istatistikleri üretir.
  Değiştirmeden önce `app/tests/unit/test_route_analyzer_coverage.py`'yi
  tam okuyun (residual-distribution rounding mantığı hassas).

## Test stratejisi

- `app/tests/unit/test_route_analyzer*.py`, `test_segment_simulator.py`,
  `test_segment_resampler.py`, `test_mapbox_*.py`, `test_open_meteo_*.py`,
  `test_openroute_client*.py`, `test_route_simulator.py`,
  `test_route_service*.py` — 0-mock, çoğu `pytest.mark.integration` +
  `TEST_DATABASE_URL` + `docker compose --profile test up -d api-stub`
  gerektirir (gerçek HTTP round-trip, sentinel koordinat tekniğiyle
  hata senaryosu seçimi — bkz. `api_stub/main.py`).
- `app/tests/api/test_routes_*.py`, `test_locations_*.py` (route-info kısmı) —
  endpoint testleri.
- Free-function `unittest.mock.patch` hedefi: modül-seviyesi importlar için
  TÜKETEN modül (`v2.modules.route_simulation.api.route_routes.get_route_details`
  gibi); fonksiyon-içi (inline) importlar için KAYNAK modül
  (`v2.modules.route_simulation.application.get_route_details.get_prediction_service`
  gibi — `get_prediction_service` orada her çağrıda taze import edilir).

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-route_simulation` kontratı:
`application/` katmanı diğer modüllerin yalnız `public`/`events`'ini
import edebilir (2026-07-18'den beri KEPT). Diğer modüller bu modüle
yalnız `v2.modules.route_simulation.public` üzerinden erişir. Geçici
istisnalar (eski `app/` yolları — `weather_service`, `openroute_service`)
kontratın ignore listesinde dokümante; `prediction_ml` 2026-07-18'de
taşındı, bu modül artık ona `public.py` üzerinden erişiyor (istisna değil).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`rota`=route, `güzergah`=route/itinerary, `eğim`=grade/slope,
`tırmanış`=ascent, `iniş`=descent, `kesim/segment`=segment,
`benzetim`=simulation, `rakım`=elevation, `mesafe`=distance,
`zorluk`=difficulty.
