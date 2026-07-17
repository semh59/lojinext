"""
Unit tests for RAGEngine (rag_engine.py) and supporting classes.

Heavy dependencies (sentence_transformers, faiss) are mocked so that tests
pass in CI environments where these packages are not installed.

Pattern:
  - FAISSVectorStore is tested directly when FAISS is not available (index=None path).
  - RAGEngine is tested with is_initialized forced to True and embedder/vector_store
    replaced with mocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vehicle(vid=1, plaka="34ABC123"):
    return {
        "id": vid,
        "plaka": plaka,
        "marka": "MAN",
        "model": "TGX",
        "yil": 2020,
        "hedef_tuketim": 32.0,
        "tank_kapasitesi": 600,
        "aktif": True,
    }


def _make_driver(did=1, ad_soyad="Ahmet Yılmaz"):
    return {
        "id": did,
        "ad_soyad": ad_soyad,
        "ehliyet_sinifi": "CE",
        "score": 1.0,
        "aktif": True,
    }


def _make_trip(tid=1):
    return {
        "id": tid,
        "tarih": "2025-01-15",
        "cikis_yeri": "Ankara",
        "varis_yeri": "İstanbul",
        "mesafe_km": 450,
        "ton": 20,
        "tuketim": 32.5,
        "durum": "Tamamlandı",
    }


def _make_alert(aid=1):
    return {
        "id": aid,
        "title": "Yakıt Anomalisi",
        "message": "Beklenenden %20 fazla tüketim",
        "severity": "high",
        "alert_type": "fuel",
        "created_at": "2025-01-15T10:00:00Z",
    }


def _build_rag_engine_with_mocks():
    """Return a RAGEngine with is_initialized=True and mocked internals."""
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

    engine = RAGEngine.__new__(RAGEngine)
    engine.is_initialized = True
    engine.status = "ready"
    engine.embedder = MagicMock()
    engine.vector_store = MagicMock()
    engine.EMBEDDING_MODEL = "test-model"
    engine.EMBEDDING_DIM = 384
    engine.RAG_MAX_CHARS = 4000
    engine.SIMILARITY_THRESHOLD = 0.35
    engine.MAX_DOCUMENT_CHARS = 10000
    engine._last_inference_time_ms = 0.0
    import threading

    engine._init_lock = threading.Lock()
    return engine


# ---------------------------------------------------------------------------
# FAISSVectorStore (no-FAISS path)
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreNoFaiss:
    def test_instantiates_without_faiss(self):
        """FAISSVectorStore should not crash when faiss is absent."""
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISSVectorStore,
        )

        store = FAISSVectorStore(embedding_dim=384)
        # If FAISS is available, index is set; otherwise it's None
        # Either way, the object is created successfully.
        assert store.embedding_dim == 384

    def test_count_returns_zero_on_empty(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if FAISS_AVAILABLE:
            pytest.skip("Test targets no-FAISS path")

        store = FAISSVectorStore(384)
        assert store.count() == 0

    def test_add_noop_without_faiss(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if FAISS_AVAILABLE:
            pytest.skip("Test targets no-FAISS path")

        store = FAISSVectorStore(384)
        store.add(
            "doc1", "hello world test doc", np.zeros(384), {"source_type": "test"}
        )
        # Should not raise; count stays 0
        assert store.count() == 0

    def test_search_returns_empty_without_faiss(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if FAISS_AVAILABLE:
            pytest.skip("Test targets no-FAISS path")

        store = FAISSVectorStore(384)
        results = store.search(np.zeros(384), top_k=5)
        assert results == []

    def test_clear_noop_without_faiss(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if FAISS_AVAILABLE:
            pytest.skip("Test targets no-FAISS path")

        store = FAISSVectorStore(384)
        store.clear()  # should not raise
        assert store.count() == 0


# ---------------------------------------------------------------------------
# FAISSVectorStore (FAISS-available path)
# ---------------------------------------------------------------------------


class TestFAISSVectorStoreWithFaiss:
    def test_add_and_count(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if not FAISS_AVAILABLE:
            pytest.skip("faiss not installed")

        store = FAISSVectorStore(384)
        embedding = np.random.rand(384).astype(np.float32)
        store.add(
            "doc1",
            "This is a test document for FAISS.",
            embedding,
            {"source_type": "test"},
        )
        assert store.count() == 1

    def test_short_document_rejected(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if not FAISS_AVAILABLE:
            pytest.skip("faiss not installed")

        store = FAISSVectorStore(384)
        before = store.count()
        store.add("short", "Hi", np.random.rand(384).astype(np.float32), {})
        assert store.count() == before  # rejected

    def test_upsert_marks_old_as_deleted(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            FAISS_AVAILABLE,
            FAISSVectorStore,
        )

        if not FAISS_AVAILABLE:
            pytest.skip("faiss not installed")

        store = FAISSVectorStore(384)
        emb = np.random.rand(384).astype(np.float32)
        store.add(
            "doc1", "first version of the document text", emb, {"source_type": "v"}
        )
        store.add(
            "doc1", "second version of the document text", emb, {"source_type": "v"}
        )

        # First entry should be marked deleted
        old_idx = list(store.documents.keys())[0]
        assert store.metadatas[old_idx].get("_deleted") is True

    def test_create_document_id(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        engine = RAGEngine.__new__(RAGEngine)
        doc_id = engine._create_document_id("vehicle", 42)
        assert doc_id == "vehicle_42"


# ---------------------------------------------------------------------------
# RAGEngine — not initialized path
# ---------------------------------------------------------------------------


class TestRAGEngineNotInitialized:
    def test_stats_when_not_initialized(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        engine = RAGEngine.__new__(RAGEngine)
        engine.is_initialized = False
        engine.vector_store = None
        result = engine.get_stats()
        assert result["initialized"] is False

    async def test_search_returns_empty_when_not_initialized(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        engine = RAGEngine.__new__(RAGEngine)
        engine.is_initialized = False
        results = await engine.search("fuel consumption")
        assert results == []

    async def test_index_vehicle_returns_false_when_not_initialized(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        engine = RAGEngine.__new__(RAGEngine)
        engine.is_initialized = False
        result = await engine.index_vehicle(_make_vehicle())
        assert result is False

    def test_clear_index_returns_false_when_not_initialized(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        engine = RAGEngine.__new__(RAGEngine)
        engine.is_initialized = False
        assert engine.clear_index() is False


# ---------------------------------------------------------------------------
# RAGEngine — initialized path (mocked embedder + vector_store)
# ---------------------------------------------------------------------------


class TestRAGEngineIndexing:
    async def test_index_vehicle_success(self):
        engine = _build_rag_engine_with_mocks()
        engine.embedder.encode = MagicMock(return_value=np.zeros(384, dtype=np.float32))

        with patch.object(
            engine, "_generate_embedding", new_callable=AsyncMock
        ) as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            result = await engine.index_vehicle(_make_vehicle())

        assert result is True
        engine.vector_store.add.assert_called_once()

    async def test_index_vehicle_empty_plaka_returns_false(self):
        engine = _build_rag_engine_with_mocks()
        bad_vehicle = {"id": 1, "plaka": "", "marka": "MAN"}
        result = await engine.index_vehicle(bad_vehicle)
        assert result is False

    async def test_index_driver_success(self):
        engine = _build_rag_engine_with_mocks()
        with patch.object(
            engine, "_generate_embedding", new_callable=AsyncMock
        ) as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            result = await engine.index_driver(_make_driver())

        assert result is True

    async def test_index_driver_empty_name_returns_false(self):
        engine = _build_rag_engine_with_mocks()
        bad_driver = {"id": 1, "ad_soyad": ""}
        result = await engine.index_driver(bad_driver)
        assert result is False

    async def test_index_trip_success(self):
        engine = _build_rag_engine_with_mocks()
        with patch.object(
            engine, "_generate_embedding", new_callable=AsyncMock
        ) as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            result = await engine.index_trip(_make_trip())

        assert result is True

    async def test_index_alert_success(self):
        engine = _build_rag_engine_with_mocks()
        with patch.object(
            engine, "_generate_embedding", new_callable=AsyncMock
        ) as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            result = await engine.index_alert(_make_alert())

        assert result is True


class TestRAGEngineSearch:
    async def test_search_returns_empty_on_empty_query(self):
        engine = _build_rag_engine_with_mocks()
        results = await engine.search("")
        assert results == []

    async def test_search_calls_vector_store(self):
        engine = _build_rag_engine_with_mocks()
        engine.vector_store.search = MagicMock(return_value=[])

        with patch.object(
            engine, "_generate_embedding", new_callable=AsyncMock
        ) as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            results = await engine.search("yakıt tüketimi")

        assert isinstance(results, list)

    async def test_search_top_k_capped_at_20(self):
        """top_k > 20 should be silently capped."""
        engine = _build_rag_engine_with_mocks()
        engine.vector_store.search = MagicMock(return_value=[])

        with patch.object(
            engine, "_generate_embedding", new_callable=AsyncMock
        ) as mock_emb:
            mock_emb.return_value = np.zeros(384, dtype=np.float32)
            await engine.search("test", top_k=100)

        # vector_store.search called with top_k ≤ 20
        called_top_k = engine.vector_store.search.call_args[0][1]
        assert called_top_k <= 20

    def test_get_stats_returns_initialized_true(self):
        engine = _build_rag_engine_with_mocks()
        engine.vector_store.count = MagicMock(return_value=42)
        stats = engine.get_stats()
        assert stats["initialized"] is True
        assert stats["total_documents"] == 42

    def test_clear_index_delegates_to_vector_store(self):
        engine = _build_rag_engine_with_mocks()
        result = engine.clear_index()
        engine.vector_store.clear.assert_called_once()
        assert result is True


class TestRAGEngineBulkIndex:
    async def test_bulk_index_counts_successes(self):
        engine = _build_rag_engine_with_mocks()
        with (
            patch.object(
                engine, "index_vehicle", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                engine, "index_driver", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                engine, "index_trip", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                engine, "index_alert", new_callable=AsyncMock, return_value=False
            ),
        ):
            result = await engine.bulk_index(
                vehicles=[_make_vehicle()],
                drivers=[_make_driver()],
                trips=[_make_trip()],
                alerts=[_make_alert()],
            )

        assert result["vehicles"] == 1
        assert result["drivers"] == 1
        assert result["trips"] == 1
        assert result["alerts"] == 0
        assert result["errors"] == 1
        assert result["total"] == 3


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestRAGEngineSingleton:
    def test_is_rag_available_returns_bool(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
            is_rag_available,
        )

        result = is_rag_available()
        assert isinstance(result, bool)

    def test_search_result_dataclass(self):
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

        sr = SearchResult(
            document="test doc",
            metadata={"source_type": "vehicle"},
            score=0.85,
            source_type="vehicle",
        )
        assert sr.score == 0.85
        assert sr.source_type == "vehicle"
