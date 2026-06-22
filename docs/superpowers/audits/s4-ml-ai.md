# S4 — ML/AI + orkestrasyon denetimi

Odak (§5): ensemble ağırlık normalizasyonu (R²), cold-start DEFAULT_WEIGHTS, sıfıra bölme/NaN/inf,
`asyncio.to_thread` atlanmış bloklayan çağrı, ARIMA min-gözlem fallback, Kalman, `.pkl` yükleme hata
yönetimi, MAX_REALISTIC clamp.

## S4a-1 — physics_fuel_predictor.py (648) — 0 bulgu (temiz/örnek)

Savunmacı fizik motoru: tüm bölmeler guard'lı (`if dist_m > 0`, `total_dist_km > 0`,
`np.maximum(|pred|, 1e-6)`); `np.isfinite(fuel)` ile NaN/inf → 0.0; `MAX_REALISTIC_L_100KM=65` clamp +
Prometheus counter + log (`silent_outlier_log` ile per-segment susturma); `predict_segment_tractive`
grade `max(-cap,min(cap,..))` clamp + `t_s=dist/max(v,1.0)`; `learn_from_actual` ±50% outlier guard +
20-pencere. `__post_init__` engine_efficiency/fuel_density>0 doğrular. 0 bulgu.
> İz (low): `_build_segments` Path-1'de `raw_ascent==0 & route.ascent_m>0` → `s_up=1.0` (gerçek ascent
> segmentlere yansımaz) — nadir kenar; düşük etki.

## S4a-2 — adjustment_factors.py (185) + ensemble_strategy.py (127) — 0 bulgu (temiz)

- `adjustment_factors`: tüm hava faktörleri (`temperature`/`wind`/`precipitation`) `_clamp`'li;
  `combine_factors` çift-sayma'yı `max(temp, seasonal)` ile çözüyor + final `clamp(0.7, 1.5)`. Saf,
  div-by-zero yok. 0 bulgu.
- `ensemble_strategy`: `DynamicWeightStrategy` R²-normalize (`max(0.01, r2)` negatif/sıfır ağırlığı önler,
  `total_r2` guard, hepsi 0 ise equal fallback); `Equal`/`PhysicsFirst` `len()` guard'lı. Ağırlık
  normalizasyonu (§5 odak) doğru. 0 bulgu.

## S4a-3 — segment_simulator.py (265) + kalman_estimator.py (364) — 1 bulgu

- `segment_simulator`: `_effective_speed_kmh` min(cap/maxspeed/traffic) + congestion mult yalnız traffic
  yoksa (çift-sayma guard) + floor 5; length≤0 → sıfır çıktı; avg `total_km>0` guard. Per-segment fizik
  doğru (AUDIT-069 estimator header/segment ıraksaması orada). 0 bulgu.
- `KalmanFuelEstimator` (filtre): Joseph-form kovaryans (numerik kararlı), `S=max(1e-10,S)` underflow guard,
  `sqrt(max(0.1,var))`, `load_state` **örnek** input validation (shape + NaN/Inf + pozitif-definitlik),
  `batch_update` MAX_BATCH_SIZE=1000 DoS guard. 0 bulgu. Bulgu AUDIT-125 (servis katmanı).

### AUDIT-125 — `KalmanEstimatorService` ölü + bozuk: senkron metotlar async analiz_repo'yu await'siz çağırıyor
- Şiddet: medium
- Sınıf: dead-code / bug
- Konum: kalman_estimator.py:271-349 (get_estimator/_save_to_db/update_with_trip/predict)
- Durum: confirmed
- Kanıt:
    ```python
    def get_estimator(self, arac_id: int) -> KalmanFuelEstimator:   # SENKRON
        ...
        params = self.analiz_repo.get_model_params(arac_id)         # async, await YOK → coroutine
        if params and "kalman_state" in params.get("coefficients", {}):  # coroutine.get → AttributeError
    ...
    def _save_to_db(self, arac_id, estimator):                      # SENKRON
        self.analiz_repo.save_model_params(arac_id, {...})          # async, await YOK → coroutine atılır
    ```
  `analiz_repo.get_model_params`/`save_model_params` **async** (analiz_repo.py:105,81). `KalmanEstimatorService`
  metotları **senkron** ve bunları **await'siz** çağırıyor → coroutine asla çalıştırılmaz: `get_estimator`
  `params.get` ile `'coroutine' object has no attribute 'get'` AttributeError'a düşer (ilk çağrıda çöker);
  `_save_to_db` save coroutine'ini sessizce atar (state **hiç persist edilmez**) + "coroutine never awaited"
  uyarısı. Ayrıca `get_kalman_service`/`KalmanEstimatorService` için **üretim çağıranı yok** → ölü alt-sistem.
  (Filtre sınıfı `KalmanFuelEstimator` doğru; sorun yalnız servis sarmalı.)
