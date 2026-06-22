import asyncio
from unittest.mock import patch

import pytest

from app.core.ai.chatbot import Chatbot
from app.core.ai.prompt_tuner import PromptTuner
from app.core.ai.rag_engine import RAGEngine, SearchResult


@pytest.mark.asyncio
async def test_chatbot_input_length_limit():
    """Cok uzun mesajlarin reddedildigini dogrula"""
    chatbot = Chatbot()
    chatbot.MAX_INPUT_CHARS = 10

    response = await chatbot.chat("Bu mesaj 10 karakterden uzun")
    assert "uzun" in response.lower()


@pytest.mark.asyncio
async def test_prompt_tuner_xml_tagging():
    """Kullanici sorgusunun XML tagleri ile sarmlandigini dogrula"""
    tuner = PromptTuner()
    query = "Yakit tuketimi nedir?"

    prompt = tuner.build_tuned_prompt(query)
    assert "<user_input>" in prompt
    assert "</user_input>" in prompt
    assert query in prompt


@pytest.mark.asyncio
async def test_rag_similarity_threshold():
    """Dusuk skorlu RAG sonuclarinin filtrelendigini dogrula"""
    rag = RAGEngine()
    rag.is_initialized = True
    rag.SIMILARITY_THRESHOLD = 0.5

    mock_results = [
        SearchResult(document="Iyi sonuc", metadata={}, score=0.8, source_type="trip"),
        SearchResult(document="Kotu sonuc", metadata={}, score=0.2, source_type="trip"),
    ]

    with patch.object(rag, "search", return_value=mock_results):
        context = await rag.search_for_context("test")
        assert "Iyi sonuc" in context
        assert "Kotu sonuc" not in context


@pytest.mark.asyncio
async def test_chatbot_timeout():
    """Uretim suresi asilarsa timeout mesaji donmeli"""
    from unittest.mock import AsyncMock

    chatbot = Chatbot()

    with patch.object(
        chatbot._client, "chat", new=AsyncMock(side_effect=asyncio.TimeoutError)
    ):
        response = await chatbot._generate_response("soru", "context", [], 100, 0.7)
        assert "cok uzun" in response.lower()
