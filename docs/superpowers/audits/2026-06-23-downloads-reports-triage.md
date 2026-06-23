# İndirilen Raporların Konsolide Triyajı — 2026-06-23

**Amaç:** İki dış analiz raporundaki TÜM bulguları tek dosyada toplayıp, her birini
**canlı koda karşı** doğrulamak ("rapora güvenme, kanıta güven") ve gerçekten açık
olanları çözmek. Entegrasyon noktaları mock'suz, gerçek nesnelerle test edilir.

## Kaynak raporlar
1. `Downloads/LOJINEXT_derin_analiz_2026-06-22.md` — ZIP `lojinext-main__14_.zip` snapshot'ına karşı. Başlık bulgusu **P0**: "ML ensemble sonucu hiç kullanılmıyor; `confidence_score` key'i ensemble_service tarafından hiç üretilmiyor → her tahmin sessizce physics-fallback".
2. `Downloads/LOJINEXT_BUG_REPORT.md` (2026-06-08) — ZIP #10 snapshot'ı. ~50 bulgu (BUG-/SEC-/DATA-/MODEL-/ARCH-/MINOR-).

## Yöntem
Her bulgu güncel `main` (HEAD) kaynağında `grep`/`Read` ile bizzat doğrulandı. Durumlar:
- **FIXED** — kaynakta düzeltilmiş, kanıt (file:line / commit) verildi.
- **LIVE** — hâlâ açık, bu oturumda ele alındı.
- **DEFERRED** — açık ama migration/validasyon gerektiriyor; bilinçli ertelendi.
- **N/A** — tasarım tercihi / yanlış pozitif.

---

## ÖZET

Her iki rapor da **büyük ölçüde stale**. Başlıktaki P0 ve tüm kritik/güvenlik
bulguları zaten düzeltilmiş. Triyaj sırasında raporlarda **olmayan, gerçek bir
LIVE bug** ortaya çıktı: P0 seam'ini koruyan real-object integration testinin
kendisi geçersiz `durum` değeriyle DB CHECK constraint'ini ihlal ediyordu.

