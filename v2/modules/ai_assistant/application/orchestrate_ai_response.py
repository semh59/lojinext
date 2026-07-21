"""
LOJINEXT Intelligence Service (AIService)
LLM chat orchestration grounded in fleet context.

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: `groq` client constructor'da bağlanıyor; container
lazy-property singleton'ı olarak yaşar (her istekte GroqService yeniden
kurulmaz).

2026-07-18 ölü-kod temizliği: `predict_trip_fuel`/`detect_anomalies`/
`_get_predictor_for_vehicle`/`invalidate_predictor_cache` ve
`_predictor_cache` SİLİNDİ — grep ile doğrulandı, hiçbir prod endpoint/
servis çağırmıyordu (EnsembleFuelPredictor'ın Phase 4-5
SeferFuelEstimator tarafından supersede edilmiş ikinci bir kopyasıydı;
gerçek tahmin yolu `v2/modules/trip/application/sefer_fuel_estimator.py`).
"""

from typing import Any, Dict, List

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """AI Service for LLM chat (fleet-context grounded)."""

    # Patterns to redact from user prompts (prompt-injection guards)
    _REDACT_PATTERNS = [
        r"SYSTEM\s*:",
        r"ADMIN[\s_]+MODE",
        r"###",
    ]

    def __init__(self):
        from v2.modules.ai_assistant.infrastructure.llm.groq_client import GroqService

        self.groq = GroqService()

    # ── Prompt safety ────────────────────────────────────────────────────────
    def _sanitize_prompt(self, prompt: str, max_length: int = 1000) -> str:
        """Redact dangerous injection tokens and truncate to max_length."""
        import re

        sanitized = prompt
        for pattern in self._REDACT_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                sanitized = re.sub(
                    pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE
                )
        return sanitized[:max_length]

    # ── Context builder ──────────────────────────────────────────────────────
    async def _build_context(self) -> str:
        """Build a fleet-context string for LLM grounding."""
        try:
            from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

            async with UnitOfWork() as uow:
                stats = await uow.analiz_repo.get_dashboard_stats()
                alerts = await uow.analiz_repo.get_recent_unread_alerts()
                vehicles = await uow.arac_repo.get_all(limit=5)

            parts: List[str] = []
            if stats:
                parts.append(
                    f"Filo Ozeti: {stats.get('toplam_arac', 0)} Arac, "
                    f"{stats.get('toplam_sofor', 0)} Sofor, "
                    f"Ort Tuketim: {stats.get('filo_ortalama', 0):.1f} L/100km"
                )
            for alert in (alerts or [])[:3]:
                parts.append(
                    f"Uyari: {alert.get('title', '')} - {alert.get('message', '')}"
                )
            for v in (vehicles or [])[:3]:
                parts.append(
                    f"Arac: {v.get('plaka', '')} ({v.get('motor_verimliligi', ''):.2f} verim)"
                )

            return "\n".join(parts) if parts else "Filo verisi mevcut degil."
        except Exception as exc:
            logger.warning(f"Context build failed: {exc}")
            return "Sistem verileri su an alinamiyor"

    # ── LLM response ─────────────────────────────────────────────────────────
    async def generate_response(self, user_input: str) -> str:
        """Generate a single LLM response grounded in fleet context."""
        try:
            context = await self._build_context()
            safe_prompt = self._sanitize_prompt(user_input)
            return await self.groq.chat(
                f"Filo Bağlamı:\n{context}\n\nKullanıcı: {safe_prompt}"
            )
        except Exception as exc:
            logger.error(f"generate_response failed: {exc}")
            return "Uzgunum, su an cevap veremiyorum."

    def get_progress(self) -> Dict[str, Any]:
        """RAG engine'in yüklenme durumu — /ai/progress endpoint'i kullanır.

        `status`: 'ready' | 'loading' | 'error' | 'offline' (rag_engine.status)
        `pending_jobs`: Şu an arka planda devam eden RAG/embedding işi sayısı
        (rag_engine.async_pending_jobs döndürür, yoksa 0).
        """
        try:
            from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
                get_rag_engine,
            )

            rag = get_rag_engine()
            return {
                "status": getattr(rag, "status", "offline"),
                "pending_jobs": int(getattr(rag, "async_pending_jobs", 0) or 0),
            }
        except Exception as exc:
            logger.warning(f"AI progress probe failed: {exc}")
            return {"status": "error", "pending_jobs": 0}


def get_ai_service() -> AIService:
    from app.core.container import get_container

    return get_container().ai_service
