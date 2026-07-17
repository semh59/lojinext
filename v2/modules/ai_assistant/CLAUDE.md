# Modül: ai_assistant

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

LLM sohbet (`/ai/chat`, `/ai/query`, `/ai/progress`, `/ai/status`), RAG
(FAISS + sentence-transformers) tabanlı context-grounding, Feature C sefer
planlama sihirbazı (`TripPlannerEngine`, `app/api/v1/endpoints/trips.py`
tarafından kullanılır — trip henüz taşınmadı, dalga 14), pilot geri
bildirimi (`/feedback` → Telegram OPS). Bu modül **hiçbir DB tablosuna
sahip değil** — FAISS dosya-tabanlı indeks (`app/data/ai_kb/` +
`data/vector_store/`), Docker `app_data` named volume üzerinden
çoklu-replica'da paylaşımlı persist ediyor (kök CLAUDE.md'de dokümante).

NE YAPMAZ: gerçek ML yakıt tahmini (bu artık `sefer_fuel_estimator.py`'nin
işi, Phase 4-5 SeferFuelEstimator — bkz. aşağıdaki ölü-kod notu),
sefer/araç/şoför CRUD (fleet/driver/trip'in işi — bu modül yalnız context
okumak için onlara bakar).

## Dosya envanteri düzeltmesi (task dosyası hatalıydı)

`TASKS/modules/ai-assistant.md`'nin 15 dosyalık envanteri STALE:
`app/core/ai/chatbot.py` **hiç var olmamış** (gerçek `app/core/ai/`
içeriği 9 dosyaydı, chatbot.py değil). Gerçek envanter 14 dosya: 9 core/ai
+ `api/v1/endpoints/{ai,feedback}.py` + `core/services/ai_service.py` +
`schemas/trip_planner.py` + `services/smart_ai_service.py`. Route sayısı
task dosyasının dediği gibi **5** (ai.py=4 + feedback.py=1) — bu doğruydu.

## Public API (public.py imzaları)

```python
# Chat / status (canlı — /ai/* endpoint'leri)
AIService, get_ai_service() -> AIService
    .generate_response(user_input) -> str
    .get_progress() -> dict
    .predict_trip_fuel(...) / .detect_anomalies(...)   # ÖLÜ KOD, bkz. aşağı

# Context builder (B.1: free function'lara bölündü)
build_system_context() / build_vehicle_context(arac_id) /
build_driver_context(sofor_id) / build_analysis_context() /
build_full_context(arac_id=None, sofor_id=None, include_analysis=False)

# RAG
RAGEngine, get_rag_engine() -> RAGEngine
RAGSyncService, get_rag_sync_service() -> RAGSyncService   # main.py'de CANLI wire

# Knowledge base (ayrı FAISS store — RAGEngine'den bağımsız)
SmartAIService, KnowledgeBase, get_smart_ai() -> SmartAIService

# Feature C sefer planlama
TripPlannerEngine(prediction_service), PlanInput, PlanResult,
VehicleCandidate, DriverCandidate

# Dış LLM istemcileri (iki bağımsız client, farklı çağıranlar)
GroqService, get_groq_service() -> GroqService   # SDK tabanlı, admin-key resolve
LLMClient, get_llm_client() -> LLMClient          # raw-httpx, PII-mask + retry

# Ölü kod (taşındı, silinmedi — bkz. aşağı)
RecommendationEngine, get_recommendation_engine()
PromptTuner, get_prompt_tuner()
```

## 🔴 Üç ayrı ölü-kod bulgusu (taşındı, SİLİNMEDİ — kullanıcı kararı bekliyor)

Bu dalgada B.1 sınıf-istisna taraması sırasında üç bağımsız "sadece
testler çağırıyor, hiçbir prod endpoint/servis çağırmıyor" deseni bulundu
(grep ile doğrulandı, InsightEngine/dalga 11 ile aynı gerekçeyle
SİLİNMEDİ — davranış değişikliği kullanıcı kararı gerektirir):

1. **`AIService.predict_trip_fuel`/`detect_anomalies`/
   `_get_predictor_for_vehicle`** (`application/orchestrate_ai_response.py`)
   — `EnsembleFuelPredictor`'ı prediction_ml'in gerçek tahmin yolundan
   (Phase 4-5 `SeferFuelEstimator`, kök CLAUDE.md'de dokümante) BAĞIMSIZ
   ikinci bir kopyası. Muhtemelen supersede edilmiş eski bir yol —
   prediction_ml (dalga 13) taşınırken bu çakışma tekrar gündeme
   gelmeli. `AIService` sınıfı kendisi CANLI (chat path), yalnız bu üç
   metot ölü.
2. **`RecommendationEngine`** (`application/recommendation_engine.py`) —
   `get_all_recommendations`/`get_vehicle_recommendations`/vb. hiçbir
   prod endpoint'ten çağrılmıyor. `_cache`/`_cache_time`/`_lock` gerçek
   mutable state taşıdığı için B.1 sınıf istisnası (cache tutan sınıf,
   RAGEngine ile aynı gerekçe) — ama işlevsel olarak ölü.
3. **`PromptTuner`** (`application/prompt_tuner.py`) — `build_tuned_prompt`
   hiçbir yerden çağrılmıyor; gerçek chat akışı (`AIService.generate_response`)
   kendi basit `_sanitize_prompt`'unu kullanıyor, bu sınıfı hiç çağırmıyor.
   `self.data` (dosyadan yüklenen JSON) gerçek state taşıdığı için B.1
   sınıf istisnası.

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalan — 9 adet, hepsi gerçek mutable state/DI gerekçeli)

