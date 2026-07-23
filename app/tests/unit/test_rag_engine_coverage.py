"""
Coverage tests for app/core/ai/rag_engine.py
Targets: FAISSVectorStore, RAGEngine methods, SearchResult, singleton helpers.
"""

from __future__ import annotations

import threading
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding(dim: int = 384) -> np.ndarray:
    arr = np.random.rand(dim).astype(np.float32)
    arr /= np.linalg.norm(arr)
    return arr


def _make_faiss_store(dim: int = 8):
    """Build a minimal FAISSVectorStore with a tiny mock FAISS index."""
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import FAISSVectorStore

    store = FAISSVectorStore.__new__(FAISSVectorStore)
    store.embedding_dim = dim
    store.documents = {}
    store.metadatas = {}
    store.doc_id_to_idx = {}
    store.idx_to_doc_id = {}
    store.next_idx = 0
    store._lock = threading.Lock()

    # Build a tiny real FAISS index when available, otherwise None
    try:
        import faiss as _faiss

        store.index = _faiss.IndexFlatIP(dim)
    except ImportError:
        store.index = None

    return store


def _make_rag_engine(initialized: bool = True):
    """Build a RAGEngine with mocked embedder and vector_store."""
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

    engine = RAGEngine.__new__(RAGEngine)
    engine.is_initialized = initialized
    engine.status = "ready" if initialized else "offline"
    engine._init_lock = threading.Lock()
    engine._last_inference_time_ms = 0.0
    engine.EMBEDDING_MODEL = "test-model"
    engine.EMBEDDING_DIM = 8
    engine.RAG_MAX_CHARS = 4000
    engine.SIMILARITY_THRESHOLD = 0.35
    engine.MAX_DOCUMENT_CHARS = 10000

    if initialized:
        engine.embedder = MagicMock()
        engine.vector_store = _make_faiss_store(dim=8)
    else:
        engine.embedder = None
        engine.vector_store = None

    return engine


# ---------------------------------------------------------------------------
# SearchResult dataclass
# ---------------------------------------------------------------------------


def test_search_result_fields():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    sr = SearchResult(
        document="doc",
        metadata={"source_type": "vehicle"},
        score=0.85,
        source_type="vehicle",
    )
    assert sr.document == "doc"
    assert sr.score == 0.85
    assert sr.source_type == "vehicle"


# ---------------------------------------------------------------------------
# FAISSVectorStore — count / clear
# ---------------------------------------------------------------------------


def test_faiss_store_count_no_index():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import FAISSVectorStore

    store = FAISSVectorStore.__new__(FAISSVectorStore)
    store.index = None
    store._lock = threading.Lock()
    assert store.count() == 0


def test_faiss_store_clear_resets_state():
    store = _make_faiss_store()
    store.documents[0] = "hello"
    store.metadatas[0] = {"k": "v"}
    store.doc_id_to_idx["x"] = 0
    store.idx_to_doc_id[0] = "x"
    store.next_idx = 1
    store.clear()
    assert store.next_idx == 0
    assert len(store.documents) == 0
    assert len(store.metadatas) == 0


# ---------------------------------------------------------------------------
# FAISSVectorStore — add validation gates
# ---------------------------------------------------------------------------


def test_faiss_store_add_rejects_no_index():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import FAISSVectorStore

    store = FAISSVectorStore.__new__(FAISSVectorStore)
    store.index = None
    store._lock = threading.Lock()
    store.documents = {}
    store.metadatas = {}
    store.doc_id_to_idx = {}
    store.idx_to_doc_id = {}
    store.next_idx = 0
    # Must not raise
    store.add("id1", "hello world", _make_embedding(8), {})
    assert len(store.documents) == 0


def test_faiss_store_add_rejects_short_document():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")
    store.add("id1", "hi", _make_embedding(8), {})
    assert len(store.documents) == 0


def test_faiss_store_add_truncates_long_document():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")
    long_doc = "a" * 15000
    store.add("id1", long_doc, _make_embedding(8), {"source_type": "vehicle"})
    if store.documents:
        assert len(store.documents[0]) <= 10000