- Önerilen düzeltme: servisi `async def` yap + repo çağrılarını `await`le (UoW içinde); kullanılmıyorsa
  Kalman alt-sistemini kaldır. CLAUDE.md "Kalman smoother" referansını gerçek-kullanımla doğrula.

## S4a-4 — model_manager.py (294) + ensemble_core.py (1312) — 0 bulgu (örnek)

- `model_manager`: raw SQL parametreli; **atomik versiyon aktivasyonu** (`_activate_in_session` tek
  UPDATE CASE WHEN id THEN TRUE ELSE FALSE → AUDIT-020 sınıfını çözer); save+activate+cleanup tek
  transaction; aktif versiyon silinemez; MAX_VERSIONS=5 cleanup. İz (low): `_async_lock` oluşturulmuş
  ama hiç kullanılmıyor (ölü). 0 bulgu.
- `ensemble_core` (EnsembleFuelPredictor): cold-start DEFAULT_WEIGHTS (physics=0.80) CLAUDE.md ile uyumlu;
  `prepare_features` div-guard'lı; `_align_feature_matrix` şema uyuşmazlığında **raise** (sessiz truncate
  yok → physics fallback); `fit` label-leak guard + temporal sort/split + per-model try/except + R²-normalize
  ağırlık + physics fallback + `np.maximum(|y|,1e-6)` MAPE; `predict` input-validation + NaN/Inf→physics
  fallback + `safe_total_w` + inter-model std CI; `save_model`/`load_model` **SHA256 checksum doğrulama +
  100MB DoS limiti + SecurityError + native-JSON (xgb/lgb)**. §5 ML odakları (weight-norm/NaN/.pkl) doğru
  ele alınmış. 0 bulgu. İz (low): docstring ağırlıkları (physics %10) vs DEFAULT_WEIGHTS (0.80) çelişik;
  yorum "17 isim" bayat (gerçek 29 feature).

