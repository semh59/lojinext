from unittest.mock import patch

import pytest

from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
    RAGEngine,
    SearchResult,
)


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
