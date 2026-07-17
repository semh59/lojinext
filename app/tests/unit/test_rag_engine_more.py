"""
Additional coverage tests for app/core/ai/rag_engine.py

Targets uncovered branches not covered by test_rag_engine_coverage.py:
- FAISSVectorStore.save_index (no FAISS)
- FAISSVectorStore.load_index (dimension mismatch, missing files, error paths)
- FAISSVectorStore.search (no index)
- RAGEngine._generate_embedding (embedder None raises)
- RAGEngine.index_vehicle/driver error path (exception in vector_store.add)
- RAGEngine.bulk_index with None lists
- RAGEngine.search error path
- RAGEngine.search_for_context truncation "[... Diğer]"
- RAGEngine.clear_index exception path
- FAISSVectorStore index size limit
"""

from __future__ import annotations

import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers (same as test_rag_engine_coverage.py)
# ---------------------------------------------------------------------------


def _make_embedding(dim: int = 8) -> np.ndarray:
    arr = np.random.rand(dim).astype(np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr /= norm
    return arr


def _make_faiss_store(dim: int = 8):
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import FAISSVectorStore

    store = FAISSVectorStore.__new__(FAISSVectorStore)
    store.embedding_dim = dim
    store.documents = {}
    store.metadatas = {}
    store.doc_id_to_idx = {}
    store.idx_to_doc_id = {}
    store.next_idx = 0
    store._lock = threading.Lock()

    try:
        import faiss as _faiss

        store.index = _faiss.IndexFlatIP(dim)
    except ImportError:
        store.index = None

    return store


def _make_rag_engine(initialized: bool = True):
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
# FAISSVectorStore.save_index — no FAISS
# ---------------------------------------------------------------------------


def test_faiss_store_save_index_no_faiss():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import FAISSVectorStore

    store = FAISSVectorStore.__new__(FAISSVectorStore)
    store.index = None
    store._lock = threading.Lock()
    store.embedding_dim = 8
    # Should return silently without error
    store.save_index("/tmp/test_rag_no_faiss")


# ---------------------------------------------------------------------------
# FAISSVectorStore.load_index — missing files
# ---------------------------------------------------------------------------


def test_faiss_store_load_index_missing_files():
    store = _make_faiss_store()
    result = store.load_index("/tmp/definitely_does_not_exist_xyz")
    assert result is False


def test_faiss_store_load_index_no_faiss():
    store = _make_faiss_store()
    with patch(
        "v2.modules.ai_assistant.infrastructure.rag.rag_engine.FAISS_AVAILABLE", False
    ):
        result = store.load_index("/tmp/test_rag")
    assert result is False


def test_faiss_store_load_index_dimension_mismatch(tmp_path):
    """Loading index with mismatched embedding_dim should return False and reset."""
    try:
        import faiss
    except ImportError:
        pytest.skip("faiss not available")

    store = _make_faiss_store(dim=8)
    # Write a metadata.json with a different dimension
    index_file = tmp_path / "faiss.index"
    meta_file = tmp_path / "metadata.json"

    # Write a tiny valid faiss index
    idx = faiss.IndexFlatIP(16)
    faiss.write_index(idx, str(index_file))

    meta = {
        "documents": {},
        "metadatas": {},
        "doc_id_to_idx": {},
        "idx_to_doc_id": {},
        "next_idx": 0,
        "embedding_dim": 16,  # mismatch with store.embedding_dim=8
    }
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    result = store.load_index(str(tmp_path))
    assert result is False


def test_faiss_store_load_index_success(tmp_path):
    """Load index successfully when files match."""
    try:
        import faiss
    except ImportError:
        pytest.skip("faiss not available")

    store = _make_faiss_store(dim=8)
    index_file = tmp_path / "faiss.index"
    meta_file = tmp_path / "metadata.json"

    idx = faiss.IndexFlatIP(8)
    faiss.write_index(idx, str(index_file))

    meta = {
        "documents": {"0": "hello world doc"},
        "metadatas": {"0": {"source_type": "vehicle"}},
        "doc_id_to_idx": {"vehicle_1": 0},
        "idx_to_doc_id": {"0": "vehicle_1"},
        "next_idx": 1,
        "embedding_dim": 8,
    }
    meta_file.write_text(json.dumps(meta), encoding="utf-8")

    result = store.load_index(str(tmp_path))
    assert result is True
    assert store.documents[0] == "hello world doc"
    assert store.next_idx == 1


# ---------------------------------------------------------------------------
# FAISSVectorStore — index size limit
# ---------------------------------------------------------------------------


def test_faiss_store_add_rejects_when_full():
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")

    # Override MAX_INDEX_SIZE to 0 to trigger the limit immediately
    store.MAX_INDEX_SIZE = 0
    store.add("id1", "hello valid doc", _make_embedding(8), {})
    assert len(store.documents) == 0


# ---------------------------------------------------------------------------
# FAISSVectorStore — search with no index (ntotal=0 guard)
# ---------------------------------------------------------------------------


def test_faiss_store_search_no_index():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import FAISSVectorStore

    store = FAISSVectorStore.__new__(FAISSVectorStore)
    store.index = None
    store._lock = threading.Lock()
    store.documents = {}
    store.metadatas = {}
    result = store.search(_make_embedding(8))
    assert result == []


# ---------------------------------------------------------------------------
# RAGEngine._generate_embedding — embedder None
# ---------------------------------------------------------------------------


async def test_rag_engine_generate_embedding_no_embedder():
    engine = _make_rag_engine(initialized=True)
    engine.embedder = None

    with pytest.raises(RuntimeError, match="not loaded"):
        await engine._generate_embedding("test text")


# ---------------------------------------------------------------------------
# RAGEngine.index_vehicle — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_index_vehicle_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine,
        "_generate_embedding",
        new=AsyncMock(side_effect=RuntimeError("embed fail")),
    ):
        result = await engine.index_vehicle({"id": 1, "plaka": "34ABC"})
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.index_driver — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_index_driver_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine, "_generate_embedding", new=AsyncMock(side_effect=RuntimeError("fail"))
    ):
        result = await engine.index_driver({"id": 1, "ad_soyad": "Ahmet Veli"})
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.index_trip — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_index_trip_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine, "_generate_embedding", new=AsyncMock(side_effect=RuntimeError("fail"))
    ):
        result = await engine.index_trip(
            {"id": 10, "cikis_yeri": "A", "varis_yeri": "B"}
        )
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.index_alert — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_index_alert_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine, "_generate_embedding", new=AsyncMock(side_effect=RuntimeError("fail"))
    ):
        result = await engine.index_alert({"id": 5, "title": "Test"})
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.index_log — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_index_log_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine, "_generate_embedding", new=AsyncMock(side_effect=RuntimeError("fail"))
    ):
        result = await engine.index_log({"message": "test log"})
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.index_event — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_index_event_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine, "_generate_embedding", new=AsyncMock(side_effect=RuntimeError("fail"))
    ):
        result = await engine.index_event("MY_EVENT", {"key": "val"})
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.bulk_index — None lists pass silently
# ---------------------------------------------------------------------------


