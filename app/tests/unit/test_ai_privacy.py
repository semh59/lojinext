import os
import threading
from unittest.mock import patch

import pytest

from app.core.ai.chatbot import ChatMessage, get_chatbot
from app.core.ai.rag_engine import RAGEngine


@pytest.mark.asyncio
async def test_chatbot_history_privacy():
    """A ve B kullanıcılarının history'lerinin birbirine sızmadığını doğrula"""
    chatbot = get_chatbot()

    # User A history
    history_a = [ChatMessage(role="user", content="Benim adım Ahmet")]
    # User B history
    history_b = [ChatMessage(role="user", content="Benim adım Mehmet")]

    # Mock generation and model_loaded
    async def mock_gen(msg, ctx, hist, *args, **kwargs):
        # History içinden ismi bulmaya çalış
        names = [m.content for m in hist if "adım" in m.content]
        return f"Merhaba {names[0] if names else 'yabancı'}"

    with patch.object(chatbot, "_generate_response", side_effect=mock_gen):
        # A kullanıcısı için yanıt al
        resp_a = await chatbot.chat("Selam", history=history_a)
        assert "Ahmet" in resp_a

        # B kullanıcısı için yanıt al
        resp_b = await chatbot.chat("Selam", history=history_b)
        assert "Mehmet" in resp_b
        assert "Ahmet" not in resp_b  # Sızıntı yok!


def test_config_robustness():
    """Hatalı ENV VAR durumunda sistemin çökmediğini doğrula"""
    with patch.dict(
        os.environ,
        {"AI_MAX_HISTORY": "invalid_number", "AI_RAG_THRESHOLD": "not_a_float"},
    ):
        chatbot = get_chatbot()
        # Default değer olan 10'a dönmeli
        assert chatbot.MAX_HISTORY == 10

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