def test_faiss_store_add_upsert_marks_old_deleted():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")

    emb = _make_embedding(8)
    store.add("doc1", "hello world document", emb, {"source_type": "vehicle"})
    old_idx = store.doc_id_to_idx.get("doc1")
    store.add("doc1", "updated hello world doc", emb, {"source_type": "vehicle"})
    if old_idx is not None:
        assert store.metadatas[old_idx].get("_deleted") is True


def test_faiss_store_add_with_user_id_enriches_metadata():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")
    store.add(
        "id_user",
        "some valid document text",
        _make_embedding(8),
        {"source_type": "trip"},
        user_id=42,
    )
    if store.documents:
        idx = store.doc_id_to_idx["id_user"]
        assert store.metadatas[idx]["user_id"] == 42


# ---------------------------------------------------------------------------
# FAISSVectorStore — search filters
# ---------------------------------------------------------------------------


def test_faiss_store_search_empty_index_returns_empty():
    store = _make_faiss_store()
    result = store.search(_make_embedding(8))
    assert result == []


def test_faiss_store_search_filters_deleted():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")
    emb = _make_embedding(8)
    store.add("d1", "valid vehicle document text", emb, {"source_type": "vehicle"})
    # mark deleted manually
    idx = store.doc_id_to_idx["d1"]
    store.metadatas[idx]["_deleted"] = True
    results = store.search(emb, top_k=5)
    assert all(r[0] != idx for r in results)


def test_faiss_store_search_source_type_filter():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")
    emb = _make_embedding(8)
    store.add("v1", "valid vehicle document text", emb, {"source_type": "vehicle"})
    results = store.search(emb, top_k=5, source_types=["driver"])
    assert len(results) == 0


def test_faiss_store_search_user_id_isolation():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")
    emb = _make_embedding(8)
    store.add(
        "u1",
        "user one valid document text",
        emb,
        {"source_type": "vehicle"},
        user_id=1,
    )
    results = store.search(emb, top_k=5, user_id=99)
    assert len(results) == 0


# ---------------------------------------------------------------------------
# RAGEngine — not initialized guards
# ---------------------------------------------------------------------------


async def test_rag_engine_index_vehicle_not_initialized():
    engine = _make_rag_engine(initialized=False)
    result = await engine.index_vehicle({"id": 1, "plaka": "06ABC"})
    assert result is False


async def test_rag_engine_index_driver_not_initialized():
    engine = _make_rag_engine(initialized=False)
    result = await engine.index_driver({"id": 1, "ad_soyad": "Ali Veli"})
    assert result is False


async def test_rag_engine_index_trip_not_initialized():
    engine = _make_rag_engine(initialized=False)
    result = await engine.index_trip({"id": 1, "cikis_yeri": "A", "varis_yeri": "B"})
    assert result is False





async def test_rag_engine_search_not_initialized():
    engine = _make_rag_engine(initialized=False)
    result = await engine.search("yakıt tüketimi")
    assert result == []


# ---------------------------------------------------------------------------
# RAGEngine — index methods happy path (mocked _generate_embedding)
# ---------------------------------------------------------------------------


async def test_rag_engine_index_vehicle_empty_plaka():
    engine = _make_rag_engine(initialized=True)
    result = await engine.index_vehicle({"id": 1, "plaka": ""})
    assert result is False


async def test_rag_engine_index_vehicle_success():
    engine = _make_rag_engine(initialized=True)
    emb = _make_embedding(8)
    with patch.object(engine, "_generate_embedding", new=AsyncMock(return_value=emb)):
        result = await engine.index_vehicle(
            {"id": 1, "plaka": "34ABC", "marka": "Volvo", "model": "FH", "yil": 2020}
        )
    assert result is True


async def test_rag_engine_index_driver_success():
    engine = _make_rag_engine(initialized=True)
    emb = _make_embedding(8)
    with patch.object(engine, "_generate_embedding", new=AsyncMock(return_value=emb)):
        result = await engine.index_driver(
            {"id": 5, "ad_soyad": "Mehmet Yilmaz", "ehliyet_sinifi": "E"},
            stats={"toplam_sefer": 10, "ort_tuketim": 32.0},
        )
    assert result is True


