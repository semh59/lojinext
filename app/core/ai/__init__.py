"""
TIR Yakıt Takip - AI Modül

Shim (dalga 12) — gerçek kod v2/modules/ai_assistant/'a taşındı.
`ContextBuilder` sınıfı B.1 gereği free function'lara bölündüğü için
artık burada re-export edilmiyor (bkz. v2/modules/ai_assistant/
application/build_context.py).
"""

from app.core.ai.groq_service import GroqService, get_groq_service  # noqa: F401

__all__ = ["GroqService", "get_groq_service"]
