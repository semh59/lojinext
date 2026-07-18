# Modül: ai_assistant

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

LLM sohbet (`/ai/chat`, `/ai/query`, `/ai/progress`, `/ai/status`), RAG
(FAISS + sentence-transformers) tabanlı context-grounding, Feature C sefer
planlama sihirbazı (`TripPlannerEngine`, `app/api/v1/endpoints/trips.py`
tarafından kullanılır — trip henüz taşınmadı, dalga 14), pilot geri
bildirimi (`/feedback` → Telegram OPS). Bu modül **hiçbir DB tablosuna
sahip değil** — FAISS dosya-tabanlı indeks (`app/data/ai_kb/` +
`app/data/vector_store/`), Docker `app_data` named volume üzerinden
çoklu-replica'da paylaşımlı persist ediyor. ✅ **DÜZELTİLDİ (2026-07-17,
aynı gün ikinci tur):** kök CLAUDE.md'nin bu iddiası önceden YANLIŞTI —
`rag_engine.py`'nin `save_to_disk`/`load_from_disk` varsayılanı
(`"data/vector_store"`) ve `knowledge_base.py`'nin `KB_DIR`'ı
(`<repo_root>/data/ai_kb`) ikisi de container'da `/app/data/*`'e
çözümleniyordu, oysa `docker-compose.yml`'ın mount ettiği paylaşımlı
volume `app_data:/app/app/data`'dır — indeksler paylaşımlı volume'ün
DIŞINDAYDI (dalga-12-öncesinden beri, `git show` ile doğrulanmış
pre-existing bug, regresyon değil). Path'ler `"app/data/vector_store"`
ve `<repo_root>/app/data/ai_kb` olarak düzeltildi (artık `/app/app/data/*`
— gerçek mount hedefi, kök CLAUDE.md'nin dokümantasyonuyla tutarlı).
Eski verinin taşınması GEREKMEZ — bug indeksin hiç kalıcı olmamasıydı,
kaybedilecek gerçek veri yoktu. Detay: `TASKS/bug-11-wave-b1-detective-
audit-2026-07-17.md` BÖLÜM C madde 10.

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
# (predict_trip_fuel/detect_anomalies + build_context.py'nin 5 fonksiyonu
#  2026-07-18 ölü-kod temizliğinde SİLİNDİ — bkz. aşağıdaki bölüm)

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
```

## ✅ Ölü-kod bulguları — 2026-07-18'de TAMAMI SİLİNDİ (kullanıcı kararı: "ölü kod yasak")

Aşağıdaki 5 kalemin hepsi 2026-07-18 tam-denetim düzeltme turunda, her
biri silinmeden önce grep ile sıfır-prod-çağıran TEKRAR doğrulanarak
silindi (public export'ları + shim'leri + kendi testleriyle birlikte:
`recommendation_engine.py`, `prompt_tuner.py`, `build_context.py`,
`AIService.predict_trip_fuel`/`detect_anomalies`/`_get_predictor_for_vehicle`/
`invalidate_predictor_cache`, `RAGEngine.index_alert`/`index_log`/
`index_event`/`bulk_index`). Tarihçe (silinmeden önceki bulgu kaydı):

1. **`AIService.predict_trip_fuel`/`detect_anomalies`/
   `_get_predictor_for_vehicle`** (`application/orchestrate_ai_response.py`)
   — `EnsembleFuelPredictor`'ı prediction_ml'in gerçek tahmin yolundan
   (Phase 4-5 `SeferFuelEstimator`, kök CLAUDE.md'de dokümante) BAĞIMSIZ
   ikinci bir kopyasıydı. Muhtemelen supersede edilmiş eski bir yoldu.
   `AIService` sınıfının kendisi CANLI kalıyor (chat path), yalnız bu üç
   metot + `_predictor_cache`/`_PREDICTOR_CACHE_TTL` silindi.
2. **`RecommendationEngine`** (`application/recommendation_engine.py`) —
   `get_all_recommendations`/`get_vehicle_recommendations`/vb. hiçbir
   prod endpoint'ten çağrılmıyordu. SİLİNDİ.
3. **`PromptTuner`** (`application/prompt_tuner.py`) — `build_tuned_prompt`
   hiçbir yerden çağrılmıyordu; gerçek chat akışı
   (`AIService.generate_response`) kendi basit `_sanitize_prompt`'unu
   kullanıyor. SİLİNDİ.
4. **`build_context.py`'nin TÜM public API'si** (`build_system_context`/
   `build_vehicle_context`/`build_driver_context`/`build_analysis_context`/
   `build_full_context`) — repo-genelinde sıfır çağıran (testler hariç).
   Canlı `/ai/chat` yolu (`AIService.generate_response` →
   `orchestrate_ai_response.py`'nin kendi ÖZEL, KOPYA `_build_context()`
   metodu) bunları hiç çağırmıyordu. Dosyasıyla birlikte SİLİNDİ.
5. **`RAGEngine.index_log`/`index_event`/`bulk_index`** (`bulk_index`
   yalnız `index_alert`'i çağırıyordu) — repo-genelinde sıfır prod
   çağıran (testler hariç). SİLİNDİ (`index_alert` de yalnız
   `bulk_index`'in kendisi tarafından çağrıldığı için birlikte gitti).

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalan — 8 adet, hepsi gerçek mutable state/DI gerekçeli)

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
   constructor'da kurulan `groq` client'ı container lazy-property
   singleton'ı olarak yaşar (2026-07-18: `_predictor_cache` ölü
   metotlarla birlikte silindi, gerekçe client-DI'ya güncellendi).
7. **`SmartAIService`+`KnowledgeBase`** (`application/knowledge_base.py`)
   — kendi FAISS store'u + SentenceTransformer model + throttled-save
   state (`_last_saved`/`_adds_since_save`). RAGEngine'den TAMAMEN
   BAĞIMSIZ ikinci bir FAISS store (`app/data/ai_kb/` vs RAGEngine'in
   `data/vector_store/`) — iki ayrı bilgi tabanı var, birleştirilmedi
   (davranış değişikliği, kapsam dışı).
8. ~~`RecommendationEngine`~~ / ~~`PromptTuner`~~ — 2026-07-18 ölü-kod
   temizliğinde silindi.
9. **`TripPlannerEngine`** (`application/plan_trip.py`) — kendi
   docstring'i "Stateless engine. Endpoint her istekte yeniden
   oluşturur" diyor; constructor'ı `prediction_service`'i DI olarak
   tutuyor — `RouteSimulator`/`LokasyonHydrator`/`DriverCoachingEngine`
   ile aynı "tek cohesive pipeline + constructor-injected dependency"
   gerekçesi.

`ContextBuilder` (eski `app/core/ai/context_builder.py`) B.1'e göre
SINIF OLARAK KALMADI — constructor'ı `pass` idi (anlamlı state yok,
yalnız lazy-import property'ler), `application/build_context.py`'de free
function'lara bölünmüştü (AnalizService/CostAnalyzer ile aynı gerekçe);
o dosya artık 2026-07-18'de ölü kod olarak tamamen silindi.

## Yayınladığı / dinlediği event'ler (events.py)

Yayınlamıyor (DB tablosu sahibi değil). `RAGSyncService` 6 event'e abone
(`ARAC_ADDED/UPDATED`, `SOFOR_ADDED/UPDATED`, `SEFER_ADDED/UPDATED`) —
kayıt/wiring **CANLI** (`main.py` lifespan startup'ında gerçekten
`initialize()` çağrılıyor). ⚠️ Not: bu abonelikler `Event`/`EventType`
(ham `dict` payload) kullanıyor, `events.py`'de tipli DTO **yok** — bu
modül yalnız DİNLEYİCİ, publisher değil (2026-07-17 compliance
denetiminde bulunan doküman/gerçeklik farkı — bu bölüm önceden "DTO'lara
bağlı" diyordu, bu yanlıştı, düzeltildi).

✅ **DÜZELTİLDİ (2026-07-17, aynı gün ikinci tur):** 3 gerçek artımlı-
senkron bug'ı (dalga-12-öncesinden beri var, `git show` ile doğrulanmıştı,
kullanıcı onayıyla düzeltildi):
1. `_on_sefer_changed` prod'da hep no-op'tu — hiçbir gerçek sefer-event
   publisher'ı `"result"` anahtarını kullanmıyordu. Artık `"sefer_id"`
   (ör. `sefer_write_service.py`) VE `"id"` (ör.
   `sefer_analiz_service.py`'nin `publish_simple_async(..., id=t_id,
   ...)` deseni) anahtarlarını da kontrol edip `UnitOfWork` üzerinden
   `uow.sefer_repo.get_by_id(...)` ile çekiyor.
2. `_on_arac_changed`/`_on_sofor_changed`'in gerçek koşulda HER ZAMAN
   girilen int-branch'i session'sız singleton repo'nun `.get_by_id()`'ini
   çağırıyordu — `RuntimeError` fırlatıp event-bus tarafından sessizce
   yutuluyordu. Artık `initial_sync()`'in zaten kullandığı `UnitOfWork`
   deseniyle (`uow.arac_repo`/`uow.sofor_repo`) çekiyor.
3. Doğrulama: `app/tests/unit/test_rag_sync_service_coverage.py`'ye 4 yeni
   regresyon testi eklendi (sefer_id/id anahtar varyantları), 2 mevcut
   test `UnitOfWork` mock desenine çevrildi (eski `get_arac_repo`/
   `get_sofor_repo` patch'i artık koda hiç değmiyordu — testler YANLIŞLIKLA
   yeşildi). Gerçek Docker+DB'de 142 passed.

## Şema & tablo sahipliği

Yok. FAISS dosya-tabanlı indeks (iki bağımsız store — bkz. sınıf
istisnaları #2/#7).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **analytics_executive (taşındı)**: `AIService._build_context` →
  `uow.analiz_repo` (get_dashboard_stats/get_recent_unread_alerts).
  (Eski `build_context.py`'nin fleet/fuel/reports/analytics/driver
  bağlantıları dosyayla birlikte 2026-07-18'de silindi.)
- **driver (taşındı)**: `plan_trip.py` → `v2.modules.driver.public.
  {classify_route, get_route_profile_sofor, get_score_breakdown_sofor}`.
- **notification (taşındı)**: `api/feedback_routes.py` →
  `v2.modules.notification.public.notify_feedback` (2026-07-18: public'e
  çevrildi).
- **anomaly (taşındı, ters yön)**: `generate_cluster_insight.py` →
  `v2.modules.ai_assistant.public.GroqService` (2026-07-18: public'e
  çevrildi).
- **driver (taşındı, ters yön)**: `generate_coaching.py` →
  `v2.modules.ai_assistant.public.get_groq_service` (2026-07-18: public'e
  çevrildi, lazy import — döngü notu driver/CLAUDE.md'de).
- **prediction_ml (taşınmadı, dalga 13, ters yön)**:
  `app/services/prediction_service.py::_log_prediction_to_ai` bu modülün
  `get_smart_ai().teach()`'ini best-effort arka plan görevi olarak
  çağırıyor. `app/workers/tasks/prediction_tasks.py` bu modülün
  `public.get_llm_client()`'ını çağırıyor (2026-07-18: public'e çevrildi).
- **trip (taşınmadı, dalga 14, geçici bağımlılık)**:
  `plan_trip.py` `app.database.unit_of_work.UnitOfWork` üzerinden
  `lokasyon_repo`/`arac_repo`/`sofor_repo`/`sefer_repo`'ya (route_analysis/
  weather fetch, shortlist, context) doğrudan erişiyor — trip taşınınca
  güncellenecek (location/route_simulation dalga 1'deki geçici
  bağımlılıkla aynı desen). `app/api/v1/endpoints/trips.py` (trip
  modülünün kendisi) bu modülün `public.py`'sinden `TripPlannerEngine`/
  `PlanInput`/`PlanResult`/sihirbaz şemalarını (`DriverSuggestion`/
  `PlanWizardRequest`/`PlanWizardResponse`/`VehicleSuggestion`,
  2026-07-18'de public'e eklendi) import ediyor.
- **route_simulation (taşınmadı kısım, geçici)**: `plan_trip.py`
  `app.core.container.get_container().weather_service` (henüz taşınmayan
  `weather_service.py`) ve `app.core.ml.route_similarity.find_similar_trips`
  (henüz taşınmayan prediction_ml/route_similarity) çağırıyor.
- **fuel (taşındı)**: ✅ **DÜZELTİLDİ (2026-07-17, aynı gün ikinci tur)** —
  `api/ai_routes.py::_fuel_trend_chart` fuel'in `yakit_alimlari`
  tablosuna API katmanından doğrudan ham SQL atıyordu (dalga-12-öncesinden
  beri, `git show` ile doğrulanmış pre-existing katman ihlali). Sorgu
  `v2/modules/fuel/infrastructure/repository.py::YakitRepository.
  get_monthly_cost_trend()` + `application/list_yakit.py::
  get_monthly_cost_trend()` olarak fuel'e taşındı (birebir aynı SQL,
  davranış değişikliği yok), `fuel.public`'ten export edildi.
  `ai_routes.py` artık `v2.modules.fuel.public.get_monthly_cost_trend`'i
  çağırıyor, `SessionDep`'e bağımlılığı kalmadı. Detay:
  `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md` BÖLÜM C madde 11.

## İzin verilen / yasak import'lar (import-linter özeti)

FAZ1'in import-linter gate'i henüz aktif değil (rapor modu), ama
kontratlar 2026-07-18'den beri fiilen KEPT: diğer modüller yalnız
`v2.modules.ai_assistant.public`/`.events`'i import eder (anomaly/driver'ın
eski groq_client doğrudan importları aynı gün public'e çevrildi). Bu
modülün kendisi de fleet/fuel/analytics_executive/driver/reports/
notification'a hep `public.py` üzerinden gidiyor.

## Modüle özel iş kuralları & gotcha'lar

- **İki bağımsız FAISS store** (sınıf istisnaları #2/#7): `RAGEngine`
  (`app/data/vector_store/`) ve `KnowledgeBase` (`app/data/ai_kb/`) —
  birleştirilmedi (davranış değişikliği, kapsam dışı). İkisi de Docker
  `app_data` volume mount hedefinin (`/app/app/data`) İÇİNDE (2026-07-17
  path düzeltmesi).
- **RAG artımlı senkron anahtarları**: sefer publisher'ları `sefer_id`
  VEYA `id` anahtarı gönderir (tutarsız — publisher tekilleştirme ayrı
  iş); `_on_sefer_changed` ikisini de kabul eder. Arac/şoför event'leri
  her zaman `{"result": <int id>}` taşır → handler `UnitOfWork` içinde
  `get_by_id` çağırır (session'sız singleton çağrısı YASAK — 2026-07-17
  bug fix'i).
- **Prompt guard'ı `AIService._sanitize_prompt`'tadır** (REDACT desenleri +
  1000 karakter kesme) — ayrı bir PromptTuner katmanı YOK (2026-07-18'de
  ölü kod olarak silindi; sanitizasyon canlı yolun kendi içinde).
- **`get_ai_service()` container'a delege eder** (`get_container().ai_service`)
  — testlerde `container_mod` yerine tüketen route modülünün adını patch'le.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`sohbet`=chat, `bağlam`=context, `bilgi tabanı`=knowledge base,
`gömme/vektör temsili`=embedding, `benzerlik eşiği`=similarity threshold,
`istem`=prompt, `sefer planlama sihirbazı`=trip planner wizard,
`aday`=candidate (vehicle/driver şortlist üyesi).

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_ai_service*.py` → patch hedefi
  `v2.modules.ai_assistant.application.orchestrate_ai_response.<fn>`.
  (`test_ai_service_more.py` ve `test_context_builder_coverage.py` —
  test ettikleri ölü kodla birlikte 2026-07-18'de silindi.)
- `app/tests/unit/test_rag_engine_coverage.py`/`test_rag_engine_more.py`/
  `tests/test_rag_engine.py` (kök `tests/`!) → import path
  `v2.modules.ai_assistant.infrastructure.rag.rag_engine`.
- `app/tests/unit/test_rag_sync_service_coverage.py` → import path
  `v2.modules.ai_assistant.infrastructure.rag.rag_sync_service`.
- `app/tests/unit/test_groq_service_coverage.py`/`test_llm_client.py`/
  `tests/core/test_llm_client_remote.py` (kök `tests/`!) → import path
  `v2.modules.ai_assistant.infrastructure.llm.{groq_client,raw_client}`.
- (`test_recommendation_engine_coverage.py`/`test_recommendation_more.py`/
  `test_prompt_tuner_coverage.py` — test ettikleri sınıflarla birlikte
  2026-07-18'de silindi.)
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
  güncellendi; PromptTuner/RecommendationEngine'e değinen testler
  2026-07-18'de dosyalarıyla birlikte kaldırıldı, geri kalan davranış aynı.
- `app/tests/sections/test_section_1_backend_core.py` → import path
  güncellendi (birden çok ai_assistant sembolü referans alıyor).
