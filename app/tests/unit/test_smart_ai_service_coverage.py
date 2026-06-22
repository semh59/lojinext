"""
Coverage tests for app/services/smart_ai_service.py
Targets: KnowledgeBase (add_document, search branches), SmartAIService
(learn_from_trip consumption branches, learn_from_fuel, learn_from_log,
learn_from_event, teach, ask with/without context, get_stats).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# KnowledgeBase helpers
# ---------------------------------------------------------------------------


def _make_kb(has_model: bool = True):
    """Return a KnowledgeBase with a stubbed FAISSVectorStore."""
    import app.services.smart_ai_service as mod

    kb = mod.KnowledgeBase.__new__(mod.KnowledgeBase)
    vs = MagicMock()
    vs.load_index = MagicMock(return_value=False)
    vs.count = MagicMock(return_value=0)
    vs.add = MagicMock()
    vs.save_index = MagicMock()
    vs.search = MagicMock(return_value=[])
    vs.idx_to_doc_id = {}
    vs.documents = {}
    vs.metadatas = {}
    kb.vector_store = vs
    kb.model = MagicMock() if has_model else None
    # AUDIT-129: __init__ bypass edildiği için batch-save durumunu elle ayarla.
    kb._adds_since_save = 0
    kb._last_saved = 0.0
    return kb


class TestKnowledgeBase:
    # add_document — no model → returns False
    async def test_add_document_no_model_returns_false(self):
        kb = _make_kb(has_model=False)
        result = await kb.add_document("content", "cat")
        assert result is False

    # add_document — with model → returns True
    async def test_add_document_with_model_returns_true(self):
        import numpy as np

        kb = _make_kb(has_model=True)
        embedding = np.zeros(384)

        # to_thread called twice: once for encode, once for save_index
        async def fake_to_thread(fn, *args, **kwargs):
            return embedding  # doesn't matter for save_index

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            result = await kb.add_document("content text", "sefer", {"key": "val"})

        assert result is True
        kb.vector_store.add.assert_called_once()

    async def test_add_document_no_metadata_uses_empty_dict(self):
        import numpy as np

        kb = _make_kb(has_model=True)
        embedding = np.zeros(384)

        async def fake_to_thread(fn, *args, **kwargs):
            return embedding

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            result = await kb.add_document("content", "genel", None)

        assert result is True

    # search — no model → returns []
    async def test_search_no_model_returns_empty(self):
        kb = _make_kb(has_model=False)
        result = await kb.search("query")
        assert result == []

    # search — empty vector store → returns []
    async def test_search_empty_store_returns_empty(self):
        kb = _make_kb(has_model=True)
        kb.vector_store.count = MagicMock(return_value=0)
        result = await kb.search("query")
        assert result == []

    # search — low score results filtered out
    async def test_search_low_score_filtered(self):
        import numpy as np

        kb = _make_kb(has_model=True)
        kb.vector_store.count = MagicMock(return_value=3)
        embedding = np.zeros(384)
        search_results = [(0, 0.2)]  # below 0.3 threshold

        # asyncio.to_thread is called twice: once for encode, once for search
        call_results = [embedding, search_results]
        call_idx = 0

        async def fake_to_thread(fn, *args, **kwargs):
            nonlocal call_idx
            result = call_results[call_idx]
            call_idx += 1
            return result

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            result = await kb.search("query")

        assert result == []

    # search — above threshold → returned
    async def test_search_above_threshold_returned(self):
        import numpy as np

        kb = _make_kb(has_model=True)
        kb.vector_store.count = MagicMock(return_value=3)
        kb.vector_store.idx_to_doc_id = {0: "abc123"}
        kb.vector_store.documents = {0: "some content"}
        kb.vector_store.metadatas = {0: {"category": "sefer"}}
        embedding = np.zeros(384)
        search_results = [(0, 0.8)]

        call_results = [embedding, search_results]
        call_idx = 0

        async def fake_to_thread(fn, *args, **kwargs):
            nonlocal call_idx
            result = call_results[call_idx]
            call_idx += 1
            return result

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            result = await kb.search("query")

        assert len(result) == 1
        assert result[0]["score"] == pytest.approx(0.8)
        assert result[0]["content"] == "some content"

    # search — with category filter
    async def test_search_with_category_filter(self):
        import numpy as np

        kb = _make_kb(has_model=True)
        kb.vector_store.count = MagicMock(return_value=1)
        embedding = np.zeros(384)
        search_results = []
        captured_args = {}

        call_results = [embedding, search_results]
        call_idx = 0

        async def fake_to_thread(fn, *args, **kwargs):
            nonlocal call_idx
            result = call_results[call_idx]
            call_idx += 1
            if call_idx == 2:  # second call is the search
                captured_args["source_types"] = args[2] if len(args) > 2 else None
            return result

        with patch("asyncio.to_thread", side_effect=fake_to_thread):
            result = await kb.search("query", category="sefer")

        # source_types should be passed as ["sefer"]
        assert result == []

    # get_stats
    def test_get_stats(self):
        kb = _make_kb(has_model=True)
        kb.vector_store.count = MagicMock(return_value=42)
        stats = kb.get_stats()
        assert stats["total_documents"] == 42
        assert stats["initialized"] is True


# ---------------------------------------------------------------------------
# SmartAIService helpers
# ---------------------------------------------------------------------------


def _make_svc():
    import app.services.smart_ai_service as mod

    svc = mod.SmartAIService.__new__(mod.SmartAIService)
    kb = _make_kb(has_model=True)
    svc.kb = kb
    svc._llm = None
    return svc


class TestSmartAIServiceLearn:
    # learn_from_trip — very efficient (tuketim < 28)
    async def test_learn_from_trip_efficient(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        result = await svc.learn_from_trip(
            {
                "tuketim": 25.0,
                "cikis_yeri": "IST",
                "varis_yeri": "ANK",
                "mesafe_km": 450,
                "ton": 18,
            }
        )
        assert result is True
        call_content = svc.kb.add_document.call_args[0][0]
        assert "Cok verimli" in call_content

    # learn_from_trip — normal (28 <= tuketim <= 38)
    async def test_learn_from_trip_normal(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        await svc.learn_from_trip(
            {
                "tuketim": 33.0,
                "cikis_yeri": "IST",
                "varis_yeri": "BUR",
                "mesafe_km": 150,
                "ton": 20,
            }
        )
        call_content = svc.kb.add_document.call_args[0][0]
        assert "Normal" in call_content

    # learn_from_trip — high consumption (tuketim > 38)
    async def test_learn_from_trip_high_consumption(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        await svc.learn_from_trip(
            {
                "tuketim": 42.0,
                "cikis_yeri": "IST",
                "varis_yeri": "KON",
                "mesafe_km": 300,
                "ton": 25,
            }
        )
        call_content = svc.kb.add_document.call_args[0][0]
        assert "Yuksek tuketim" in call_content

    # learn_from_trip — tuketim None → treated as 0
    async def test_learn_from_trip_none_tuketim(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        await svc.learn_from_trip({"tuketim": None})
        svc.kb.add_document.assert_called_once()

    # learn_from_fuel
    async def test_learn_from_fuel(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        result = await svc.learn_from_fuel(
            {"litre": 450.5, "fiyat_tl": 35.20, "istasyon": "BP", "km_sayac": 123456}
        )
        assert result is True
        call_content = svc.kb.add_document.call_args[0][0]
        assert "450.5" in call_content
        assert "BP" in call_content

    # learn_from_fuel — None values handled
    async def test_learn_from_fuel_none_values(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        await svc.learn_from_fuel({"litre": None, "fiyat_tl": None})
        svc.kb.add_document.assert_called_once()

    # learn_from_log
    async def test_learn_from_log(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        result = await svc.learn_from_log(
            {
                "timestamp": "2024-01-01T00:00:00",
                "level": "ERROR",
                "message": "Fuel spike detected",
                "module": "anomaly_detector",
            }
        )
        assert result is True
        call_content = svc.kb.add_document.call_args[0][0]
        assert "ERROR" in call_content
        assert "Fuel spike detected" in call_content

    async def test_learn_from_log_defaults(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        await svc.learn_from_log({})  # No fields present
        call_content = svc.kb.add_document.call_args[0][0]
        assert "INFO" in call_content  # default level

    # learn_from_event
    async def test_learn_from_event(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        result = await svc.learn_from_event("ANOMALY_DETECTED", {"arac_id": 5})
        assert result is True
        call_content = svc.kb.add_document.call_args[0][0]
        assert "ANOMALY_DETECTED" in call_content

    # teach
    async def test_teach_delegates_to_kb(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        result = await svc.teach("TIR fuel efficiency guide", "manual")
        assert result is True
        svc.kb.add_document.assert_called_once_with(
            "TIR fuel efficiency guide", category="manual"
        )

    async def test_teach_default_category(self):
        svc = _make_svc()
        svc.kb.add_document = AsyncMock(return_value=True)
        await svc.teach("some knowledge")
        _, kwargs = svc.kb.add_document.call_args
        # default category is "genel"
        assert (
            "genel" in svc.kb.add_document.call_args[0]
            or kwargs.get("category") == "genel"
            or svc.kb.add_document.call_args[0][1] == "genel"
        )


# ---------------------------------------------------------------------------
# SmartAIService.ask
# ---------------------------------------------------------------------------


class TestSmartAIServiceAsk:
    async def test_ask_with_context_calls_llm(self):
        svc = _make_svc()
        svc.kb.search = AsyncMock(
            return_value=[
                {
                    "id": "x",
                    "content": "relevant doc",
                    "category": "sefer",
                    "score": 0.9,
                }
            ]
        )
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="LLM answer")
        svc._llm = mock_llm

        result = await svc.ask("yakıt sorusu", use_context=True)

        assert result["answer"] == "LLM answer"
        assert result["context_used"] is True
        assert len(result["sources"]) == 1

    async def test_ask_without_context_no_kb_search(self):
        svc = _make_svc()
        svc.kb.search = AsyncMock(return_value=[])
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="answer no context")
        svc._llm = mock_llm

        result = await svc.ask("question", use_context=False)

        svc.kb.search.assert_not_called()
        assert result["context_used"] is False

    async def test_ask_no_llm_returns_fallback_message(self):
        svc = _make_svc()
        svc.kb.search = AsyncMock(return_value=[])
        svc._llm = None

        with patch.object(svc, "_get_llm", return_value=None):
            result = await svc.ask("question", use_context=False)

        assert (
            "AI istemcisi" in result["answer"] or "kullanilamiyor" in result["answer"]
        )

    async def test_ask_kb_empty_no_context_added(self):
        svc = _make_svc()
        svc.kb.search = AsyncMock(return_value=[])
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="answer")
        svc._llm = mock_llm

        result = await svc.ask("question", use_context=True)

        assert result["context_used"] is False
        assert result["sources"] == []

    async def test_ask_system_prompt_content(self):
        """LLM must receive logistics-focused system prompt."""
        svc = _make_svc()
        svc.kb.search = AsyncMock(return_value=[])
        mock_llm = MagicMock()
        captured_kwargs = {}

        async def capture_chat(**kwargs):
            captured_kwargs.update(kwargs)
            return "OK"

        mock_llm.chat = capture_chat
        svc._llm = mock_llm

        await svc.ask("yakıt", use_context=False)
        assert "lojistik" in captured_kwargs.get("system_prompt", "").lower()


# ---------------------------------------------------------------------------
# SmartAIService.get_stats
# ---------------------------------------------------------------------------


class TestSmartAIServiceGetStats:
    def test_stats_llm_available(self):
        svc = _make_svc()
        svc.kb.vector_store.count = MagicMock(return_value=10)
        svc._llm = MagicMock()

        with patch.object(svc, "_get_llm", return_value=svc._llm):
            stats = svc.get_stats()

        assert stats["llm_status"] == "available"
        assert stats["knowledge_base"]["total_documents"] == 10

    def test_stats_llm_unavailable(self):
        svc = _make_svc()
        svc.kb.vector_store.count = MagicMock(return_value=0)
        svc._llm = None

        with patch.object(svc, "_get_llm", return_value=None):
            stats = svc.get_stats()

        assert stats["llm_status"] == "unavailable"

    def test_stats_embedding_model_status(self):
        svc = _make_svc()
        svc.kb.model = None
        svc.kb.vector_store.count = MagicMock(return_value=0)

        with patch.object(svc, "_get_llm", return_value=None):
            stats = svc.get_stats()

        assert stats["embedding_model"] == "unavailable"

    def test_stats_embedding_model_available(self):
        svc = _make_svc()
        svc.kb.model = MagicMock()
        svc.kb.vector_store.count = MagicMock(return_value=5)

        with patch.object(svc, "_get_llm", return_value=None):
            stats = svc.get_stats()

        assert stats["embedding_model"] == "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# SmartAIService._get_llm
# ---------------------------------------------------------------------------


class TestGetLlm:
    def test_get_llm_caches_client(self):
        svc = _make_svc()
        mock_llm = MagicMock()

        with patch("app.core.ai.llm_client.get_llm_client", return_value=mock_llm):
            r1 = svc._get_llm()
            r2 = svc._get_llm()

        assert r1 is mock_llm
        assert r2 is mock_llm  # cached

    def test_get_llm_exception_returns_none(self):
        svc = _make_svc()
        with patch(
            "app.core.ai.llm_client.get_llm_client",
            side_effect=Exception("no config"),
        ):
            result = svc._get_llm()

        assert result is None
