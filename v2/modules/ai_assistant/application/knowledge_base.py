"""
LojiNext AI RAG service.

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: RAG + LLM servisi — FAISS vektör indeksi ve embedding modeli yüklenir.
CREATED_BY: app/core/container.py (lazy property)
"""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
else:
    try:
        from sentence_transformers import SentenceTransformer

        EMBEDDING_AVAILABLE = True
    except ImportError:
        SentenceTransformer = None
        EMBEDDING_AVAILABLE = False

from app.infrastructure.logging.logger import get_logger
from v2.modules.ai_assistant.infrastructure.rag.vector_store import FAISSVectorStore

logger = get_logger(__name__)

KB_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "ai_kb"
KB_DIR.mkdir(parents=True, exist_ok=True)


class KnowledgeBase:
    """Persistent FAISS-backed knowledge base."""

    # Persist at most every 60s or every 20 adds (whichever comes first).
    _SAVE_INTERVAL_S = 60.0
    _SAVE_BATCH = 20

    def __init__(self, embedding_dim: int = 384):
        self.vector_store = FAISSVectorStore(embedding_dim)
        self.model: Optional[Any] = None
        self._last_saved: float = 0.0
        self._adds_since_save: int = 0

        if self.vector_store.load_index(str(KB_DIR)):
            logger.info("Existing knowledge base loaded from disk.")

        self._load_embedding_model()

    def _load_embedding_model(self):
        if not EMBEDDING_AVAILABLE:
            return
        try:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except Exception as exc:
            logger.error(f"Embedding model could not be loaded: {exc}")

    def _generate_doc_id(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()[:12]

    async def add_document(
        self, content: str, category: str, metadata: Optional[Dict] = None
    ) -> bool:
        if not self.model:
            return False

        doc_id = self._generate_doc_id(content)
        embedding = await asyncio.to_thread(
            self.model.encode,
            content,
            convert_to_numpy=True,
        )

        payload = metadata.copy() if metadata else {}
        payload.update(
            {
                "category": category,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        self.vector_store.add(doc_id, content, embedding, payload)
        self._adds_since_save += 1

        now = time.monotonic()
        should_save = (
            self._adds_since_save >= self._SAVE_BATCH
            or (now - self._last_saved) >= self._SAVE_INTERVAL_S
        )
        if should_save:
            await asyncio.to_thread(self.vector_store.save_index, str(KB_DIR))
            self._last_saved = now
            self._adds_since_save = 0

        return True

    async def search(
        self, query: str, top_k: int = 5, category: Optional[str] = None
    ) -> List[Dict]:
        if not self.model:
            logger.warning(
                "KB search invoked but embedding model is not loaded; "
                "returning empty results (degraded state)."
            )
            return []
        if self.vector_store.count() == 0:
            return []

        query_embedding = await asyncio.to_thread(
            self.model.encode,
            query,
            convert_to_numpy=True,
        )
        source_types = [category] if category else None
        raw_results = await asyncio.to_thread(
            self.vector_store.search,
            query_embedding,
            top_k,
            source_types,
        )

        results = []
        for idx, score in raw_results:
            if score <= 0.3:
                continue
            results.append(
                {
                    "id": self.vector_store.idx_to_doc_id.get(idx),
                    "content": self.vector_store.documents.get(idx),
                    "category": self.vector_store.metadatas.get(idx, {}).get(
                        "category"
                    ),
                    "metadata": self.vector_store.metadatas.get(idx),
                    "score": float(score),
                }
            )
        return results

    def get_stats(self) -> Dict:
        return {
            "total_documents": self.vector_store.count(),
            "storage_path": str(KB_DIR),
            "initialized": self.model is not None,
        }


class SmartAIService:
    """Knowledge-base plus LLM orchestration service."""

    def __init__(self):
        self.kb = KnowledgeBase()
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            try:
                from v2.modules.ai_assistant.infrastructure.llm.raw_client import (
                    get_llm_client,
                )

                self._llm = get_llm_client()
            except Exception as exc:
                logger.error(f"LLM client could not be loaded: {exc}")
        return self._llm

    async def learn_from_trip(self, trip_data: Dict) -> bool:
        tuketim = float(trip_data.get("tuketim") or 0)
        content = (
            f"Sefer Bilgisi: {trip_data.get('cikis_yeri', '')} -> "
            f"{trip_data.get('varis_yeri', '')}. "
            f"Mesafe: {trip_data.get('mesafe_km', 0)} km. "
            f"Yuk: {trip_data.get('ton', 0)} ton. "
            f"Tuketim: {tuketim:.1f} L/100km. "
        )

        if tuketim < 28:
            content += "Degerlendirme: Cok verimli sefer."
        elif tuketim > 38:
            content += "Degerlendirme: Yuksek tuketim, incelenmeli."
        else:
            content += "Degerlendirme: Normal sefer."

        return await self.kb.add_document(content, category="sefer", metadata=trip_data)

    async def learn_from_fuel(self, fuel_data: Dict) -> bool:
        content = (
            f"Yakit Alimi: {float(fuel_data.get('litre', 0) or 0):.1f} litre, "
            f"Fiyat: {float(fuel_data.get('fiyat_tl', 0) or 0):.2f} TL/L, "
            f"Istasyon: {fuel_data.get('istasyon', 'Bilinmiyor')}. "
            f"KM Sayac: {fuel_data.get('km_sayac', 0)}."
        )
        return await self.kb.add_document(content, category="yakit", metadata=fuel_data)

    async def learn_from_log(self, log_entry: Dict) -> bool:
        timestamp = log_entry.get("timestamp", datetime.now(timezone.utc).isoformat())
        level = log_entry.get("level", "INFO")
        message = log_entry.get("message", "")
        module = log_entry.get("module", "unknown")
        content = (
            f"Sistem Logu [{level}]: {message} (Zaman: {timestamp}, Modul: {module})"
        )
        return await self.kb.add_document(
            content,
            category="log",
            metadata={"level": level, "module": module},
        )

    async def learn_from_event(self, event_type: str, details: Dict) -> bool:
        content = (
            f"Sistem Olayi [{event_type}]: {json.dumps(details, ensure_ascii=False)}"
        )
        return await self.kb.add_document(
            content,
            category="event",
            metadata={"event_type": event_type},
        )

    async def teach(self, knowledge: str, category: str = "genel") -> bool:
        return await self.kb.add_document(knowledge, category=category)

    def get_stats(self) -> Dict:
        kb_stats = self.kb.get_stats()
        llm_status = "available" if self._get_llm() else "unavailable"
        return {
            "knowledge_base": kb_stats,
            "llm_status": llm_status,
            "embedding_model": "all-MiniLM-L6-v2" if self.kb.model else "unavailable",
        }


def get_smart_ai() -> SmartAIService:
    from app.core.container import get_container

    return get_container().smart_ai_service
