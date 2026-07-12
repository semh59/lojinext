# Modül Görevi: fleet (dalga 3/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/fleet/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** notification dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil; fleet `out=4/in=19` profiliyle "sağlıklı sağlayıcı" — erken taşınması sonraki dalgaların (trip, prediction_ml, driver, reports, import_excel, analytics_executive) fleet'e bağımlılığını public.py üzerinden kurmasını sağlar.

---

## 1. Dosya envanteri (15 dosya, 3.632 LOC — `vehicle_health_factor.py` bağımsız doğrulama ajanınca prediction_ml'e taşındı, MEMORY §2.1)
```
app/api/v1/endpoints/vehicles.py
app/api/v1/endpoints/trailers.py
app/api/v1/endpoints/maintenance.py
app/api/v1/endpoints/admin_maintenance.py
app/core/services/arac_service.py
app/core/services/dorse_service.py
app/core/services/maintenance_service.py
app/database/repositories/arac_repo.py
app/database/repositories/dorse_repo.py
app/database/repositories/maintenance_repository.py
app/schemas/arac.py
app/schemas/dorse.py
app/schemas/maintenance_prediction.py
app/core/ml/maintenance_predictor.py
app/core/services/ics_generator.py
```

## 2. Route envanteri (31 route)
`vehicles.py`(13) + `trailers.py`(10) + `maintenance.py`(1) + `admin_maintenance.py`(7) = 31.

## 3. Tablo sahipliği (5 tablo)
`araclar`, `dorseler`, `arac_bakimlari`, `vehicle_event_log`, `vehicle_spec_timeline`. Çapraz-şema FK'ları: `araclar.olusturan_id`→auth_rbac.kullanicilar; `arac_bakimlari.arac_id`/`.dorse_id` modül-içi.

## 4. Bağlaşıklık karnesi
- **out (az — sağlıklı sağlayıcı):** fleet→import_excel 3, fleet→auth_rbac 1
- **in (çok — 19 import statement diğer modüllerden):** prediction_ml→fleet 7 (en yoğun — `ensemble_service.py`→`arac_repo.py`+`dorse_repo.py`), ai_assistant→fleet 3, reports→fleet 3, analytics_executive→fleet 2, admin_platform→fleet 1, import_excel→fleet 1, trip→fleet 1, fuel→fleet 1
- Event publisher: `arac_service.py` satır 84/193/282 → `ARAC_ADDED`/`ARAC_UPDATED`/`ARAC_DELETED`. Subscriber'lar (rag_sync, cache_invalidation — ai_assistant ve platform-infra'da) bu event'leri ASENKRON tüketir, fleet modülü kimin dinlediğini bilmez (doğru ayrışma).
- Raw-SQL sitesi: `arac_repo.py` kendi + `seferler`(trip) tablosuna erişiyor (32 raw-SQL sitesinden biri) — bu erişim FAZ2'de trip şemasına SELECT-only grant gerektirecek, fleet'in kendi şemasında kalır.

## 5. Taşıma adımları
1. İskelet + `arac_repo.py`/`dorse_repo.py`/`maintenance_repository.py` → `infrastructure/repository.py` (3 ayrı dosya, tek dosyaya birleştirilmez — modül-içi zaten ayrı sorumluluk).
2. `arac_service.py`, `dorse_service.py`, `maintenance_service.py` → `application/`'da use-case başına dosya (create_vehicle.py, update_vehicle.py, deactivate_vehicle.py, vb.); `@publishes` decorator'ları (ARAC_ADDED/UPDATED/DELETED) `events.py`'ye taşınırken gerçek payload'ları kontrol edilir (MEMORY §3'teki "henüz ölçülmedi" notu — bu modülün publish siteleri burada ilk kez doğrulanır: dict mi ORM mü taşıyor).
3. `maintenance_predictor.py` (ML) → `domain/maintenance_prediction.py` (fleet-içi, prediction_ml'e taşınmadı çünkü bakım-tahmini fleet'in kendi iş kuralı — vehicle_health_factor'dan farklı olarak trip/fuel prediction pipeline'ına post-process olarak eklenmiyor).
4. `ics_generator.py` → `application/export_maintenance_calendar.py`.
5. `vehicles.py`/`trailers.py`/`maintenance.py`/`admin_maintenance.py` router'ları → `api/` altında ayrı dosyalar, RBAC Depends() route ile taşınır.
6. Shim'ler + `app/modules/fleet/CLAUDE.md`.

## 6. Kabul kriterleri
- [ ] 15 dosya taşındı, shim tek satır
- [ ] ARAC_ADDED/UPDATED/DELETED event payload'ları `events.py`'de DTO — ORM sızıntısı testi (faz1-davranissal-mimari-testler.md madde 3) bu 3 site için yeşil
- [ ] `arac_repo.py`'nin `seferler` tablosuna raw-SQL erişimi FAZ2 rol matrisine not düşüldü (SELECT-only grant ihtiyacı)
- [ ] import-linter: fleet `out=4` kontratı — yeni cross-module import eklenmedi
