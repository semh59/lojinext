"""Public surface of the ai_assistant module.

Other modules that need to call into ai_assistant should import from here,
not from ``application/``, ``domain/``, or ``infrastructure/`` directly.
This module owns no DB table (FAISS dosya-tabanlı indeks, `app/data/ai_kb/`
+ `data/vector_store/`, Docker `app_data` named volume üzerinden persist).

`trip` (dalga 14, henüz taşınmadı) `TripPlannerEngine`/`PlanInput`/
`PlanResult` için doğrudan bu public surface'i kullanır
(`app/api/v1/endpoints/trips.py`). `anomaly`/`driver` (taşındı)
`get_groq_service()`'i doğrudan `infrastructure/llm/groq_client.py`'den
import ediyor (bkz. CLAUDE.md "senkron konuştuğu modüller").
"""

from v2.modules.ai_assistant.application.build_context import (
    build_analysis_context,
    build_driver_context,
    build_full_context,
    build_system_context,
    build_vehicle_context,
)
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
from v2.modules.ai_assistant.application.prompt_tuner import (
    PromptTuner,
    get_prompt_tuner,
)
from v2.modules.ai_assistant.application.recommendation_engine import (
    Recommendation,
    RecommendationEngine,
    get_recommendation_engine,
)
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
    "RecommendationEngine",
    "Recommendation",
    "get_recommendation_engine",
    "PromptTuner",
    "get_prompt_tuner",
    "GroqService",
    "get_groq_service",
    "LLMClient",
    "get_llm_client",
    "RAGEngine",
    "get_rag_engine",
    "is_rag_available",
    "RAGSyncService",
    "get_rag_sync_service",
    "build_system_context",
    "build_vehicle_context",
    "build_driver_context",
    "build_analysis_context",
    "build_full_context",
]
