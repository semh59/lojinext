# Modül Görevi: driver (dalga 5/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/driver/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** fuel dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

---

## 1. Dosya envanteri (14 dosya, 4.477 LOC)
```
app/api/v1/endpoints/drivers.py
app/api/v1/endpoints/coaching.py
app/core/services/sofor_service.py
app/core/services/sofor_analiz_service.py
app/core/services/sofor_pdf_service.py
app/database/repositories/sofor_repo.py
app/schemas/sofor.py
app/schemas/coaching.py
app/core/entities/sofor_degerlendirme.py
app/core/ai/driver_coaching_engine.py
app/core/ml/driver_performance_ml.py
app/core/ml/driver_route_profile.py
app/workers/tasks/coaching_tasks.py
app/workers/tasks/driver_tasks.py
```

## 2. Route envanteri (17 route)
`drivers.py`(14) + `coaching.py`(3) = 17.

## 3. Tablo sahipliği (4 tablo)
`soforler`, `sofor_ad_soyad_trigram`, `sofor_adaptasyon`, `coaching_deliveries`.

## 4. Bağlaşıklık karnesi
- **out:** driver→import_excel 2, driver→trip 2, driver→ai_assistant 1, driver→anomaly 1, driver→prediction_ml 1, driver→analytics_executive 1, driver→reports 1
- **in:** reports→driver 5 (en yoğun — `advanced_reports.py`→`sofor_analiz_service.py` ×2, `report_service.py`→`sofor_repo.py`), admin_platform→driver 3, ai_assistant→driver 3, prediction_ml→driver 3, trip→driver 1
- Celery: `coaching_tasks.py` 2 task (`coaching.weekly_digest` beat mon 09:00, `coaching.evaluate_pending` beat 02:00), `driver_tasks.py` 1 task (`driver.calculate_performance_score`).
- `sefer_repo.py`'de (trip modülünde) driver'a özel sorgular var: `get_by_sofor_id`, `get_with_route_analysis`, `get_driver_trips_with_route_analysis`, `get_driver_trips_by_route_type`, `get_recent_trips_batch`, `_search_driver_ids_by_name` (heavy-split ajanı tespiti) — bunlar trip modülünün `sefer_repo.py` bölünürken `modules/driver/infrastructure/driver_trip_queries.py`'ye taşınacak (trip görev dosyasında da not var).

## 5. Taşıma adımları
1. İskelet + `sofor_repo.py` → `infrastructure/repository.py`.
2. `sofor_service.py` → CRUD use-case'leri; `@publishes` (SOFOR_ADDED/UPDATED/DELETED, satır 44/142/184) payload doğrulaması.
3. `sofor_analiz_service.py`, `driver_performance_ml.py`, `driver_route_profile.py` → `domain/` (skorlama/analitik saf kurallar).
4. `driver_coaching_engine.py` (AI destekli coaching, `groq_service.py`'ye bağımlı) → `application/generate_coaching.py`; ai_assistant'a olan bağımlılık public.py üzerinden.
5. `sofor_degerlendirme.py` (entity) → `domain/models.py` (driver-scoring, shared_kernel'e DEĞİL çünkü yalnız driver kullanıyor).
6. `sofor_pdf_service.py` → `infrastructure/pdf_export.py`.
7. trip modülü taşınınca (dalga 14), `sefer_repo.py`'deki 6 driver-özel sorgu buraya `infrastructure/driver_trip_queries.py` olarak gelir — bu adım o dalgada tamamlanır, burada yalnız NOT edilir.
8. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [x] 14 dosya taşındı — commit `f2321a1`, dedektif denetimde (2026-07-14) 14/14 doğrulandı, eski path'lerin hiçbiri kalmadı (shim yok)
- [x] SOFOR_* event payload'ları DTO doğrulaması geçti — `test_sofor_service_delete_event.py`, `test_rag_sync_service_coverage.py`, `test_cache_invalidation_coverage.py` yeşil (`event_bus.publish()` çağrısı yok, decorator ölü kod olarak dokümante — bkz. CLAUDE.md)
- [x] Celery isim-uzayı testi 3 task için (`coaching.weekly_digest`, `coaching.evaluate_pending`, `driver.calculate_performance_score`) yeşil — `test_coaching_tasks.py`, `test_driver_tasks.py`, `test_coaching_flow.py`, `test_coaching_endpoints.py` doğrulandı
- [x] sefer_repo'daki 6 driver-sorgusu taşıma NOTU trip görev dosyasına çapraz-referanslı — `TASKS/modules/trip.md:22,67`'de doğrulandı

**Dedektif denetim notu (2026-07-14, bağımsız 5 paralel ajan + ana oturum doğrulaması):** kod-tarafı taşıma tam ve temiz; commit `9206e3f`'te bulunup düzeltilen gerçek regresyonun (session'sız singleton repo) İKİZİ bir pre-existing bug `domain/evaluation.py::_add_guzergah_performansi`'de bulundu (taşımadan ÖNCE de vardı, dalga 5 regresyonu DEĞİL — bkz. CLAUDE.md). `import_service.py`'nin `soforler`/`sofor_ad_soyad_trigram`'a ham SQL ile yazması da pre-existing bir tablo-sahipliği istisnası (CLAUDE.md'de dokümante edildi). "Çıkış kriteri: import-linter kontratı yeşil" fiilen ölçülemez — `.importlinter` `v2.modules.driver`'ı kapsamıyor, CI adımı `continue-on-error: true` (FAZ0'ın rapor-modu kısıtı, dalga 5'e özgü değil).
