# Modül: location

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Lokasyon/güzergah kayıtlarının CRUD'u, geocoding (adres → koordinat), ve
güzergah "hidrasyon"u (Mapbox+Open-Meteo'dan 500m bucket segment haritası
çıkarma). `lokasyonlar` + `lokasyon_segments` tablolarının tek sahibi.

NE YAPMAZ: rota simülasyonu/fizik hesabı (route_simulation modülünün işi —
bu modül yalnız route_simulation'ın `get_route_details`/`RouteSimulator`
sonuçlarını tüketir), yakıt tahmini (prediction_ml), sefer oluşturma (trip).

## Public API (public.py imzaları)

```python
create_location(repo, data: LokasyonCreate, existing_index=None) -> int
update_location(repo, lokasyon_id: int, data: LokasyonUpdate) -> bool
delete_location(repo, lokasyon_id: int) -> bool          # smart delete: aktif→pasif→hard
list_locations(repo, skip=0, limit=100, aktif_only=True, zorluk=None, search=None) -> dict
analyze_location_route(repo, lokasyon_id: int) -> dict
geocode_location(q: str, limit=5) -> list[dict]           # ORS → Nominatim → offline fallback
                                                            # (infrastructure/openroute_geocode_client.py — 2026-07-22'de
                                                            # app/core/services/openroute_service.py'den buraya taşındı)

route_key(cikis, varis) -> tuple[str, str]                 # Türkçe-normalize dict key
normalize_turkish_title(s) -> str                           # İ/ı bug-fix'li title-case

LokasyonHydrator, get_lokasyon_hydrator()                   # application/hydration.py
LokasyonRepository, get_lokasyon_repo(session=None)

get_location_stats(repo) -> dict
get_stale_locations(repo, days: int) -> list[dict]
get_location_by_id(repo, lokasyon_id: int, include_inactive=False) -> dict | None
search_locations_by_route(repo, cikis: str, varis: str) -> list[Lokasyon]
get_unique_location_names(repo) -> list[str]
get_all_locations(repo) -> list[dict]
hydrate_location(repo, hydrator: LokasyonHydrator, lokasyon_id: int) -> dict
get_location_segments(repo, lokasyon_id: int) -> dict | None
```

**Önemli**: `LokasyonService` sınıfı YOK. Her use-case bağımsız bir
fonksiyon, caller kendi `UnitOfWork`'ünden aldığı `LokasyonRepository`'yi
(`uow.lokasyon_repo`) parametre olarak geçirir.

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalanlar)