1. **`FAISSVectorStore`** (`infrastructure/rag/vector_store.py`) — FAISS
   index + threading.Lock, gerçek mutable state.
2. **`RAGEngine`** (`infrastructure/rag/rag_engine.py`) — embedder/index/
   status, background-thread init.
3. **`RAGSyncService`** (`infrastructure/rag/rag_sync_service.py`) —
   sync lock/is_syncing state; `main.py` lifespan'de gerçekten wire
   edilmiş (bkz. events.py — diğer modüllerin "hiç tetiklenmiyor" ölü
   event-subscriber bulgusundan FARKLI, bu CANLI).
4. **`GroqService`** (`infrastructure/llm/groq_client.py`) — kurulu
   `AsyncGroq` client + api_key state.
5. **`LLMClient`** (`infrastructure/llm/raw_client.py`) — config state
   (api_key/model/base_url/timeout/max_retries), gerçek constructor
   parametreleri.
6. **`AIService`** (`application/orchestrate_ai_response.py`) —
   `_predictor_cache` (TTL cache, Dict[int, tuple]) gerçek mutable state
   (RecommendationEngine'in cache'i ile aynı gerekçe).
7. **`SmartAIService`+`KnowledgeBase`** (`application/knowledge_base.py`)
   — kendi FAISS store'u + SentenceTransformer model + throttled-save
   state (`_last_saved`/`_adds_since_save`). RAGEngine'den TAMAMEN
   BAĞIMSIZ ikinci bir FAISS store (`app/data/ai_kb/` vs RAGEngine'in
   `data/vector_store/`) — iki ayrı bilgi tabanı var, birleştirilmedi
   (davranış değişikliği, kapsam dışı).
8. **`RecommendationEngine`** (yukarıda ölü-kod olarak da sayıldı) — cache
   state gerekçesiyle sınıf.
9. **`PromptTuner`** (yukarıda ölü-kod olarak da sayıldı) — dosya-yüklü
   state gerekçesiyle sınıf.
10. **`TripPlannerEngine`** (`application/plan_trip.py`) — kendi
    docstring'i "Stateless engine. Endpoint her istekte yeniden
    oluşturur" diyor; constructor'ı `prediction_service`'i DI olarak
    tutuyor — `RouteSimulator`/`LokasyonHydrator`/`DriverCoachingEngine`
    ile aynı "tek cohesive pipeline + constructor-injected dependency"
    gerekçesi.

`ContextBuilder` (eski `app/core/ai/context_builder.py`) B.1'e göre
SINIF OLARAK KALMADI — constructor'ı `pass` idi (anlamlı state yok,
yalnız lazy-import property'ler), `application/build_context.py`'de free
function'lara bölündü (AnalizService/CostAnalyzer ile aynı gerekçe).

## Yayınladığı / dinlediği event'ler (events.py)

Yayınlamıyor (DB tablosu sahibi değil). `RAGSyncService` 6 event'e abone
(`ARAC_ADDED/UPDATED`, `SOFOR_ADDED/UPDATED`, `SEFER_ADDED/UPDATED`) —
**CANLI**, `main.py` lifespan startup'ında gerçekten `initialize()`
çağrılıyor (diğer modüllerin ölü event-subscriber bulgusundan farklı).

## Şema & tablo sahipliği