| Kategori | Adet |
|----------|------|
| Raporlarda FIXED (kanıtla doğrulandı) | 18+ |
| Bu oturumda çözülen LIVE — test bug'ları (TEST-BUG-01..06) | 6 |
| Bu oturumda çözülen LIVE — **prod servis bug'ı** (SVC-BUG-01) | 1 |
| Bu oturumda çözülen LIVE — temizlik (ölü requirements, openroute msg) | 2 |
| DEFERRED (migration/validasyon gerektiriyor) | 3 |
| N/A / tasarım | 2 |
| Kapsam dışı test-izolasyon flake (kod bug'ı değil) | 1 |

**Nihai test durumu:** seam dosyaları 13 passed (mock'suz) · prediction/ensemble unit
60 passed (regresyon yok) · tüm integration suite **229 passed, 8 skipped, 1 error
(izolasyon flake), 0 failed**.

---

## P0 (derin_analiz 2026-06-22) — FIXED ✅

**İddia:** `ensemble_service.predict_consumption()` döndürülen dict'te `confidence_score`
key'i yok → `_extract_confidence_score()` her zaman `None` → koşulsuz physics-fallback.

**Kanıt (güncel kod):**
- `app/core/ml/ensemble_service.py:603-612` — `confidence_score` raporun önerdiği
  formülün **birebir aynısı** ile hesaplanıp dict'e ekleniyor:
  ```python
  interval = result.confidence_high - result.confidence_low
  confidence_score = max(0.0, min(1.0, 1 - interval / (2 * max(result.tahmin_l_100km, 1e-6))))
  return {..., "confidence_score": round(confidence_score, 3), ...}
  ```
- `app/services/prediction_service.py:455` — `_extract_confidence_score` bunu okuyor;
  fail-closed dalı (satır 463-469) artık yalnızca gerçek eksiklikte tetikleniyor.
- Git: `945e2c4 fix(contracts): apply source fixes for prediction key mismatches`.

**Guard:** `app/tests/integration/test_prediction_contract_integration.py` — bu seam'i
**mock'suz** test ediyor (`confidence_score` varlığı satır 88). Yani fix hem kaynakta
hem real-object testte korunuyor. → Raporun P0'ı **moot**.

---

## P1 (derin_analiz 2026-06-22)

| # | Bulgu | Durum | Kanıt / Aksiyon |
|---|-------|-------|------------------|
| P1-1 | Physics yaş etkisi çift uygulanıyor olabilir (`ensemble_core.py:964` `physics_raw*yas_faktoru*mevsim_faktor` + physics_predictor içi yaş) | **DEFERRED** | İki farklı mekanizma (regen-recovery vs genel aşınma) olabilir; rapor da "doğrulama gerekiyor" diyor. Net bir bug değil. `scripts/p51_real_world_validation.py` ile 10+ yaş araçlarda sapma ölçülmeli. |
| P1-2 | `openroute_client.py` uyarısı yalnız legacy env adını söylüyor | **LIVE→FIXED** | `app/infrastructure/routing/openroute_client.py` uyarı mesajı canonical ada güncellendi. |
| P1-3 | `requirements-secure.txt` / `requirements-lock.txt` ölü dosya, eski CVE'li pin (`python-jose==3.3.0`, `torch==2.1.0`) | **LIVE→FIXED** | İkisi de hiçbir build/CI/Dockerfile'da referans edilmiyor (grep ile doğrulandı). Silindi. |
| P1-4 | `sefer_write_service.py:171` `prediction_liters` legacy fallback | **DEFERRED** | Zararsız metadata fallback; canonical alan `tahmini_litre`. Düşük değer, davranış kırılmıyor. |

---

## BUG_REPORT (2026-06-08) — doğrulama matrisi

| # | Bulgu | Durum | Kanıt (güncel kod) |
|---|-------|-------|---------------------|
| BUG-001 | `auth_service` `import datetime` + `datetime.now()` crash | **FIXED** | `auth_service.py:1` `from datetime import datetime, timedelta, timezone`; satır 231 doğru. |
| BUG-002 | 12 lokasyonda Türkçe durum literal'ı raw SQL | **FIXED** | `app/core/utils/trip_status.py` normalizasyon haritası (`"Tamamlandı"→Completed`). Kalan kullanımlar yorum/Excel/display. |
| BUG-003 | `analiz_repo` `FROM anomalier` typo | **FIXED** | Kaynakta `anomalier` yok; yalnız bir test yorumunda referans. |
| SEC-001 | IDOR `mark_as_read` ownership yok | **FIXED** | `notification_service.py:145` `mark_as_read(self, notification_id, user_id)`. |
| SEC-002 | `INTERNAL_API_SECRET` prod validator yok | **FIXED** | `config.py:323` prod'da boşsa `ValueError`. |
| SEC-003 | WebSocket RS256 sessiz auth fail | **FIXED** | JWT-decode kaldırıldı; Redis ticket tabanlı `verify_ws_ticket` (admin_ws.py). |
| SEC-004 | Token blacklist fail-open | **FIXED** | `token_blacklist.py:61` exception'da `return True` (fail-closed). |
| SEC-005 | `ADMIN_PASSWORD` migration bootstrap crash | **DEFERRED** | Tip hâlâ `Optional[SecretStr]`; prod validator startup'ta var. Yalnızca yeni ortamda `ADMIN_PASSWORD` set edilmeden migration koşulursa latent. Migration guard ayrı kalem. |
| SEC-006 | Access token localStorage'da | **N/A** | Frontend güvenlik tradeoff; refresh token HttpOnly. Bilinçli tasarım. |
| SEC-007 | İki ayrı bcrypt impl (72-byte guard eksik) | **FIXED** | `jwt_handler.get_password_hash` canonical `core.security`'e delege ediyor. |
| SEC-008 | `kullanicilar.id` FK'larında `ondelete` eksik | **DEFERRED** | Çoğu düzeltilmiş; `models.py:1148` tek FK hâlâ açık. Migration gerektirir. |
| DATA-002 | `sefer_fuel_estimator.arac_yasi=5` hardcoded | **FIXED** | `_derive_arac_yasi(arac)` gerçek yaş mantığı (satır 355). |
| DATA-004 | `YakitFormul.updated_at` timezone yok | **FIXED** | `models.py` YakitFormul `DateTime(timezone=True)` + `onupdate=get_utc_now` + created_at eklendi. |
| MODEL-001 | `TripStatus` ASSIGNED/IN_PROGRESS DB CHECK'te yok | **FIXED** | `schemas/sefer.py:31` "kaldırıldı" yorumu; enum yalnız Planned/Completed/Cancelled. |
| MINOR-002 | `slowapi` opsiyonel → rate limit kapanabilir | **FIXED** | `app/requirements.txt:77` `slowapi>=0.1.9` zorunlu. NoopLimiter sadece savunma. |
| MINOR-010 | SSE semaphore TOCTOU race | **N/A** | `error_stream.py:39-42` kod-içi not: `locked()`↔`acquire()` arası `await` yok → gerçek TOCTOU yok. |
| ARCH-001 | Superadmin id=0 audit anonimleşiyor | **FIXED** | `deps.py` prod gerçek superadmin row'unu çözüyor; id=0 yalnız dev/test/DB-down break-glass (commit `3d9d094`). |

> BUG_REPORT'taki diğer MODEL-/MINOR-/ARCH- kalemleri (updated_at eksikleri, mypy
> baseline, CQRS facade, stil) ya tasarım tercihidir ya da ayrı epic'lerde
> (ARCH-004 mypy) izleniyor; bu triyaj kapsamı kritik/runtime bulgulardır.

---

## YENİ LIVE BUG'LAR (raporlarda yok — triyaj sırasında testi KOŞARAK bulundu)

> Önemli metodoloji notu: Statik hipotezim "geçersiz `durum` → CHECK ihlali" idi.
> Testi gerçekten koşunca **ilk** kök nedenin farklı olduğu ortaya çıktı; körü
> körüne fix uygulamadan koştuğum için doğru kök neden bulundu (systematic-debugging).

### TEST-BUG-01 · `insert(Arac)` olmayan kolon `euro_sinifi`'ye yazıyor → tüm seam testleri patlıyor

**Dosyalar (3):**
- `app/tests/integration/test_prediction_contract_integration.py:36`
- `app/tests/integration/test_cashflow_projector_integration.py:30`
- `app/tests/integration/test_sefer_status_filter_integration.py:31`

`insert(Arac).values(..., euro_sinifi="EURO6")` — ama `araclar` tablosunda
`euro_sinifi` **kolonu yok**. `euro_sinifi` yalnızca Pydantic entity'de bir
**computed property** (`core/entities/models.py:157`, `yil`'den türetilir:
`yil>=2014 → "Euro 6"`). ORM insert'i → `sqlalchemy.exc.CompileError: Unconsumed
column names: euro_sinifi`. Bu yüzden **5 seam testinin tamamı** seam mantığına
ulaşmadan `_create_arac` helper'ında patlıyordu.

**Ampirik RED (fix öncesi):**
```
sqlalchemy.exc.CompileError: Unconsumed column names: euro_sinifi
5 failed in 26.44s  (test_prediction_contract_integration.py)
```

**Fix:** Üç dosyadan da `euro_sinifi="EURO6"` insert kwarg'ı kaldırıldı. `yil` zaten
set; entity euro_sinifi'yi otomatik hesaplar (testler bu alanı assert etmiyor).

Bu 3 dosya **tamamen hayali bir şema/API'ye karşı yazılmış ve hiç koşmamıştı**.
Testi katman katman koşarak art arda açığa çıkan kusurlar (her biri bir öncekinin
downstream'i — tek seferde değil, gerçek RED'leri görerek bulundu):

### TEST-BUG-02 · geçersiz `durum="tamamlandi"` → DB CHECK ihlali
`test_prediction_contract_integration.py:222,263` — raw core insert Pydantic
`ensure_canonical_sefer_status`'u bypass eder. CHECK `durum IN
('Planned','Completed','Cancelled')` (`models.py:488`). → `durum="Completed"`.

### TEST-BUG-03 · `insert(Sefer)`'de olmayan kolon adları (3 dosya)
`baslangic_lokasyon`/`bitis_lokasyon`/`gercek_tuketim`/`aktif` → `araclar`/`seferler`
şemasında yok. Gerçek adlar: `cikis_yeri`, `varis_yeri`, `tuketim`; soft-delete
`is_deleted` (Sefer'de `aktif` yok). `gercek_tuketim→tuketim` **semantik** olarak da
şart (analiz repo `WHERE s.tuketim IS NOT NULL AND > 0`).

### TEST-BUG-04 · olmayan metod + UoW dışı çağrı + commit'siz insert
- `service._calculate_elite_score(...)` metodu **hiç yok** → gerçek `_calc_elite_from_trips(seferler)`'e çevrildi.
- `calculate_elite_performance_score` UoW'suz çağrılıyordu → session-less singleton repo → `RuntimeError: Database session not initialized` (CLAUDE.md gotcha). → `SoforAnalizService(uow=uow)` + `uow=uow`.
- Trip'ler `async with UnitOfWork()` içinde **commit edilmeden** insert ediliyordu → `__aexit__` rollback → trip kaybı → score None. → `db_session.execute(...)` + `await db_session.commit()`.

### TEST-BUG-05 · yanlış return-şekli assertion'ları
- cashflow: `w.fuel_liters` → `CashflowWeek`'te yok; gerçek alan `fuel_tl`.
- cost_leakage: `fuel_diff_liters` → gerçek key `fuel_gap_liters`.

### SVC-BUG-01 (PROD) · `predict_consumption` None elevation'da `None + None` crash
**Dosya:** `app/services/prediction_service.py` (fix) · kök: `physics_fuel_predictor.py:286`
`max(route.ascent_m + route.descent_m, 0.0)`.

TEST-BUG-04 düzeltilince açığa çıkan **gerçek prod bug'ı**: nullable Sefer kolonları
`ascent_m`/`descent_m` None iken (manuel-giriş, rota analizi yok), sofor elite-score
yolu `predict_consumption(ascent_m=trip.get("ascent_m", 0))` çağırıyor — ama key
DB'de None değerle MEVCUT olduğu için `.get(...,0)` **None döndürür** (default 0
kullanılmaz). None physics'e akıp `None + None` TypeError → `safe_predict` except'i
yutar → o sürücü için **skor sessizce hesaplanmaz**. Raporun "anomali/sofor skorlama
etkilenir" uyarısının somut hâli.

**Fix (boundary, kök neden):** `predict_consumption` girişinde
`ascent_m/descent_m/flat_distance_km = float(x or 0.0)` — tüm downstream physics +
ensemble aritmetiğini korur; tek caller'a değil tüm public API'ye.

Tüm bu sınıf raporların yapısal kör noktası: integration testleri CI'da koşulmuyordu
(TEST_DATABASE_URL gerektiriyor). Hafıza [[local_test_db_execution]] +
[[fullcode_audit_campaign]] desenine birebir uyuyor — mock-ağırlıklı %93 coverage bu
sınıf kontrat/şema/robustluk bug'ını yapısal olarak göremiyor.

### TEST-BUG-06 · route simulate testi yanlış hata-zarfı şekline assert ediyor
**Dosya:** `app/tests/integration/test_routes_simulate_endpoint.py:198`
Endpoint provider başarısızlığında **doğru** 502 dönüyor, ama test `resp.json()["detail"]`
(FastAPI default şekli) okuyordu → `KeyError`. Proje zarfı `{"error":{"code","message",
"trace_id"}}` (main.py HTTPException handler). → `resp.json()["error"]["message"]`.

**Ampirik sonuç:**
```
# Seam dosyaları (mock'suz):
#   fix öncesi:  5 failed (CompileError euro_sinifi) → 9 failed → 5 failed (score None)
#   fix sonrası: 13 passed in 44.44s
# prediction/ensemble unit (prod fix regresyon kontrolü): 60 passed
# TÜM integration suite:
#   fix öncesi (örtük): seam + route_simulate kırık
#   fix sonrası: 229 passed, 8 skipped, 1 error in 96s   (FAILED yok)
```

### Kapsam dışı: 1 test-izolasyon flake (kod bug'ı DEĞİL)
`test_prediction_time_series_api.py::test_time_series_forecast_returns_structured_precondition_error`
tam suite'te "setup'ta error" veriyor ama **tek başına koşunca PASS** (2 passed).
Kök: bir önceki stress/error testi (`test_adversarial_stress` / `test_concurrency_atomic`)
paylaşılan session'ı `PendingRollbackError` (sqlalche.me/e/20/rvf5) durumunda bırakıyor →
sonraki testin setup DELETE'i patlıyor. Session-scoped event loop + paylaşılan fixture
session kaynaklı **önceden var olan cross-test kirlenmesi**; ürün davranışıyla veya bu
oturumun fix'leriyle ilgisiz, Downloads raporları kapsamı dışında. İstenirse ayrı ele alınabilir.

---

## Çalıştırma reçetesi (real-object, mock'suz)

```bash
# throwaway test DB (adı 'test' içermeli — conftest DROP SCHEMA yapıyor)
docker exec lojinext-db-1 psql -U lojinext_user -d lojinext_db -c "CREATE DATABASE lojinext_test;"

# dev image (pytest dahil) + docker ağı + repo mount
MSYS_NO_PATHCONV=1 docker run --rm --network lojinext_lojinext_network \
  -v "D:/PROJECT/LOJINEXT:/app" -w /app \
  -e TEST_DATABASE_URL="postgresql+asyncpg://lojinext_user:lojinext_pass_2026@db:5432/lojinext_test" \
  -e PYTHONIOENCODING=utf-8 -e PYTHONDONTWRITEBYTECODE=1 \
  lojinext-backend-dev:latest \
  python -m pytest app/tests/integration/test_prediction_contract_integration.py -p no:cacheprovider -q
```