async def test_rag_engine_bulk_index_none_lists():
    engine = _make_rag_engine(initialized=True)
    result = await engine.bulk_index(
        vehicles=None, drivers=None, trips=None, alerts=None
    )
    assert result["total"] == 0
    assert result["errors"] == 0


# ---------------------------------------------------------------------------
# RAGEngine.search — exception path
# ---------------------------------------------------------------------------


async def test_rag_engine_search_exception():
    engine = _make_rag_engine(initialized=True)

    with patch.object(
        engine,
        "_generate_embedding",
        new=AsyncMock(side_effect=RuntimeError("embed fail")),
    ):
        result = await engine.search("some query")
    assert result == []


# ---------------------------------------------------------------------------
# RAGEngine.search_for_context — truncation with "[... Diğer]"
# ---------------------------------------------------------------------------


async def test_rag_engine_search_for_context_truncation_message():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    engine = _make_rag_engine(initialized=True)
    # Two large documents — second should be truncated due to max_chars
    doc1 = "A" * 300
    doc2 = "B" * 300
    r1 = SearchResult(document=doc1, metadata={}, score=0.9, source_type="vehicle")
    r2 = SearchResult(document=doc2, metadata={}, score=0.85, source_type="driver")

    with patch.object(engine, "search", new=AsyncMock(return_value=[r1, r2])):
        ctx = await engine.search_for_context("query", max_chars=400)

    # When second doc exceeds max_chars, truncation message should appear
    assert "Diğer" in ctx or "dahil edilmedi" in ctx or doc2 not in ctx


# ---------------------------------------------------------------------------
# RAGEngine.search_for_context — source_type label mapping coverage
# ---------------------------------------------------------------------------


async def test_rag_engine_search_for_context_source_labels():
    from v2.modules.ai_assistant.infrastructure.rag.rag_engine import SearchResult

    engine = _make_rag_engine(initialized=True)

    source_types = [
        "vehicle",
        "driver",
        "trip",
        "alert",
        "log",
        "event",
        "unknown_type",
    ]
    results = [
        SearchResult(
            document=f"document for {st}",
            metadata={"source_type": st},
            score=0.9,
            source_type=st,
        )
        for st in source_types
    ]

    with patch.object(engine, "search", new=AsyncMock(return_value=results)):
        ctx = await engine.search_for_context("test query", max_chars=50000)

    # Context should contain content for at least the vehicle result
    assert "document for vehicle" in ctx


# ---------------------------------------------------------------------------
# RAGEngine.clear_index — exception path
# ---------------------------------------------------------------------------


def test_rag_engine_clear_index_exception():
    engine = _make_rag_engine(initialized=True)
    engine.vector_store.clear = MagicMock(side_effect=RuntimeError("clear failed"))
    result = engine.clear_index()
    assert result is False


# ---------------------------------------------------------------------------
# RAGEngine.load_from_disk — not initialized guard
# ---------------------------------------------------------------------------


def test_rag_engine_load_from_disk_not_initialized():
    engine = _make_rag_engine(initialized=False)
    # Should not raise
    engine.load_from_disk("/tmp/test_path")


# ---------------------------------------------------------------------------
# FAISSVectorStore — user_id None with metadata user_id (multi-tenancy guard)
# ---------------------------------------------------------------------------


def test_faiss_store_search_user_id_none_no_filter():
    """When search user_id=None, skip multi-tenancy filter (any doc is returned)."""
    store = _make_faiss_store()
    if store.index is None:
        pytest.skip("faiss not available")

    emb = _make_embedding(8)
    store.add(
        "d1",
        "valid document for search test",
        emb,
        {"source_type": "vehicle", "user_id": 42},
    )
    results = store.search(emb, top_k=5, user_id=None)
    # user_id=None → no filter → doc should appear
    assert len(results) >= 1