Yok. FAISS dosya-tabanlı indeks (iki bağımsız store — bkz. sınıf
istisnaları #2/#7).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **fleet (taşındı)**: `build_context.py` → `v2.modules.fleet.infrastructure.
  vehicle_repository.get_arac_repo()`.
- **fuel (taşındı)**: `build_context.py` → `v2.modules.fuel.infrastructure.
  repository.get_yakit_repo()`.
- **reports (taşındı)**: `build_context.py` → `v2.modules.reports.public.
  get_dashboard_summary()`.
- **analytics_executive (taşındı)**: `build_context.py` →
  `v2.modules.analytics_executive.infrastructure.executive_read_models.
  get_analiz_repo()`.
- **driver (taşındı)**: `build_context.py`/`recommendation_engine.py`/
  `plan_trip.py` → `v2.modules.driver.public.{evaluate_driver,
  get_rankings, classify_route, get_route_profile_sofor,
  get_score_breakdown_sofor}`.
- **notification (taşındı)**: `api/feedback_routes.py` →
  `v2.modules.notification.infrastructure.telegram_client.notify_feedback`.
- **anomaly (taşındı, ters yön)**: `v2/modules/anomaly/application/
  generate_cluster_insight.py` bu modülün `infrastructure.llm.groq_client.
  get_groq_service()`'ini doğrudan çağırıyor.
- **driver (taşındı, ters yön)**: `v2/modules/driver/application/
  generate_coaching.py` aynı şekilde `get_groq_service()`'i çağırıyor.
- **prediction_ml (taşınmadı, dalga 13, ters yön)**:
  `app/services/prediction_service.py::_log_prediction_to_ai` bu modülün
  `get_smart_ai().teach()`'ini best-effort arka plan görevi olarak
  çağırıyor. `app/workers/tasks/prediction_tasks.py` bu modülün
  `infrastructure.llm.raw_client.get_llm_client()`'ını çağırıyor.
- **trip (taşınmadı, dalga 14, geçici bağımlılık)**:
  `plan_trip.py`/`build_context.py` `app.database.unit_of_work.UnitOfWork`
  üzerinden `lokasyon_repo`/`arac_repo`/`sofor_repo`/`sefer_repo`'ya
  (route_analysis/weather fetch, shortlist, context) doğrudan erişiyor —
  trip taşınınca güncellenecek (location/route_simulation dalga 1'deki
  geçici bağımlılıkla aynı desen). `app/api/v1/endpoints/trips.py`
  (trip modülünün kendisi) bu modülün `public.py`'sinden
  `TripPlannerEngine`/`PlanInput`/`PlanResult` import ediyor.
- **route_simulation (taşınmadı kısım, geçici)**: `plan_trip.py`
  `app.core.container.get_container().weather_service` (henüz taşınmayan
  `weather_service.py`) ve `app.core.ml.route_similarity.find_similar_trips`
  (henüz taşınmayan prediction_ml/route_similarity) çağırıyor.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_ai_service*.py` → patch hedefi
  `v2.modules.ai_assistant.application.orchestrate_ai_response.<fn>`.
- `app/tests/unit/test_context_builder_coverage.py` → class-mock'tan
  free-function-mock'a çevrildi (`v2.modules.ai_assistant.application.
  build_context.<fn>` patch).
- `app/tests/unit/test_rag_engine_coverage.py`/`test_rag_engine_more.py`/
  `tests/test_rag_engine.py` (kök `tests/`!) → import path
  `v2.modules.ai_assistant.infrastructure.rag.rag_engine`.
- `app/tests/unit/test_rag_sync_service_coverage.py` → import path
  `v2.modules.ai_assistant.infrastructure.rag.rag_sync_service`.
- `app/tests/unit/test_groq_service_coverage.py`/`test_llm_client.py`/
  `tests/core/test_llm_client_remote.py` (kök `tests/`!) → import path
  `v2.modules.ai_assistant.infrastructure.llm.{groq_client,raw_client}`.
- `app/tests/unit/test_recommendation_engine_coverage.py`/
  `test_recommendation_more.py` → import path
  `v2.modules.ai_assistant.application.recommendation_engine`.
- `app/tests/unit/test_prompt_tuner_coverage.py` → import path
  `v2.modules.ai_assistant.application.prompt_tuner`.
- `app/tests/unit/test_trip_planner_engine.py`/`test_trip_planner_more.py`/
  `test_trip_planner_scoring.py`/`test_trip_planner_weather.py` → import
  path `v2.modules.ai_assistant.application.plan_trip` (engine) +
  `v2.modules.ai_assistant.domain.planner_scoring` (saf skorlama testleri).
  `test_trip_planner_scoring.py` özellikle domain modülüne taşındı (saf
  fonksiyonlar, DB yok).
- `app/tests/unit/test_smart_ai_service_coverage.py` → import path
  `v2.modules.ai_assistant.application.knowledge_base`.
- `app/tests/integration/test_plan_wizard_endpoint.py` → endpoint hâlâ
  `app/api/v1/endpoints/trips.py`'de (trip taşınmadı), yalnız import path
  güncellendi.
- `app/tests/security/test_ai_security.py`, `app/tests/unit/test_ai_security.py`,
  `app/tests/test_ai_security.py`, `app/tests/unit/test_ai_privacy.py`,
  `app/tests/unit/test_ai_deep_remediation.py`, `app/tests/unit/test_ai/
  test_rag_and_ai_service.py`, `tests/test_chatbot.py` (kök `tests/`!),
  `tests/test_security_penetration.py` (kök `tests/`!) → import path
  güncellendi, davranış aynı.
- `app/tests/sections/test_section_1_backend_core.py` → import path
  güncellendi (birden çok ai_assistant sembolü referans alıyor).
