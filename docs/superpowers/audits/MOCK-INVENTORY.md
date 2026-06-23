# MOCK-INVENTORY — Mutlak 0-Mock Test Dönüşümü (Faz 3.0)

**Tarih:** 2026-06-17
**Amaç:** "0 hata, 0 sahte/hayali kod, 0 mock, 0 yalan" hedefi için mevcut test çift-katmanını (test double) envanterle, sınıflandır, dönüşüm stratejisini bağla.
**Kapsam:** `app/tests/` (backend) + `frontend/src/**` (frontend).
**Statü:** Envanter TAMAM. Dönüşüm (3.1–3.6) faz faz, multi-session — bu doküman o işin haritası.

> Sayılar ham `grep` sinyalidir (satır/dosya bazında, açıkça etiketli). Kesin AST sayımı değil; büyüklük mertebesi ve dağılım için.

---

## 1. Büyüklük (ham sinyal)

### Backend (`app/tests/`)
| Sinyal | Değer |
|--------|------|
| `test_*.py` dosya sayısı | **451** |
| `MagicMock`/`AsyncMock`/`patch(` içeren dosya | **268** |
| `monkeypatch` içeren dosya | **85** |
| `FakeUnitOfWork`/`uow_mock`/`patch_unit_of_work` içeren dosya | **14** |
| `MagicMock`/`AsyncMock` toplam geçiş | ~8164 |
| `patch(` toplam geçiş | ~1944 |
| `monkeypatch.setattr` toplam geçiş | ~354 |
| `assert True` placeholder | **1** |
| `@pytest.mark.skip` / `xfail` | **5** |

### Frontend (`frontend/src/`)
| Sinyal | Değer |
|--------|------|
| Test dosyası (`*.test.*` / `*.spec.*`) | **150** |
| `vi.mock` içeren dosya | **123** |
| `vi.mock` toplam geçiş | **355** |
| `vi.spyOn` / `vi.fn` geçiş | **639** |

**Sonuç:** Mock yükü çok yüksek ve yük taşıyor (load-bearing). Bu, tek oturumda değil **fazlı** dönüştürülür. İyi haber: gerçek "sahte/yalan" test yüzeyi küçük (1 `assert True`, 5 skip/xfail) — asıl iş mock'ları **gerçeğe** çevirmek, çöp test silmek değil.

---

## 2. Sınıflandırma (3 kategori)

### Kategori A — İÇ kod mock'u → **gerçek DB/Redis'e çevrilecek**
İç repo/servis/UoW monkeypatch'i. Hedef: gerçek `UnitOfWork` + gerçek repo + gerçek Postgres/Redis transaction; gerçek servis çalışır, gerçek sonuç doğrulanır.
- **Birincil hedef:** `FakeUnitOfWork` / `app/tests/_helpers/uow_mock.py` (14 dosya) → **sil**, gerçek UoW.
- `monkeypatch.setattr("app...Service.method", AsyncMock(...))` ve `patch.object(Service, "_internal", ...)` (85+ dosya) → gerçek çağrı.
- `conftest.py` autouse `mock_redis_for_cache_manager` (tüm unit testleri etkiler) → gerçek Redis (testcontainers/CI servisi).

### Kategori B — DIŞ HTTP sınırı → **gerçek ağ (yerel stub konteyner) + opt-in canlı kulvar**
Üçüncü-parti API in-process taklidi. Hedef: in-process `MagicMock`/`patch("httpx...")` yerine gerçek `httpx` ile gerçek bir endpoint'e (deterministik yerel stub konteyner). Ayrıca `RUN_LIVE_API_TESTS=1` ile gerçek API kulvarı (nightly/manuel).

Backend test referans yoğunluğu (ham):
| Dış sınır | Referans | Not |
|-----------|---------:|-----|
| `httpx` (genel HTTP) | 154 | Mapbox/Openroute/Open-Meteo/OCR çağrıları buradan |
| `sentry` | 137 | conftest module-level Sentry mock; gözlemlenebilirlik — stub yeterli |
| `mapbox` | 111 | Directions API |
| `openroute` | 106 | ORS fallback |
| `redis_pubsub` | 67 | **Kategori A'ya yakın** — gerçek Redis pub/sub ile çözülür |
| `telegram_notifier` | 18 | Bot bildirimi |
| `open_meteo` | 16 | Elevation + weather; canlı kulvarda `test_open_meteo_live.py` çekirdek |
| `redis.from_url` / `redis.asyncio.from_url` | 19 | **Kategori A** — gerçek Redis |
| `AsyncGroq` | 3 | LLM; stub + canlı kulvar |

### Kategori C — Placeholder / yalan test → **sil veya gerçek assertion**
- `assert True`: **1** (`app/tests/test_db_hardening.py`) → gerçek assertion'la doldur veya sil.
- `@pytest.mark.skip`/`xfail`: **5** → gerçek sebep yoksa kaldır; `test_open_meteo_live.py` skipif = canlı kulvara taşınacak (meşru).
- Dağınık `pass`-gövdeli coverage testleri (örn. `app/tests/api/test_admin_ws_coverage.py`) → gerçek davranış doğrula.

---

## 3. Hedef altyapı (3.1)