async def test_rag_engine_index_driver_empty_name():
    engine = _make_rag_engine(initialized=True)
    result = await engine.index_driver({"id": 5, "ad_soyad": ""})
    assert result is False


async def test_rag_engine_index_trip_success():
    engine = _make_rag_engine(initialized=True)
    emb = _make_embedding(8)
    with patch.object(engine, "_generate_embedding", new=AsyncMock(return_value=emb)):
        result = await engine.index_trip(
            {
                "id": 100,
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450,
                "ton": 20,
            }
        )
    assert result is True


async def test_rag_engine_index_trip_date_string():
    engine = _make_rag_engine(initialized=True)
    emb = _make_embedding(8)
    with patch.object(engine, "_generate_embedding", new=AsyncMock(return_value=emb)):
        result = await engine.index_trip(
            {
                "id": 101,
                "cikis_yeri": "Bursa",
                "varis_yeri": "Izmir",
                "tarih": "2024-01-15",
                "mesafe_km": 300,
            }
        )
    assert result is True





# ---------------------------------------------------------------------------
# RAGEngine — bulk_index
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# RAGEngine — search
# ---------------------------------------------------------------------------


async def test_rag_engine_search_empty_query():
    engine = _make_rag_engine(initialized=True)
    result = await engine.search("   ")
    assert result == []


async def test_rag_engine_search_top_k_capped_at_20():
    engine = _make_rag_engine(initialized=True)
    emb = _make_embedding(8)
    with patch.object(engine, "_generate_embedding", new=AsyncMock(return_value=emb)):
        with patch.object(
            engine.vector_store, "search", return_value=[]
        ) as mock_search:
            await engine.search("test query", top_k=50)
            args, kwargs = mock_search.call_args
            assert args[1] <= 20


async def test_rag_engine_search_returns_search_results():
    engine = _make_rag_engine(initialized=True)
    emb = _make_embedding(8)
    # Populate store
    engine.vector_store.documents[0] = "sample doc"
    engine.vector_store.metadatas[0] = {"source_type": "vehicle"}

    with patch.object(engine, "_generate_embedding", new=AsyncMock(return_value=emb)):
        with patch.object(engine.vector_store, "search", return_value=[(0, 0.9)]):
            results = await engine.search("araç tüketimi")

    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].score == 0.9


# ---------------------------------------------------------------------------
# RAGEngine — search_for_context
# ---------------------------------------------------------------------------


async def test_rag_engine_search_for_context_no_results():
    engine = _make_rag_engine(initialized=True)
    with patch.object(engine, "search", new=AsyncMock(return_value=[])):
        ctx = await engine.search_for_context("query")
    assert ctx == ""


async def test_rag_engine_search_for_context_filters_low_score():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    engine = _make_rag_engine(initialized=True)
    low_score_result = SearchResult(
        document="doc", metadata={}, score=0.10, source_type="vehicle"
    )
    with patch.object(engine, "search", new=AsyncMock(return_value=[low_score_result])):
        ctx = await engine.search_for_context("query")
    # Only header would be there if nothing passes threshold — or empty string
    assert "doc" not in ctx or ctx == ""


async def test_rag_engine_search_for_context_with_results():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    engine = _make_rag_engine(initialized=True)
    good_result = SearchResult(
        document="Araç Volvo 2020", metadata={}, score=0.85, source_type="vehicle"
    )
    with patch.object(engine, "search", new=AsyncMock(return_value=[good_result])):
        ctx = await engine.search_for_context("araç bilgisi")
    assert "Araç Volvo 2020" in ctx


async def test_rag_engine_search_for_context_respects_max_chars():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    engine = _make_rag_engine(initialized=True)
    big_doc = "A" * 5000
    r1 = SearchResult(document=big_doc, metadata={}, score=0.9, source_type="vehicle")
    r2 = SearchResult(document=big_doc, metadata={}, score=0.8, source_type="vehicle")
    with patch.object(engine, "search", new=AsyncMock(return_value=[r1, r2])):
        ctx = await engine.search_for_context("query", max_chars=200)
    assert len(ctx) < 5000 + 1000


