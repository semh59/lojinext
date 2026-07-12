# Modül: route_simulation

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

İki koordinat çifti arası rota geometrisi + segment-bazlı fizik/yakıt
simülasyonu. İki sağlayıcı: OpenRouteService (ORS, birincil) ve Mapbox
Directions (hibrit fallback + segment-mode kaynağı). `route_paths`,
`route_simulations`, `route_segments` tablolarının tek sahibi.

NE YAPMAZ: lokasyon CRUD'u (location modülünün işi), yakıt tahmin ML
modeli (prediction_ml — bu modül yalnız `PhysicsBasedFuelPredictor`'ı
tüketir), hava durumu (weather_service.py henüz bu modüle taşınmadı).

**DURUM (dürüst, dalga 1 sonu itibarıyla)**: modül kod-tarafında TAM
değil. `application/`+`api/`+`domain/`+`infrastructure/` dolu ama
`public.py`/`events.py`/`schemas.py` YOK — diğer modüller (location) şu an
`application/`'dan doğrudan import ediyor (mimari borç, dokümante).
`weather_service.py`, `route_validator.py`, `openroute_service.py`
(geocode wrapper), `route_calibration_service.py`, `admin_calibration.py`
endpoint'i, `route_similarity.py` henüz v2'ye taşınmadı — eski `app/`
yolunda kalıyor.

## Public API (henüz public.py YOK — application/ dosyalarından doğrudan import)

```python
# application/get_route_details.py
RouteService, get_route_service()
  .get_route_details(start_coords, end_coords, use_cache=True, include_details=False) -> dict
  .analyze_route_difficulty(ascent, descent, distance_km) -> str

# application/simulate_route.py
RouteSimulator, get_route_simulator()
  .simulate(cikis_lon, cikis_lat, varis_lon, varis_lat, ton=15.0, arac_yasi=5,
            target_length_km=0.5, vehicle=None) -> Optional[SimulationResult]

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
RouteRepository, get_route_repo(session=None)

# api/route_routes.py
router  # POST /analyze, POST /simulate, GET /simulate/{id}
```

## Yayınladığı / dinlediği event'ler

Yok — bu modül event-bus üzerinden hiçbir şey publish/subscribe etmiyor
(senkron çağrı + DB persist üzerinden konuşuyor).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **location** (senkron): `LokasyonHydrator` (location/domain/hydration.py)
  bu modülün `MapboxClient`/`OpenMeteoElevationClient`/`resample_segments`'ini
  doğrudan import eder — sefer create anında güncel trafik/elevation lazım,
  event-gecikmesi kabul edilemez.
- **prediction_ml** (senkron, geçici): `segment_simulator.py` ve
  `simulate_route.py` `app.core.ml.physics_fuel_predictor`'ı (VehicleSpecs,
  PhysicsBasedFuelPredictor) henüz eski yoldan import ediyor — prediction_ml
  v2'ye taşınınca güncellenecek.
- **route_validator/openroute_service** (senkron, geçici): `RouteService`
  ve `OpenRouteClient` `app.core.services.route_validator.RouteValidator`'ı
  ve `app.core.services.integration_secrets`'i eski yoldan kullanıyor.

## Şema & tablo sahipliği

`route_paths` (RouteRepository — ORS cache), `route_simulations` +
`route_segments` (segment-mode simülasyon persist, `/simulate` endpoint'i).
Kolon adları `total_km`/`total_l`/`total_eta_sec`/`avg_l_per_100km` —
`distance_km`/`duration_min` DEĞİL (bkz. root CLAUDE.md gotcha'sı).

## Modüle özel iş kuralları & gotcha'lar

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
- **`RouteService.get_route_details`'te ORS→Mapbox hibrit fallback**:
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
- Free-function/class-method `unittest.mock.patch` hedefi: modül-seviyesi
  importlar için TÜKETEN modül (`v2.modules.route_simulation.api.route_routes.RouteService`
  gibi); fonksiyon-içi (inline) importlar için KAYNAK modül
  (`v2.modules.route_simulation.application.get_route_details.get_prediction_service`
  gibi — `get_prediction_service` orada her çağrıda taze import edilir).
