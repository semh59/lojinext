# Modül Görevi: prediction_ml (dalga 13/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/prediction_ml/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** ai-assistant dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil. Bu modül `out=27` ile EN DOLAŞIK tüketici — geç taşınması, bağımlı olduğu 9 modülün çoğunun (fleet, driver, fuel, route_simulation, trip, analytics_executive, ai_assistant, auth_rbac, admin_platform, reports) zaten public.py yüzeyine sahip olmasını sağlıyor.

---

## 1. Dosya envanteri (35 dosya, 10.375 LOC — EN BÜYÜK modül; `vehicle_health_factor.py` fleet'ten buraya taşındı, bağımsız doğrulama ajanı kanıtı)
```
app/api/v1/endpoints/predictions.py
app/api/v1/endpoints/admin_ml.py
app/api/v1/endpoints/admin_predictions.py
app/api/v1/endpoints/admin_pilot.py
app/core/ml/advanced_lstm.py
app/core/ml/benchmark.py
app/core/ml/ensemble_core.py
app/core/ml/ensemble_predictor.py
app/core/ml/ensemble_service.py
app/core/ml/ensemble_strategy.py
app/core/ml/kalman_estimator.py
app/core/ml/lightgbm_predictor.py
app/core/ml/model_manager.py
app/core/ml/physics_fuel_predictor.py
app/core/ml/predictors/__init__.py
app/core/ml/predictors/ensemble_predictor.py
app/core/ml/time_series_predictor.py
app/core/ml/training/__init__.py
app/core/ml/training/scheduler_task.py
app/core/ml/training/trainer.py
app/core/ml/adjustment_factors.py
app/core/ml/vehicle_health_factor.py
app/core/services/ml_service.py
app/core/services/prediction_backfill_service.py
app/core/handlers/model_training_handler.py
app/core/handlers/physics_handler.py
app/services/prediction_service.py
app/services/time_series_service.py
app/schemas/ml_schemas.py
app/schemas/prediction.py
app/database/repositories/ml_training_repo.py
app/database/repositories/model_versiyon_repo.py
app/workers/tasks/prediction_tasks.py
app/workers/tasks/prediction_backfill_tasks.py
app/scripts/benchmark.py
```

## 2. Route envanteri (16 route)
`predictions.py`(11) + `admin_ml.py`(3) + `admin_predictions.py`(1) + `admin_pilot.py`(1) = 16.

## 3. Tablo sahipliği (3 tablo) + FAZ0 açık nokta
`egitim_kuyrugu`, `model_versiyonlar`, `prediction_results`. **FAZ0 Adım 3 sonucu buraya işlenir:** `model_manager.py`'nin 7 raw-SQL sitesi `model_versions`'a erişiyor — eğer bu ölü kod çıkarsa, taşıma sırasında bu 7 site TEMİZLENİR (kaldırılır, "geçici" bırakılmaz); eğer gerçek bir tabloya karşılık geliyorsa `model_versiyonlar` ile birleştirme kararı burada uygulanır.

## 4. Bağlaşıklık karnesi
- **out (27 — en dolaşık tüketici):** prediction_ml→fleet 7 (en yoğun — `ensemble_service.py`→`arac_repo.py`+`dorse_repo.py`), prediction_ml→trip 4, prediction_ml→driver 3, prediction_ml→route_simulation 3, prediction_ml→analytics_executive 3, prediction_ml→admin_platform 2, prediction_ml→ai_assistant 2, prediction_ml→auth_rbac 1, prediction_ml→fuel 1, prediction_ml→reports 1
- **in:** trip→prediction_ml 6, route_simulation→prediction_ml 4, ai_assistant→prediction_ml 2, anomaly→prediction_ml 1, location→prediction_ml 1, driver→prediction_ml 1
- Warm-up hook: `main.py:300-338` (ML predictor warm-up, `_warmup_all_predictors`) → bu modülün `startup(app)` hook'una taşınır (faz1-registry-iskelet-ve-shim.md'de belirtilen taşıma).
- Multi-worker sorunu (MEMORY §4.1): `EnsemblePredictorService` 20-slot LRU × 4 worker — bu modülün SINIRLARI İÇİNDE ama ÇÖZÜMÜ bu FAZ'da DEĞİL (mimari sorun değil, kaynak-yönetimi sorunu; ayrı performans işi olarak modül CLAUDE.md'sine not düşülür, plan kapsamı dışı).

## 5. Taşıma adımları (heavy-split ajanının `prediction_service.py` 950 satır haritası)
1. İskelet oluştur.
2. `predict_consumption` (CC=50, 257 satır, en kompleks fonksiyon) 4 kümeye ayrılır — **None-coalescing sınırı (satır 612-616: ascent_m/descent_m/flat_distance_km None→0.0) çağrıdan AYRILMAZ**, downstream fizik hesapları non-null varsayıyor:
   - fizik kümesi (`_run_physics_model`, `_run_physics_fallback`, `_build_base_factors`, `_build_vehicle_specs`) → `domain/physics_model.py`
   - ensemble kümesi (`_run_ensemble_prediction`, `_process_ensemble_result`) → `domain/ensemble.py`
   - yanıt/açıklama kümesi (`_build_prediction_response`, `_build_explanation_summary`, `_normalize_confidence_band`, `_extract_confidence_score`) → `application/response_builder.py`
   - rota-oranı yardımcıları (`_derive_route_ratios`, `_normalize_route_analysis`, `_sum_segment_km`) → `domain/route_ratios.py`
3. **Prefetch-N+1 koruması korunur:** `predict_consumption` prefetched `_arac_obj`/`_sofor_obj`/`_dorse_obj` (satır 594-596) alır; `_build_sefer_dict` (173L) bunlar yoksa DB'den yükler — orkestratör bu "varsa kullan, yoksa yükle" dalını KORUMALI, yoksa `bulk_add_sefer`'ın batch yolu 5N sorguya regresyon yapar.
4. `ensemble_core.py::fit` (CC=61, en yüksek kompleksite) baseline'a alınır, bu FAZ'da bölünmez (gerekçesiz split yasak — kod kısalığı kuralı).
5. `vehicle_health_factor.py` fleet'ten gelen post-process çarpanı → `domain/vehicle_health_adjustment.py`.
6. `adjustment_factors.py` → `domain/adjustment_factors.py`.
7. analytics_executive'ten gelen ML-parametre metodları (`get_training_seferler`, `save_model_params`, `get_model_params`, `get_daily_summary_for_ml`) → `infrastructure/model_params_repo.py` (analytics-executive görev dosyasının madde 4'ünde işaretlenen taşıma, burada tamamlanır).
8. `training/scheduler_task.py` (`@shared_task`, beat pazar 03:00) → `infrastructure/tasks.py`.
9. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] 35 dosya + analytics_executive'ten gelen 4 ML-param metodu taşındı
- [ ] `predict_consumption` 4 kümeye ayrıldı, None-coalescing sınırı çağrıyla birlikte
- [ ] Prefetch-N+1 koruması regresyon testiyle kanıtlı (batch-import senaryosu hâlâ tek sorgu)
- [ ] `ensemble_core.fit` CC=61 baseline'da (bölünmedi, gerekçe CLAUDE.md'de)
- [ ] model_versions/model_versiyonlar FAZ0 kararı uygulandı