1. **`LokasyonHydrator`** (`application/hydration.py` — 2026-07-17'de
   `domain/`'dan taşındı, gerçek Mapbox+Open-Meteo network çağrısı + ORM
   state mutasyonu yapıyor, "domain/ = I/O yok" kuralına aykırıydı, bkz.
   `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md` madde 1) —
   constructor-injected client bağımlılığı (Mapbox/Open-Meteo client'ları),
   `RouteSimulator` ile aynı gerekçe kategorisi.

## Yayınladığı / dinlediği event'ler (events.py DTO'ları)

`LOKASYON_ADDED`, `LOKASYON_UPDATED`, `LOKASYON_DELETED` — `@publishes(...)`
decorator'ı `create_location`/`update_location`/`delete_location` üzerinde
var ama **repo-genelinde ölü kod**: hiçbir yerde `event_bus.publish(...)`
çağrısı yok, `_publishes` attribute'u okunmuyor. Bu modülün getirdiği bir
regresyon değil — pre-existing bir davranış boşluğu, dokümante edildi.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **route_simulation** (senkron): `analyze_location_route`, `/route-info`
  endpoint'i ve `application/hydration.py` route_simulation'a artık
  `v2.modules.route_simulation.public` üzerinden erişir (`get_route_details`,
  `resample_segments`, `MapboxClient`, `OpenMeteoElevationClient`).
  2026-07-18: route_simulation'a public.py eklendi — eski "public'i yok,
  application/'dan doğrudan import" borcu kapandı.
- **prediction_ml** (taşındı, dalga 13): `analyze_location_route`'un
  `_apply_baseline_fuel_estimate` yardımcı fonksiyonu 2026-07-18'den beri
  `v2.modules.prediction_ml.public.PhysicsBasedFuelPredictor`/`RouteConditions`
  üzerinden erişir (eski `app.core.ml.physics_fuel_predictor` bypass'ı kapandı).
- **admin_platform** (taşındı, 2026-07-22): `infrastructure/
  openroute_geocode_client.py`'nin `_resolve_api_key()`'i (DB-configured
  ORS anahtarı .env fallback'inden önceliklidir) `v2.modules.admin_platform.
  public.get_integration_secret`'i çağırıyor — dosya `app/core/services/
  openroute_service.py`'den bu modüle taşındığında ZATEN var olan bir
  bağımlılık, taşımayla yeni oluşmadı.

## Şema & tablo sahipliği + çapraz-şema FK kontratları

`lokasyonlar`, `lokasyon_segments` (FK: `lokasyon_segments.lokasyon_id` →
`lokasyonlar.id`, cascade delete-orphan). `seferler.guzergah_id` bu
tabloya çapraz-modül FK (trip modülü tarafında).

## İzin verilen / yasak import'lar (import-linter özeti)

`public-surface-only-location` kontratı aktif/blocking (KEPT) — diğer
modüller yalnız `v2.modules.location.public`/`.events`'i import eder;
`application/`/`domain/`/`infrastructure/`'a doğrudan erişim yasak.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`lokasyon`=location, `guzergah`=route, `cikis_yeri`/`varis_yeri`=origin/destination,
`mesafe_km`=distance_km, `zorluk`=difficulty, `aktif`=active.

## Modüle özel iş kuralları & gotcha'lar

- ✅ **DÜZELTİLDİ (2026-07-15/16, ilk 9 dalganın tam-yeniden dedektif
  denetiminde bulundu)** — `api/location_routes.py`'nin 8 handler'ı
  (`get_location_stats`/`get_stale_locations`/`get_location_by_id`/
  `search_locations_by_route`/`get_unique_location_names`/`get_all_locations`/
  `hydrate_location`/`get_location_segments`) `application/`'ı atlayıp
  repo/UoW'a doğrudan erişiyordu — 8 yeni `application/` use-case dosyasına
  taşındı. `get_location_stats`/`get_stale_locations` isimli 2 yeni import
  route handler'larıyla AYNI İSİM taşıyordu (modül-seviyesi gölgeleme riski)
  — `as get_location_stats_usecase`/`as get_stale_locations_usecase`
  alias'ıyla düzeltildi. Mekanik, davranış değişikliği yok.
- **İ/ı normalizasyon bug-fix'i** (`route_key.py`): Python'un `str.lower()`'ı
  'İ' (U+0130) karakterini 'i' + birleşik nokta (U+0307) olarak ayrıştırır.
  `normalize_turkish_title`/`route_key` önce İ→i, ı→i çevirip SONRA
  `.lower()` çağırır — bu sıra bozulursa bug geri gelir.
- **Smart delete state machine** (`delete_location.py`): aktif kayıt →
  soft-delete (aktif=False); zaten pasif kayıt → hard-delete (FK ihlali
  varsa `ValueError`'a çevrilir).
- **N+1 önleme** (`create_location.py`): toplu import (`ImportService.import_routes`)
  `existing_index` parametresiyle `get_by_route`'un satır-başına SELECT
  atmasını önler — `get_all_route_keys()` ile tek sorguda önceden doldurulur.
- **ORS geocode URL bug-fix'i** (`geocode_providers.py`): geocode endpoint'i
  host root'ta yaşar, ORS `base_url`'inin (ki `/v2` içerir) altında DEĞİL —
  `urlsplit`/`urlunsplit` ile origin'den yeniden türetilir.
- **`geocode_providers.py`'nin gerçek HTTP/offline motoru** (`infrastructure/
  openroute_geocode_client.py`, 2026-07-22'de `app/core/services/
  openroute_service.py`'den taşındı — mekanik taşıma, davranış değişikliği
  yok): `geocode_via_openroute`/`geocode_via_offline` kendi HTTP client'ını
  yazmıyor, bu dosyanın `OpenRouteService`/`get_openroute_service()`
  singleton'ını (client/api-key/7-şehirlik offline tablo) ödünç alıyor.
  Thread-safe singleton reset pattern'i test'lerde önemli (`ors_mod.
  _openroute_service = None`) — modül yolu değişirse bu reset satırları da
  güncellenmeli.
- **Hydration idempotency** (`application/hydration.py`): `hydrate()` her
  çağrıldığında `lokasyon.segments`'i temizleyip yeniden doldurur (cascade
  delete-orphan) — caller commit etmeli, aksi halde hidrasyon sessizce kaybolur.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_lokasyon_service*.py` — use-case
  fonksiyon testleri (0-mock: gerçek `LokasyonRepository` + `db_session`).
- `app/tests/unit/test_services/test_location_geocode_client_coverage.py`
  (2026-07-22'de `test_openroute_service_coverage.py`'den yeniden
  adlandırıldı) — `openroute_geocode_client.py`'nin geocode/offline-fallback
  testleri.
- `app/tests/unit/test_lokasyon_hydrator.py` — `LokasyonHydrator` (FakeMapbox/FakeElev stub'ları).
- `app/tests/unit/test_lokasyon_schemas.py` — Pydantic şema validasyonu.
- `app/tests/api/test_locations_*.py`, `app/tests/integration/test_locations_api.py` —
  endpoint testleri (`TEST_DATABASE_URL` zorunlu, `docker compose --profile test up -d api-stub` ile ORS/Nominatim canlı stub).
- Free-function `unittest.mock.patch` hedefi HER ZAMAN **tüketen modül**
  (`v2.modules.location.api.location_routes.<fn>` veya
  `v2.modules.location.application.create_location.<fn>`) — kaynak modül
  değil, çünkü modül-seviyesi importlar tüketen modülün namespace'inde
  kalıcı attribute olarak yaşar. İstisna: fonksiyon-içi (inline) importlar
  (`analyze_location_route`'daki `get_route_service`, `/route-info`
  endpoint'indeki aynısı) — bunlar her çağrıda KAYNAK modülden taze
  import edilir, patch hedefi kaynak modül olmalı.
