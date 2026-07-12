# Modül Görevi: location (PİLOT — dalga 1/17)

> **DURUM (2026-07-12): KOD+TEST TAMAM.** Hedef klasör bu dosyanın yazıldığı andan sonra `app/modules/location/` → **`v2/modules/location/`** olarak değişti (bkz. `TASKS/STATUS.md` "KARAR (2026-07-12)"), ve "eski dosyalarda tek-satır shim" stratejisi terk edildi — eski 5 dosya shim'siz TAMAMEN SİLİNDİ. Aşağıdaki plan (adım 6, shim) bu yüzden GÜNCEL DEĞİL; gerçek uygulanan hâl için `v2/modules/location/CLAUDE.md` ve `TASKS/STATUS.md`'deki "DALGA 1" bölümüne bakın. Bu dosya tarihsel planlama kaydı olarak kalıyor.
>
> **1. Adım:** ~~`app/modules/location/CLAUDE.md` henüz yok~~ → **`v2/modules/location/CLAUDE.md` yazıldı ve dolu.**

**Neden pilot:** En küçük modül (5 dosya / 1.695 LOC, 2 tablo), dış bağımlılığı düşük (in=3 import statement), taşıma deseninin ilk kez kanıtlanacağı yer.

**Giriş kriteri:** FAZ0 çıkışı. **Çıkış kriteri:** import-linter kontratı bu modül için yeşil, slice+entegrasyon testleri geçiyor, `app/modules/location/` iskeleti sonraki dalgalara şablon oluyor.

---

## 1. Dosya envanteri (5 dosya, 1.695 LOC — MEMORY/PROGRESS.md §2.1)
```
app/api/v1/endpoints/locations.py
app/core/services/lokasyon_service.py
app/core/services/lokasyon_hydrator.py
app/database/repositories/lokasyon_repo.py
app/schemas/lokasyon.py
```

## 2. Route envanteri (17 route — tamamı `locations.py`)
`GET/POST/PUT/DELETE /locations/*` — tam liste `grep -nE "@router\.(get|post|put|patch|delete)" app/api/v1/endpoints/locations.py` ile çıkarılır (bu görev dosyası sayıyı doğruladı, isim listesini taşıma sırasında route dosyası bölünürken üretilecek). Hedef: `application/` altında use-case başına 1 dosya (ör. `create_location.py`, `list_locations.py`, `hydrate_location.py`) — trivial list/get okumaları `queries.py` altında toplanabilir (B.1 kuralı).

## 3. Tablo sahipliği
`lokasyonlar`, `lokasyon_segments` (2 tablo). `guzergah_kalibrasyonlari` bu modülde DEĞİL — route_simulation'a ait (yazan `route_calibration_service`), FK'sı lokasyonlar'a kesiyor (çapraz-şema kenar, fk_registry.yml'e FAZ2'de girer).

## 4. Bağlaşıklık karnesi (MEMORY/PROGRESS.md §2.1'den bu modülün payı)
- **out (location → diğer):** location→route_simulation **7** (en yoğun kenar — `locations.py`→`route_service.py`, `lokasyon_hydrator.py`→`segment_resampler.py`+`open_meteo_client.py`), location→import_excel 3, location→prediction_ml 1
- **in (diğer → location):** import_excel→location 2, route_simulation→location 1
- Bu modül **sağlıklı sağlayıcı değil** — kendisi 3 modüle bağımlı, kendisine bağımlılık az. Taşıma sırası bunu telafi eder: route_simulation ve import_excel henüz taşınmamışken location taşınırsa, bu 10 import kenarı geçici olarak `app/modules/location/` → eski `app/core/services/*` yoluna gider; `ignore_imports`'a "location → henüz-taşınmamış-modül" biçiminde geçici satırlar eklenir, o modüller taşındıkça güncellenir.

## 5. Taşıma adımları
1. `app/modules/location/{api,application,domain,infrastructure}/` iskeletini oluştur.
2. `lokasyon_repo.py` → `infrastructure/repository.py`; `models.py`'deki `Lokasyon`/`LokasyonSegment` sınıfları henüz TAŞINMAZ (models.py bölünmesi ayrı, riskli adım — D.1/1; bu modülde yalnız import yolu değişir, ORM tanımı FAZ1'in son adımında shared_kernel'den ayrılır).
3. `lokasyon_service.py` → `application/` altında use-case'lere bölünür (CRUD + hydrate ayrı dosyalar).
4. `lokasyon_hydrator.py` → `domain/hydration.py` (route_simulation'a olan 2 bağımlılığı public.py üzerinden çağırır — henüz route_simulation taşınmadıysa geçici olarak eski yola).
5. `locations.py` router → `api/location_routes.py`; 17 route'un mevcut RBAC `Depends()` zinciri route ile birlikte taşınır (ayrılmaz — B.1 kuralı).
6. Eski dosyalarda tek-satır shim bırakılır (`faz1-registry-iskelet-ve-shim.md` deseni).
7. `app/modules/location/CLAUDE.md`'yi B.6 şablonuyla doldur (bkz. `faz1-claude-md-per-module-template.md`).

## 6. Kabul kriterleri
- [ ] `app/modules/location/CLAUDE.md` var ve dolu (placeholder yok)
- [ ] 5 dosya taşındı, eski yollarda tek-satır shim
- [ ] import-linter `module-layers` kontratına location eklendi, yeşil
- [ ] Slice testleri (use-case başına) + mevcut entegrasyon testleri (0-mock, gerçek DB) geçiyor
- [ ] Kod-kısalığı PR kontrol listesi (≥2 tüketici / shim tek satır / net-LOC raporu) PR açıklamasında yanıtlı
- [ ] `app/modules/location/CLAUDE.md` içeriği root CLAUDE.md modül tablosuna eklendi