# ---------------------------------------------------------------------------
# RAGEngine — get_stats / clear_index
# ---------------------------------------------------------------------------


def test_rag_engine_get_stats_not_initialized():
    engine = _make_rag_engine(initialized=False)
    stats = engine.get_stats()
    assert stats["initialized"] is False


def test_rag_engine_get_stats_initialized():
    engine = _make_rag_engine(initialized=True)
    stats = engine.get_stats()
    assert stats["initialized"] is True
    assert "total_documents" in stats
    assert stats["embedding_model"] == "test-model"


def test_rag_engine_clear_index_not_initialized():
    engine = _make_rag_engine(initialized=False)
    assert engine.clear_index() is False


def test_rag_engine_clear_index_success():
    engine = _make_rag_engine(initialized=True)
    result = engine.clear_index()
    assert result is True


# ---------------------------------------------------------------------------
# RAGEngine — wait_until_ready
# ---------------------------------------------------------------------------


def test_rag_engine_wait_until_ready_already_ready():
    engine = _make_rag_engine(initialized=True)
    engine.status = "ready"
    assert engine.wait_until_ready(timeout=0.5) is True


def test_rag_engine_wait_until_ready_error_status():
    engine = _make_rag_engine(initialized=True)
    engine.status = "error"
    assert engine.wait_until_ready(timeout=0.5) is False


def test_rag_engine_wait_until_ready_times_out():
    engine = _make_rag_engine(initialized=False)
    engine.status = "loading"
    assert engine.wait_until_ready(timeout=0.05) is False


# ---------------------------------------------------------------------------
# RAGEngine — save_to_disk / load_from_disk delegates
# ---------------------------------------------------------------------------


def test_rag_engine_save_to_disk_not_initialized():
    engine = _make_rag_engine(initialized=False)
    # Should not raise
    engine.save_to_disk("/tmp/test_rag")


def test_rag_engine_save_to_disk_calls_vector_store():
    engine = _make_rag_engine(initialized=True)
    engine.vector_store.save_index = MagicMock()
    engine.save_to_disk("/tmp/test_rag")
    engine.vector_store.save_index.assert_called_once_with("/tmp/test_rag")


# ---------------------------------------------------------------------------
# RAGEngine — _create_document_id
# ---------------------------------------------------------------------------


def test_create_document_id():
    engine = _make_rag_engine(initialized=False)
    assert engine._create_document_id("vehicle", 42) == "vehicle_42"
    assert engine._create_document_id("trip", 0) == "trip_0"


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------


def test_get_rag_engine_returns_same_instance():
    import v2.modules.ai_assistant.infrastructure.rag.rag_engine as mod

    orig = mod._rag_engine
    mod._rag_engine = None
    try:
        with (
            patch(
                "v2.modules.ai_assistant.infrastructure.rag.rag_engine.SENTENCE_TRANSFORMERS_AVAILABLE",
                False,
            ),
            patch(
                "v2.modules.ai_assistant.infrastructure.rag.rag_engine.FAISS_AVAILABLE",
                False,
            ),
        ):
            e1 = mod.get_rag_engine()
            e2 = mod.get_rag_engine()
        assert e1 is e2
    finally:
        mod._rag_engine = orig


def test_is_rag_available():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import is_rag_available

    with (
        patch(
            "v2.modules.ai_assistant.infrastructure.rag.rag_engine.SENTENCE_TRANSFORMERS_AVAILABLE",
            True,
        ),
        patch(
            "v2.modules.ai_assistant.infrastructure.rag.rag_engine.FAISS_AVAILABLE",
            True,
        ),
    ):
        assert is_rag_available() is True

    with (
        patch(
            "v2.modules.ai_assistant.infrastructure.rag.rag_engine.SENTENCE_TRANSFORMERS_AVAILABLE",
            False,
        ),
        patch(
            "v2.modules.ai_assistant.infrastructure.rag.rag_engine.FAISS_AVAILABLE",
            True,
        ),
    ):
        assert is_rag_available() is False
