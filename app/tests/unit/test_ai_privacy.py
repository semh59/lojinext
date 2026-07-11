import os
import threading
from unittest.mock import patch

import pytest

from app.core.ai.rag_engine import RAGEngine


def test_config_robustness():
    """Hatalı ENV VAR durumunda sistemin çökmediğini doğrula"""
    with patch.dict(
        os.environ,
        {"AI_RAG_THRESHOLD": "not_a_float"},
    ):
        rag = RAGEngine()
        # Geçerli bir default eşiğe dönmeli
        assert 0.0 < rag.SIMILARITY_THRESHOLD <= 1.0


@pytest.mark.asyncio
async def test_rag_thread_safe_init():
    """RAG motorunun çoklu thread'de güvenli yüklendiğini doğrula"""
    # FAISS ve ST mockla (ağır yükleme yapmasın)
    with (
        patch("app.core.ai.rag_engine.SentenceTransformer"),
        patch("app.core.ai.rag_engine.FAISSVectorStore"),
    ):
        from app.core.ai.rag_engine import get_rag_engine

        # Birden fazla thread ile aynı anda motoru istemeye çalış
        results = []

        def get_engine():
            results.append(get_rag_engine())

        threads = [threading.Thread(target=get_engine) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Hepsinin aynı instance olduğunu doğrula (Singleton)
        assert all(r == results[0] for r in results)
