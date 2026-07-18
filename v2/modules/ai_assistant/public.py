"""Public surface of the ai_assistant module.

Other modules that need to call into ai_assistant should import from here,
not from ``application/``, ``domain/``, or ``infrastructure/`` directly.
This module owns no DB table (FAISS dosya-tabanlı indeks, `app/data/ai_kb/`
+ `data/vector_store/`, Docker `app_data` named volume üzerinden persist).

`trip` (dalga 14, henüz taşınmadı) `TripPlannerEngine`/`PlanInput`/
`PlanResult`/sihirbaz şemaları için doğrudan bu public surface'i kullanır
(`app/api/v1/endpoints/trips.py`). `anomaly`/`driver` (taşındı) da
`GroqService`/`get_groq_service`'e buradan erişir (2026-07-18 denetiminde
public'e çevrildi).

2026-07-18 ölü-kod temizliği: `RecommendationEngine`/`PromptTuner`/
`build_context.py` (5 fonksiyon) hiçbir prod yolundan çağrılmadığı
doğrulanarak SİLİNDİ — export'ları da kaldırıldı.
"""

from v2.modules.ai_assistant.application.knowledge_base import (
    KnowledgeBase,
    SmartAIService,
    get_smart_ai,
)
from v2.modules.ai_assistant.application.orchestrate_ai_response import (
    AIService,
    get_ai_service,
)
from v2.modules.ai_assistant.application.plan_trip import TripPlannerEngine
from v2.modules.ai_assistant.domain.planner_scoring import (
    DriverCandidate,
    PlanInput,
    PlanResult,
    VehicleCandidate,
)
from v2.modules.ai_assistant.infrastructure.llm.groq_client import (
    GroqService,
    get_groq_service,
)
from v2.modules.ai_assistant.infrastructure.llm.raw_client import (
    LLMClient,
    LLMMessage,
    get_llm_client,
)
from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
    RAGEngine,
    get_rag_engine,
    is_rag_available,
)
from v2.modules.ai_assistant.infrastructure.rag.rag_sync_service import (
    RAGSyncService,
    get_rag_sync_service,
)
from v2.modules.ai_assistant.schemas import (
    DriverSuggestion,
    PlanWizardRequest,
    PlanWizardResponse,
    VehicleSuggestion,
)

__all__ = [
    "AIService",
    "get_ai_service",
    "SmartAIService",
    "KnowledgeBase",
    "get_smart_ai",
    "TripPlannerEngine",
    "PlanInput",
    "PlanResult",
    "VehicleCandidate",
    "DriverCandidate",
    "GroqService",
    "get_groq_service",
    "LLMClient",
    "LLMMessage",
    "DriverSuggestion",
    "PlanWizardRequest",
    "PlanWizardResponse",
    "VehicleSuggestion",
    "get_llm_client",
    "RAGEngine",
    "get_rag_engine",
    "is_rag_available",
    "RAGSyncService",
    "get_rag_sync_service",
]
