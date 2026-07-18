"""
TIR Yakıt Takip - AI Modül

Shim (dalga 12) — gerçek kod v2/modules/ai_assistant/'a taşındı.
`ContextBuilder`/`build_context` ve `RecommendationEngine`/`PromptTuner`
2026-07-18 ölü-kod temizliğinde tamamen silindi (hiçbir prod çağıranı
yoktu) — burada da re-export edilmiyor.
"""

from app.core.ai.groq_service import GroqService, get_groq_service  # noqa: F401

__all__ = ["GroqService", "get_groq_service"]