1. **testcontainers-python** (`app/requirements-dev.txt`): lokalde gerçek geçici `postgres:16-alpine` + `redis:7-alpine`; CI'da mevcut servis kullanılır.
2. `conftest.py`: `mock_redis_for_cache_manager` autouse **kaldır** → gerçek Redis.
3. `_helpers/uow_mock.py` **sil**; `FakeUnitOfWork` tüketicileri gerçek UoW'a taşı.
4. **Yerel dış-API stub konteyner** (küçük FastAPI veya WireMock) compose'a eklenir; testler gerçek `httpx` ile ona gider.
5. **Frontend:** Playwright E2E (gerçek dockerized stack'e karşı) + component testlerinde `vi.mock` yerine yerel test server'a gerçek `fetch`.
6. **CI mock-grep gate:** dönüştürülen alanda yeni `MagicMock`/`patch(`/iç `monkeypatch`/`vi.mock` → CI kırılır.

---

## 4. Dönüşüm dilimleri (3.2, kademeli — her dilim ayrı PR + yeşil suite)

ARCH-004 mypy epic'indeki kademeli-merge yöntemi:
1. Altyapı (testcontainers + conftest Redis + UoW gerçek) — temel.
2. `sefer` domain (en büyük).
3. `arac` / `sofor` / `dorse` / `lokasyon`.
4. `ml` (ensemble/physics/time_series) — fixture'lı gerçek model, stub değil.
5. `ai` / RAG / Groq — stub konteyner + canlı kulvar.
6. `import` (Excel pipeline).
7. `admin` / `audit` / `monitoring` / `telegram` / `sentry`.
8. Frontend (Playwright + component).
9. CI gate + coverage gate + doküman drift (CLAUDE.md "70%" → gerçek **%92**).

---

## 5. Bilinen gerilim (0 yalan)

- **Her CI'da canlı dış API ≠ deterministik.** Open-Meteo rate-limit kanıtlı (bkz. CLAUDE.md gotcha). Bu yüzden default CI = gerçek-yerel-stub (in-process mock değil, gerçek ağ), canlı API = gated kulvar. Bu "0 in-process mock" ilkesini korur; "her koşuda canlı API" demez (kasıtlı, gerekçeli).
- **Süre:** ~268 backend + ~123 frontend dosya. Tek oturum değil. İlerleme bu dokümana ve task listesine işlenecek; hiçbir dilim koşulmadan "bitti" denmeyecek.

---

## 6. Integration-test mock triyajı (2026-06-23) — 16/55 dosya

`app/tests/integration/` mock kullanan 16 dosya kanıt-bazlı sınıflandı:

**A — FALSE POSITIVE (gerçek mock yok, aksiyon gerekmez):**
`test_api_seferler` (`async_client.patch()` HTTP, mock import yok), `test_ml_ai_pipeline`
(`monkeypatch.setenv` invalid GROQ — gerçek failure-path testi).

**B — MEŞRU harici-API / feature-flag izolasyonu (KORU):** `test_mapbox_client`,
`test_coaching_effectiveness`, `test_coaching_endpoints`, `test_theft_alarm`,
`test_internal_coaching`, `test_investigations_crud`, `test_maintenance_predictions`,
`test_plan_wizard_endpoint` — httpx (Telegram/Mapbox) veya `settings.*_ENABLED` flag.

**C — İÇ SEAM mock'u — derin inceleme sonrası rafine (2026-06-23):**
Başta "6 dosya çevrilecek" sanılıyordu; tek tek gerçek koda bakınca yalnız **3'ü**
gerçek çevrilebilir iç-seam çıktı (çevrildi+yeşil); kalan 3'ün mock'u meşru sınır:

1. `test_route_service_hybrid` — mocked UoW (`get_uow`) + mocked prediction
   (`{"prediction_liters":30.0}`). **→ ÇEVRİLDİ: real UoW (db_session) + real
   prediction_service; harici ORS/Mapbox mock'u korundu. 2 passed.** (P0-sınıfı seam)
2. `test_route_api` — `AsyncSessionLocal` (DB) + iç `PolylineDecoder`/`RouteAnalyzer`.
   **→ ÇEVRİLDİ: gerçek polyline → real decoder+analyzer; `update_route_distance`
   gerçek DB SELECT→UPDATE round-trip; yalnız ORS httpx mock kaldı. 2 passed.**
3. `test_prediction_time_series_api` — `StubTimeSeriesService` (iç servis stub).
   **→ ÇEVRİLDİ: stub kaldırıldı; gerçek TimeSeriesService boş DB'de gerçek
   PRECONDITION_NOT_MET/structured-error üretiyor (gerçek servis↔endpoint kontratı).
   2 passed.**
4. `test_error_detector_integration` — **MEŞRU (çevrilmedi):** `fresh_bus` zaten
   GERÇEK `ErrorEventBus` örneği (izolasyon); gerçek ORM insert + gerçek API okur.
   Kalan mock'lar `_write_redis`/Redis-mgr + httpx webhook = **harici servis**
   izolasyonu (Kategori-B); `_write_postgres` etkisi gerçek insert+API ile zaten
   doğrulanıyor.
5. `test_import_partial_events` — **OBSOLETE (çevrilmez):** dosya zaten
   `pytest.mark.skip` — kaldırılmış `/trips/import` CSV endpoint'ini hedefliyor
   (canlı yol `/trips/upload` Excel-only). De-mock değil, **xlsx fixture'lı tam
   rewrite** gerektirir (ayrı iş).
6. `test_activity_log` — **CALL-CONTRACT SINIRI (çevrilmedi):** `log_audit_event`
   mock'u endpoint'in audit helper'ını doğru çağırdığını doğruluyor. Gerçek
   `admin_audit_log` persist'i best-effort/exception-yutulan (CLAUDE.md) →
   gerçeğe çevirmek flake riski (0-yalan ilkesine aykırı). Mock meşru sınır.

**Sonuç:** Integration katmanında "her seam mock'suz" hedefi pratikte 3 dosyada
gerçekleşti; kalan 3 ya meşru harici-izolasyon ya obsolete-skip ya call-contract
sınırı — hiçbiri P0-tipi gizli-kontrat riski taşımıyor.