> **Ara değerlendirme (S4a 7/26):** ML çekirdeği (physics/adjustment/strategy/segment/kalman-filtre/
> model_manager/ensemble_core) **yüksek kalite, savunmacı** — tek bulgu AUDIT-125 (Kalman SERVİS sarmalı,
> ölü+await'siz). Kalan ML: ensemble_service, lightgbm/fuel/time_series/advanced_lstm predictors,
> driver_performance_ml, maintenance_predictor, anomaly_clustering, fleet/bus/carbon/health.

## S4a-5 — ensemble_service.py (633) + fuel_predictor.py (153) + lightgbm_predictor.py (568) — 1 bulgu

Temiz: `fuel_predictor` (sklearn LinearRegression fallback, ss_tot>0 guard, not-fitted raise),
`lightgbm_predictor` (seeded split + early-stop + quantile prediction-interval; save/load **SHA256 checksum +
100MB DoS limit** ensemble_core ile aynı örnek desen). İz (low): `LightGBMAnomalyClassifier.fit` accuracy'yi
**eğitim setinde** ölçüyor (optimistik) — yalnız log, gate değil. Bulgu AUDIT-126.

### AUDIT-126 — `EnsemblePredictorService` async metotlarında bloklayan ML çağrıları (to_thread yok) → event loop bloke
- Şiddet: medium
- Sınıf: concurrency
- Konum: ensemble_service.py:143-200 (get_predictor/load_model), 305/398/455 (fit), 572/589 (predict)
- Durum: confirmed
- Kanıt:
    ```python
    async def predict_consumption(self, ...):
        ...
        predictor = self.get_predictor(arac_id)   # SENKRON; cache-miss'te joblib.load (blocking I/O)
        ...
        result = predictor.predict(sefer)          # SENKRON sklearn predict
    async def train_for_vehicle(self, arac_id):
        result = predictor.fit(enriched_seferler, np.array(y_values))  # SENKRON sklearn .fit() (saniyeler-dakika)
    ```
  `get_predictor` (senkron, `with self._lock` içinde `predictor.load_model`→`joblib.load` disk deserileştirme)
  ve `predictor.fit()`/`predictor.predict()` (sklearn/xgb/lgb blocking CPU) async metotlardan **`asyncio.
  to_thread` olmadan** çağrılıyor → ilk tahminde model yükleme + eğitim event loop'u **bloke eder**
  (CLAUDE.md: "All ML calls go through asyncio.to_thread()" kuralına aykırı). Ayrıca `threading.Lock` disk-I/O
  boyunca tutuluyor → eşzamanlı talepler serialize. AUDIT-063 (ai_service senkron fit/predict) ile aynı sınıf.
- Önerilen düzeltme: `predictor.fit`/`predict`/`load_model` çağrılarını `await asyncio.to_thread(...)` ile
  sar; eğitimi Celery worker'a taşı (zaten ml_task varsa orada blocking sorun değil — request yolu için kritik).
- Bağımlılık: AUDIT-063, AUDIT-065.

## S4a-6 — time_series_predictor.py (885) — 0 bulgu (örnek)

- LSTM (`FuelConsumptionLSTM`/`TimeSeriesPredictor`, **dev-only** — production ARIMA'ya yönlenir):
  `normalize` kapsamlı NaN/Inf koruması (`np.isfinite`→nanmean/nanstd, `nan_to_num`, `std<=1e-10→1.0`);
  `create_sequences` yetersiz veride zero-padding+uyarı; `train` early-stopping + min-veri kontrolü + finally
  GPU `empty_cache`; `save/load_model` `torch.save(state_dict)` + **SHA256 checksum + 100MB DoS limit +
  `weights_only=True`** (PyTorch 1.13+ pickle-RCE koruması). MC-dropout CI.
- `ARIMATimeSeriesPredictor` (production): `MIN_OBSERVATIONS=10` → `_moving_average_fallback`; ARIMA(1,1,1)
  try/except → moving-average fallback (§5 "ARIMA min-gözlem fallback" **doğru**). 0 bulgu.

## S4a-7 — maintenance_predictor.py (339) — 0 bulgu (temiz)

Kural-tabanlı predictive maintenance: saf helper'lar guard'lı (`previous==0`, cap'ler); `_gather_inputs`
tek CTE sorgusu (N+1 yok) + parametreli; **tz-aware tarih matematiği doğru** (`last_dt` naive→UTC, sonra
`now(utc)-last_dt` → AUDIT-093'ün tersine doğru sürüm); `_predict_for_vehicle` saf hesap. İz (low): filo
medyanı tüm 90g tuketim satırlarını Python'a çekip `statistics.median` (SQL `percentile_cont` daha verimli).
0 bulgu.

> **S4a ara (12/26):** ML katmanı **istikrarlı yüksek kalite** — 12 dosyada yalnız 2 bulgu (AUDIT-125
> Kalman servisi ölü/await'siz, AUDIT-126 ensemble_service bloklayan ML). Kalan: advanced_lstm,
> driver_performance_ml, anomaly_clustering, route_similarity, predictors/, fleet/bus/carbon/health, benchmark, training/.

## S4a-8 — anomaly_clustering + vehicle_health_factor + fleet_efficiency_index + bus_factor + carbon_footprint + driver_performance_ml (6 dosya) — 0 bulgu (temiz)

- `anomaly_clustering`: DBSCAN saf fonksiyon, noise atılır, StandardScaler bilinçli kullanılmıyor (yorumlu).
- `vehicle_health_factor`: clamp(0.95-1.25), tz-aware (naive→UTC) + clock-skew guard (days<0→0), parametreli SQL,
  `apply_maintenance_factor` factor==1.0 no-op.
- `fleet_efficiency_index`: alt-skorlar clamp + cold-start default; tek CTE + `CASE WHEN mesafe_km>0` div-guard.
- `bus_factor`: PII-korumalı (score+km, ad/id yok), parametreli CTE, gap `max(0,..)` clamp, median fallback.
- `carbon_footprint`: Euro-sınıf CO2 faktör tablosu; `euro_class_for_year` guard'lı; `compute_fleet_carbon`
  parametreli + `total_km>0`/`benchmark>0` div-guard. (CO2 = litre×faktör — **doğru**; AUDIT-103 what_if'in
  yanlış faktör-farkı kullanımının tersine.)
- `driver_performance_ml`: LightGBM skor; `safe_ort_tuketim=max(ort,1e-6)`, toplam>0 div-guard'ları;
  survival-bias yorumla işaretli; not-trained'de basit fallback. İz (low): train metrikleri (R²/MAE)
  **eğitim setinde** ölçülüyor (held-out yok, optimistik — sadece log).
> 0 bulgu. **ML 18/26.**

## S4a-9 — route_similarity + ensemble_predictor(x2) + driver_route_profile + training/trainer + scheduler_task (6 dosya) — 0 bulgu (temiz)

- `route_similarity`: cosine sim `norm==0` guard, dist filtre, threshold.
- `ensemble_predictor.py` (re-export shim) + `predictors/ensemble_predictor.py` (inference-only wrapper, lazy
  import, FileNotFoundError) — temiz.
- `driver_route_profile`: route classify + median coefficient, `max(total,1)`/`tahmini>0` div-guard, fallback 1.0.
- `training/trainer.py`: thin facade, lazy import.
- `training/scheduler_task.py`: Celery `weekly_retrain` — `asyncio.run` **worker'da** (event loop değil) +
  per-araç try/except resilient → blocking fit burada doğru yer (**AUDIT-126'nın önerdiği** worker yolu).
> 0 bulgu. **ML 24/26.** Kalan: advanced_lstm, benchmark.

## S4a-10 — advanced_lstm.py (900) + benchmark.py (557) — 0 bulgu — core/ml TAMAM (26/26)

- `advanced_lstm` (torch BiLSTM-Attention + TCN + SARIMA/Holt-Winters/EMA, **dev-only**): tier-bazlı model
  seçimi (MIN_DEEP=90/STAT=30/HW=14/EMA=3); her seviyede graceful fallback; `c_std+1e-8`, `+1e-6`/`+1e-8`
  div-guard'ları; `train_model` Huber loss + grad-clip + early-stop + best-state restore; MC-dropout CI;
  `_deep_forecast` try/except → istatistiksel fallback; thread-safe lock. 0 bulgu.
- `benchmark` (MLBenchmark + ABTestFramework + EnsembleBenchmark): istatistiksel olarak titiz — Shapiro-Wilk
  normallik → paired t-test / Wilcoxon (nonparam), all-zero-diff guard; `ss_tot>1e-10` + `np.isfinite`
  guard'ları; MAPE non-zero mask. İz: `EnsembleBenchmark.benchmark_ensemble_models` async'te `fit()`/`predict()`
  bloklayan (AUDIT-126 sınıfı) ama **benchmark aracı** (admin/script), request yolu değil → low.

> **S4a (core/ml) TAMAMLANDI: 26/26 dosya, 2 bulgu (AUDIT-125, 126).** ML katmanı baştan sona örnek-savunmacı
> — checksum/weights_only model yükleme, NaN/Inf+div-by-zero guard, R²-normalize ağırlık, çok-seviyeli ARIMA
> fallback, tz-aware, PII-koruma, clamp. Sıradaki: **S4b** (core/ai 12 + services 10).

# S4b — core/ai + services

## S4b-1 — groq_service + llm_client + rag_engine + fuel_theft_classifier + context_builder (5 dosya) — 1 bulgu

Temiz/örnek: `rag_engine` (FAISS RAG — `SentenceTransformer(trust_remote_code=False)` RCE koruması,
`asyncio.to_thread` ile CPU-bound embed/search, multi-tenancy `user_id` filtresi, MAX_INDEX_SIZE/doc-size
OOM guard, load'da boyut-uyuşmazlık reset, JSON metadata (pickle yok)); `fuel_theft_classifier` (saf kural,
clamp'li skor, PII'siz açıklama, classify asla raise etmez — AUDIT-051 ML sınıflandırıcının tersine sağlam).
Bulgu AUDIT-127.

### AUDIT-127 — İki LLM istemcisi tutarsız PII/timeout: GroqService PII-maskelemiyor + explicit timeout yok
- Şiddet: medium
- Sınıf: security / arch-duplication
- Konum: groq_service.py:30-138 ↔ llm_client.py:25-120
- Durum: confirmed
- Kanıt:
    ```python
    # GroqService: PII maskeleme YOK, içerik ham Groq'a gider; timeout explicit set edilmemiş
    self.client = AsyncGroq(api_key=self.api_key)   # timeout param yok
    messages.append({"role": "user", "content": user_message})  # ham (mask yok)
    # LLMClient: _mask_pii (telefon + plaka) HER mesaja uygulanıyor + timeout=30 + retry
    result.append({"role": "system", "content": self._mask_pii(system_prompt)})
    ```
  İki paralel LLM istemcisi var: `GroqService` (groq SDK, `get_groq_service`) ve `LLMClient` (raw HTTP,
  `get_llm_client`). **Tutarsız**: LLMClient mesajlara PII maskesi (10-11 hane + plaka) + 30s timeout + retry
  uygular; **GroqService bunların HİÇBİRİNİ yapmaz** — kullanıcı/RAG context'i dış Groq API'sine **ham** (PII
  dahil) gider, explicit timeout yok (SDK default'una bağlı). GroqService daha yaygın kullanılıyor
  (smart_ai/anomaly/coaching). AUDIT-064 (ai_service.stream sanitize baypas) ile aynı tema: AI katmanında
  PII/prompt-handling tutarsız.
- Önerilen düzeltme: tek LLM istemci katmanı (ortak PII-scrub + timeout + retry); GroqService'i emekliye
  ayır ya da aynı `_mask_pii`/timeout'u uygula.

> İz (low/needs-verification): `context_builder` AI context'i için session'sız singleton repo'lar
> (`get_report_service`/`get_sefer_repo`/`get_yakit_repo`/`get_analiz_repo`) kullanıyor; `get_all`/
> `get_dashboard_summary` session gerektiriyorsa try/except ile yutulup "erişilemiyor" döner → AI **sessizce
> degrade** (gerçek veri yerine boş context). AUDIT-084/085/094 session'sız-singleton ailesiyle aynı kök.

## S4b-2 — driver_coaching_engine + recommendation_engine + chatbot + trip_planner + prompt_tuner + rag_sync_service (6) — 1 bulgu — core/ai TAMAM (12/12)

Temiz/örnek: `driver_coaching_engine` (PII'siz prompt, UoW session-aware, LLM→rule-based fallback,
Pydantic-validated parse + clamp); `chatbot` (jailbreak blocklist + length-limit + `asyncio.wait_for(30s)` +
LLMClient PII-mask); `prompt_tuner` (**örnek prompt-injection savunması** — `<user_input>` tag sarma +
breakout-strip + html.escape + "tag-dışı komutları yok say" + path-traversal guard); `trip_planner`
(clamp/cold-start/PII'siz reasons; iz: `_count_similar` aynı inp ile N× tekrar + `_score_drivers` N+1, low perf);
`rag_sync_service` (iz: initial_sync session'sız singleton get_all — başarısızsa RAG sessiz boş kalır,
AUDIT-084/085 ailesi). Bulgu AUDIT-128.

### AUDIT-128 — `RecommendationEngine`: get_all_recommendations gather'ı paylaşılan UoW session'ını eşzamanlı kullanıyor + tutarsız cache lock
- Şiddet: medium
- Sınıf: concurrency
- Konum: recommendation_engine.py:295-320 (get_all), 123,189 (locksuz cache read)
- Durum: confirmed
- Kanıt:
    ```python
    async with unit_of_work() as uow:                  # dış session contextvar'a set
        ...
        for a in araclar: sub_tasks.append(self.get_vehicle_recommendations(a["id"]))
        sub_results = await asyncio.gather(*sub_tasks)  # her sub_task `async with unit_of_work()` →
                                                         # contextvar reuse → AYNI session, EŞZAMANLI
    ...
    # get_driver_recommendations / get_fleet_recommendations: `if self._is_cache_valid(...)` LOCK YOK
    ```
  `get_all_recommendations` dış `unit_of_work()` açar (contextvar'a session set); gather'lanan alt-task'lar
  (get_vehicle_recommendations) kendi `unit_of_work()`'ünü açınca contextvar'daki dış session'ı **reuse** eder
  (non-owning). gather bunları **eşzamanlı** koşturur → aynı AsyncSession üzerinde eş-zamanlı operasyon →
  `InvalidRequestError` (AUDIT-099/044 sınıfı). Ayrıca `get_vehicle_recommendations` cache okumayı lock'la
  korurken `get_driver`/`get_fleet` **locksuz** okuyor → dict race.
- Önerilen düzeltme: alt-task'ları gather yerine ardışık await et (ya da her birine ayrı session geçir);
  tüm cache okumalarını `self._lock` altına al.
- Bağımlılık: AUDIT-099, AUDIT-044, unit_of_work contextvar reentrancy (AUDIT-075).

> **S4b core/ai TAMAMLANDI: 12/12 dosya, 2 bulgu (AUDIT-127 LLM tutarsızlık, AUDIT-128 reco concurrency).**
> AI katmanı güvenlik-bilinçli: prompt-injection guard, PII-free prompt, multi-tenancy RAG, trust_remote_code=False.

## S4b-3 — smart_ai_service + prediction_service (2) — 2 bulgu

Temiz yönler: smart_ai `ask()` PII-mask'lı LLMClient kullanır (AUDIT-127 doğru istemci); embed/search
`asyncio.to_thread` ile async-safe; FAISS `MAX_INDEX_SIZE=1M` + `MAX_DOC_SIZE=10k` clamp var.
prediction_service titiz orkestratör: entity fetch + ensemble ayrı UoW (session-aware), physics
`to_thread`, RED/YELLOW/GREEN confidence gating + physics fallback, D.4 maintenance factor tek noktadan.
İz (needs-verification): `explain_consumption` (l.850) session'sız `get_sofor_analiz_service().get_driver_stats`
çağırıyor → AUDIT-084 ailesi; `train_xgboost_model` ensemble.train'i to_thread'siz await ediyor → AUDIT-126.

### AUDIT-129 — KnowledgeBase her `add_document`'ta TÜM FAISS indeksini diske yazıyor (O(N) write amplification) + 1M cap'te sessiz öğrenme durması
- Şiddet: medium
- Sınıf: performance
- Konum: smart_ai_service.py:82 (save-on-every-add) + rag_engine.py:98 (cap, eviction yok)
- Durum: confirmed
- Kanıt:
    ```python
    # smart_ai_service.py add_document
    self.vector_store.add(doc_id, content, embedding, payload)
    await asyncio.to_thread(self.vector_store.save_index, str(KB_DIR))  # HER eklemede TAM serialize
    # rag_engine.py FAISSVectorStore.add
    if self.count() >= self.MAX_INDEX_SIZE:        # 1M
        logger.warning("Index full! ... Rejecting"); return   # eviction YOK → sessiz drop
    ```
  `learn_from_log`/`learn_from_event`/`_log_prediction_to_ai` her olayda/tahminde `add_document` çağırır;
  her çağrı **tüm indeksi** (max 1M döküman) yeniden diske serialize eder → O(N) disk yükü/ekleme,
  yüksek-frekanslı log akışında I/O patlaması. Ayrıca log/event içeriği timestamp taşıdığı için doc_id
  hep benzersiz → dedup yok → indeks 1M'e tırmanır; cap'e ulaşınca yeni dökümanlar **sessizce reddedilir**
  (eviction/LRU yok) → KB o noktadan sonra öğrenmeyi durdurur, kimse fark etmez.
- Önerilen düzeltme: save'i debounce/batch et (N eklemede bir veya periyodik flush); KB'ye LRU/TTL eviction
  ekle ya da log/event kategorilerini ring-buffer'la sınırla; cap-reddi metrik/uyarıya bağla.
- Bağımlılık: AUDIT-130 (per-prediction tetikleme), rag_engine FAISSVectorStore.

### AUDIT-130 — `_log_prediction_to_ai`: referanssız `asyncio.create_task` (GC'lenebilir) + her tahminde KB disk yazımı tetikler
- Şiddet: low
- Sınıf: reliability
- Konum: prediction_service.py:808-829
- Durum: confirmed
- Kanıt:
    ```python
    asyncio.create_task(_safe_teach())   # dönüş referansı saklanmıyor
    ```
  CPython'da `create_task` sonucuna referans tutulmazsa task çalışırken çöp toplanabilir (asyncio dokümante
  edilmiş tuzak) → AI'a tahmin logu sessizce kaybolabilir. Ayrıca `_safe_teach` → `smart_ai.teach` →
  `add_document` → AUDIT-129 tam-indeks yazımını **her predict_consumption** çağrısında tetikler.
- Önerilen düzeltme: task referansını bir set'te tut (`self._bg_tasks.add(t); t.add_done_callback(...)`)
  ya da outbox/queue üzerinden async-batch logla; KB yazımını AUDIT-129 düzeltmesine bağla.
- Bağımlılık: AUDIT-129.

## S4b-4 — external_service + route_service + time_series_service (3) — 2 bulgu (high 1)

Temiz: `external_service` (asyncio.Lock circuit-breaker, no-fabrication error payload, 429+Retry-After tek
retry, paylaşılan httpx client timeout=10). `time_series_service` mantığı örnek: hata taksonomisi
(TimeSeriesDataUnavailable→503 vs PRECONDITION_NOT_MET→409), to_thread filter/train/forecast, z-score
outlier, vehicle→fleet fallback — **ANCAK** veri kaynağı session'sız singleton (AUDIT-131).

### AUDIT-131 — TimeSeriesService TÜMÜYLE çalışmıyor: session'sız `get_analiz_repo()` → her train/predict/trend 503'e düşüyor (gerçek defect "degraded service" olarak maskeleniyor)
- Şiddet: high
- Sınıf: bug
- Konum: time_series_service.py:79-109 + analiz_repo.py:591,740-748 + base_repository.py:40-47
- Durum: confirmed
- Kanıt:
    ```python
    # time_series_service.get_daily_summary
    analiz_repo = get_analiz_repo()                       # session=None → session'sız SINGLETON
    rows = await analiz_repo.get_daily_summary_for_ml(...) # içeride: session = self.session
    # base_repository.session property: if self._session is None: raise RuntimeError("Database session
    #   not initialized in AnalizRepository")
    except Exception as exc:
        raise TimeSeriesDataUnavailable(...) from exc      # RuntimeError yutulur → 503 is_degraded
    ```
  `get_analiz_repo()` argümansız çağrılınca `_session=None` olan singleton'ı döner; `get_daily_summary_for_ml`
  `self.session`'a erişir → `RuntimeError("Database session not initialized")`. Bu hata
  `get_daily_summary`'nin `except Exception`'ında yakalanıp `TimeSeriesDataUnavailable`'a çevrilir →
  `train_model`/`predict_weekly`/`get_trend_analysis` **her zaman** `SERVICE_UNAVAILABLE` 503 `is_degraded=True`
  döner. Sonuç: zaman serisi tahmin/trend alt-sistemi production'da **tamamen ölü**, ama kod hatası geçici
  altyapı arızası gibi maskeleniyor (kimse fark etmez). Servis metodu session inject imkânı da sunmuyor.
- Önerilen düzeltme: `async with UnitOfWork() as uow: rows = await uow.analiz_repo.get_daily_summary_for_ml(...)`
  (veya `get_analiz_repo(session=uow.session)`). RuntimeError'ı `TimeSeriesDataUnavailable`'dan ayır ki
  gerçek kod defecti 503 maskesi ardına saklanmasın.
- Bağımlılık: AUDIT-084, AUDIT-085, AUDIT-094 (session'sız singleton ailesi), AUDIT-099.

### AUDIT-132 — route_service ORS yolunda circuit-breaker yok (weather'da var); ORS outage'ında istek başına ~15-30s asılı kalır
- Şiddet: low
- Sınıf: robustness
- Konum: route_service.py:83-310
- Durum: confirmed
- Kanıt:
    ```python
    response = await client.post(url, json=body, headers=headers, timeout=15)  # hgv
    if response.status_code == 403: ... response = await client.post(... timeout=15)  # car retry
    # ExternalService gibi CB / ardışık-hata sayacı YOK
    ```
  `ExternalService` weather için circuit-breaker uygularken `RouteService` ORS çağrılarında hiç CB tutmuyor;
  ayrıca weather servisinin private `_get_client()`'ını ödünç alıyor. ORS down olduğunda her güzergah isteği
  iki ardışık 15s timeout'a kadar (hgv→car) asılı kalır, hızlı-başarısızlık yok → bulk sefer import sırasında
  istekler birikip connection pool'u zorlar. Yine de hata yakalanıp error payload döner (crash yok).
- Önerilen düzeltme: ORS çağrılarını da paylaşılan bir circuit-breaker/with_async_retry pattern'ine al;
  private `_get_client` yerine kendi pooled client'ını kullan.
- Bağımlılık: AUDIT-129/130 değil; Open-Meteo rate-limit notuyla aynı dayanıklılık ailesi.

## S4b-5 — api/sefer_import_service (1) — 3 bulgu — S4 TAMAM

Temiz: master listeler UoW içinde çekilir (session-aware, session'sız singleton crash'i bilinçle çözülmüş,
yorum l.53-55); her satır `SeferCreate` Pydantic ile validate, hata satır-bazlı toplanır; tarih zorunlu
(datetime.now default kaldırılmış). İz (style): factory'nin enjekte ettiği 5 repo (arac/sofor/dorse/
lokasyon) `process_excel_import` içinde **hiç kullanılmıyor** (uow.* tercih edilir) → ölü injection.

### AUDIT-133 — bulk_add_sefer hatası tüm import'u count=0 + jenerik "Sistem hatası"na çökertir; satır-bazlı hatalar ve geçerli sayım kaybolur
- Şiddet: medium
- Sınıf: error-handling
- Konum: sefer_import_service.py:157-166
- Durum: confirmed
- Kanıt:
    ```python
    if valid_sefers:
        count = await self.sefer_service.bulk_add_sefer(valid_sefers)  # tek transaction
        return count, errors
    ...
    except Exception as e:                       # bulk_add içindeki herhangi DB hatası buraya
        return 0, [{"row": 0, "reason": f"Sistem hatası: {str(e)}"}]   # tüm satır hataları silinir
    ```
  Satır döngüsü Pydantic-seviye hataları izole eder; ama `bulk_add_sefer` tek transaction'da DB-seviye bir
  ihlalde (ör. net_kg check constraint, FK) patlarsa dış `except` devreye girer ve **zaten toplanmış
  per-row `errors` listesini atar**, `count=0` döner, hangi satırın patlattığını söylemez. Kullanıcı
  "geçerli 200 satırım vardı" derken "Sistem hatası" görür, neden belirsiz.
- Önerilen düzeltme: bulk_add'i topladığın `errors` ile birleştirerek raporla; mümkünse savepoint/parça
  bazlı ekleme ya da hatalı satırı tespit edip o satırı errors'a ekleyip kalanı kaydet.
- Bağımlılık: bulk_add_sefer net_kg constraint (CLAUDE.md), ImportService (ARCH-002 ikiz akış).

### AUDIT-134 — _resolve_master_id/_resolve_route_id satır başına O(masters) lineer tarama → O(satır×master) kuadratik
- Şiddet: low
- Sınıf: performance
- Konum: sefer_import_service.py:173-222
- Durum: confirmed
- Kanıt:
    ```python
    for item in master_list:        # her satır için tüm araç/şoför/dorse/route listesi taranır
        item_val = str(getattr(item, field, ...)).strip().upper()
        if item_val == search_norm: return ...
    ```
  Master listeler bir kez çekiliyor (iyi) ama her sefer satırı için 4 ayrı tam-liste taraması yapılıyor →
  N satır × M master = kuadratik. Büyük Excel + büyük filo'da yavaşlar.
- Önerilen düzeltme: master listeleri bir kez normalize-edilmiş dict index'e çevir
  (`{plaka_upper: id}`, `{ad_soyad_upper: id}`, `{(cikis,varis): id}`) → satır başına O(1).
- Bağımlılık: yok.

### AUDIT-135 — şoför `ad_soyad` birebir eşleşmede İLK eşleşeni döner; aynı adlı şoförlerde sefer sessizce yanlış şoföre bağlanır
- Şiddet: medium
- Sınıf: data-integrity
- Konum: sefer_import_service.py:179-191 (`_resolve_master_id`, field="ad_soyad")
- Durum: needs-verification
- Kanıt:
    ```python
    for item in master_list:
        if item_val == search_norm:
            return item.id ...        # İLK eşleşmede döner; çoğul eşleşme kontrolü yok
    ```
  Şoför çözümü ad-soyad string eşleşmesine dayanıyor. İki şoför aynı ada sahipse (yaygın Türkçe isimler)
  import sessizce ilk kaydı seçer → sefer yanlış şoföre atanır, hata üretilmez. Etki, `soforler.ad_soyad`
  üzerinde benzersizlik kısıtı olup olmamasına bağlı (verify gerek).
- Önerilen düzeltme: birden fazla eşleşmede hata fırlat ("birden çok şoför aynı ada sahip, sicil/ID ile
  ayır"); ya da Excel'de şoför ID/sicil sütunu zorunlu kıl.
- Bağımlılık: models.Sofor ad_soyad unique constraint? (S6 migrations / S2 schemas ile çapraz doğrula).

> **S4 TAMAMLANDI: core/ml (28) + core/ai (12) + services (10) = 50 dosya. Bulgular AUDIT-125..135 (11 bulgu, high 1=AUDIT-131).**
