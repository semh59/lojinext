"""
RAG Engine Unit Tests
"""

import sys

import numpy as np
import pytest

sys.path.insert(0, ".")

from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
    FAISS_AVAILABLE,
    SENTENCE_TRANSFORMERS_AVAILABLE,
    FAISSVectorStore,
    RAGEngine,
    SearchResult,
    is_rag_available,
)


class TestRAGAvailability:
    """RAG bağımlılık kontrolü testleri"""

    def test_sentence_transformers_import(self):
        """Sentence-Transformers import kontrolü"""
        assert isinstance(SENTENCE_TRANSFORMERS_AVAILABLE, bool)

    def test_faiss_import(self):
        """FAISS import kontrolü"""
        assert isinstance(FAISS_AVAILABLE, bool)

    def test_is_rag_available_function(self):
        """is_rag_available fonksiyon kontrolü"""
        result = is_rag_available()
        assert isinstance(result, bool)
        assert result == (SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE)


class TestFAISSVectorStore:
    """FAISSVectorStore sınıf testleri"""

    @pytest.fixture
    def store(self):
        """Test store instance"""
        if not FAISS_AVAILABLE:
            pytest.skip("FAISS not installed")
        return FAISSVectorStore(embedding_dim=384)

    def test_init(self, store):
        """Store başlatma testi"""
        assert store is not None
        assert store.embedding_dim == 384
        assert store.count() == 0

    def test_add_document(self, store):
        """Döküman ekleme testi"""
        embedding = np.random.rand(384).astype(np.float32)
        metadata = {"source_type": "vehicle", "source_id": 1}

        store.add("vehicle_1", "Test document", embedding, metadata)

        assert store.count() == 1
        assert "vehicle_1" in store.doc_id_to_idx

    def test_add_multiple_documents(self, store):
        """Çoklu döküman ekleme testi"""
        for i in range(5):
            embedding = np.random.rand(384).astype(np.float32)
            metadata = {"source_type": "trip", "source_id": i}
            store.add(f"trip_{i}", f"Document {i}", embedding, metadata)

        assert store.count() == 5

    def test_search_basic(self, store):
        """Temel arama testi"""
        # Dökümanlar ekle
        for i in range(5):
            embedding = np.random.rand(384).astype(np.float32)
            metadata = {"source_type": "vehicle", "source_id": i}
            store.add(f"vehicle_{i}", f"Vehicle {i}", embedding, metadata)

        # Ara
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.search(query_embedding, top_k=3)

        assert len(results) <= 3
        # Sonuçlar (idx, score) tuple olmalı
        for idx, score in results:
            assert isinstance(idx, (int, np.integer))
            assert isinstance(score, (float, np.floating))

    def test_search_with_filter(self, store):
        """Filtreli arama testi"""
        # Farklı tiplerde dökümanlar ekle
        for i in range(3):
            embedding = np.random.rand(384).astype(np.float32)
            store.add(
                f"vehicle_{i}",
                f"Vehicle {i}",
                embedding,
                {"source_type": "vehicle", "source_id": i},
            )

        for i in range(3):
            embedding = np.random.rand(384).astype(np.float32)
            store.add(
                f"driver_{i}",
                f"Driver {i}",
                embedding,
                {"source_type": "driver", "source_id": i},
            )

        query_embedding = np.random.rand(384).astype(np.float32)

        # Sadece vehicle ara
        results = store.search(query_embedding, top_k=5, source_types=["vehicle"])

        for idx, score in results:
            source_type = store.metadatas.get(idx, {}).get("source_type")
            assert source_type == "vehicle"

    def test_clear(self, store):
        """Temizleme testi"""
        for i in range(5):
            embedding = np.random.rand(384).astype(np.float32)
            store.add(f"doc_{i}", f"Document {i}", embedding, {})

        assert store.count() == 5

        store.clear()

        assert store.count() == 0
        assert len(store.documents) == 0


class TestRAGEngine:
    """RAGEngine sınıf testleri"""

    @pytest.fixture
    def engine(self):
        """Test engine instance — fresh in-memory store for isolation."""
        if not (SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE):
            pytest.skip("RAG dependencies not installed")
        engine = RAGEngine()
        ready = engine.wait_until_ready(timeout=120.0)
        if not ready:
            pytest.fail("RAG Engine failed to initialize within timeout")
        # Reset to empty store so tests are not affected by persisted index data
        engine.vector_store = FAISSVectorStore(engine.EMBEDDING_DIM)
        return engine

    def test_init(self, engine):
        """Engine başlatma testi"""
        assert engine is not None
        assert engine.is_initialized
        assert engine.embedder is not None
        assert engine.vector_store is not None

    @pytest.mark.asyncio
    async def test_generate_embedding(self, engine):
        """Embedding oluşturma testi"""
        text = "Bu bir test metnidir."
        embedding = await engine._generate_embedding(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (engine.EMBEDDING_DIM,)

    def test_create_document_id(self, engine):
        """Document ID oluşturma testi"""
        doc_id = engine._create_document_id("vehicle", 123)
        assert doc_id == "vehicle_123"

    @pytest.mark.asyncio
    async def test_index_vehicle(self, engine):
        """Araç indeksleme testi"""
        vehicle_data = {
            "id": 1,
            "plaka": "34ABC123",
            "marka": "Volvo",
            "model": "FH",
            "yil": 2020,
            "hedef_tuketim": 30.0,
            "tank_kapasitesi": 600,
            "aktif": True,
        }

        result = await engine.index_vehicle(vehicle_data)

        assert result
        assert engine.vector_store.count() == 1

    @pytest.mark.asyncio
    async def test_index_driver(self, engine):
        """Şoför indeksleme testi"""
        driver_data = {
            "id": 1,
            "ad_soyad": "Ahmet Yılmaz",
            "ehliyet_sinifi": "E",
            "score": 0.95,
            "aktif": True,
        }

        result = await engine.index_driver(driver_data)

        assert result

    @pytest.mark.asyncio
    async def test_index_trip(self, engine):
        """Sefer indeksleme testi"""
        from datetime import date

        trip_data = {
            "id": 1,
            "tarih": date.today(),
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450,
            "ton": 20,
            "tuketim": 32.5,
            "durum": "Tamamlandı",
        }

        result = await engine.index_trip(trip_data)

        assert result


    @pytest.mark.asyncio
    async def test_search(self, engine):
        """Arama testi"""
        # Veri indeksle
        vehicles = [
            {"id": 1, "plaka": "34ABC001", "marka": "Volvo", "model": "FH"},
            {"id": 2, "plaka": "06DEF002", "marka": "Mercedes", "model": "Actros"},
            {"id": 3, "plaka": "35GHI003", "marka": "MAN", "model": "TGX"},
        ]

        for v in vehicles:
            await engine.index_vehicle(v)

        # Ara
        results = await engine.search("Volvo marka araç", top_k=3)

        assert len(results) > 0
        assert isinstance(results[0], SearchResult)
        assert results[0].score >= 0

    @pytest.mark.asyncio
    async def test_search_for_context(self, engine):
        """Context için arama testi"""
        vehicles = [
            {"id": 1, "plaka": "34ABC001", "marka": "Volvo", "hedef_tuketim": 28.0},
        ]

        for v in vehicles:
            await engine.index_vehicle(v)

        # Context oluştur (RAG engine artık async)
        context = await engine.search_for_context("En verimli araç hangisi?", top_k=1)

        assert isinstance(context, str)
        assert len(context) > 0
        assert "Araç" in context or "İlgili" in context

    def test_get_stats(self, engine):
        """İstatistik testi"""
        stats = engine.get_stats()

        assert stats["initialized"]
        assert "total_documents" in stats
        assert stats["vector_store"] == "FAISS"

    @pytest.mark.asyncio
    async def test_clear_index(self, engine):
        """İndeks temizleme testi"""
        # Veri ekle
        await engine.index_vehicle({"id": 1, "plaka": "TEST"})

        assert engine.vector_store.count() > 0

        # Temizle
        result = engine.clear_index()

        assert result
        assert engine.vector_store.count() == 0


class TestSearchResult:
    """SearchResult dataclass testleri"""

    def test_search_result_dataclass(self):
        """SearchResult dataclass testi"""
        result = SearchResult(
            document="Test document",
            metadata={"source_id": 1},
            score=0.85,
            source_type="vehicle",
        )

        assert result.document == "Test document"
        assert result.score == 0.85
        assert result.source_type == "vehicle"


class TestIntegration:
    """Entegrasyon testleri"""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not (SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE),
        reason="RAG dependencies not installed",
    )
    async def test_full_rag_pipeline(self):
        """Tam RAG pipeline testi"""
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        engine = RAGEngine()
        # CRITICAL: Wait for model to load
        assert engine.wait_until_ready(timeout=60.0), (
            "RAG Engine timeout during integration test"
        )

        # Veri indeksle
        vehicles = [
            {
                "id": 1,
                "plaka": "34ABC001",
                "marka": "Volvo",
                "model": "FH",
                "hedef_tuketim": 28.0,
            },
            {
                "id": 2,
                "plaka": "06DEF002",
                "marka": "Mercedes",
                "model": "Actros",
                "hedef_tuketim": 30.0,
            },
        ]

        drivers = [
            {"id": 1, "ad_soyad": "Ali Veli", "score": 0.95},
            {"id": 2, "ad_soyad": "Mehmet Yılmaz", "score": 0.88},
        ]

        for v in vehicles:
            await engine.index_vehicle(v)
        for d in drivers:
            await engine.index_driver(d)

        # Farklı sorgular test et
        queries = [
            "Volvo araç bilgileri",
            "En yüksek skorlu şoför",
            "34ABC plakalı araç",
        ]

        for query in queries:
            results = await engine.search(query, top_k=2)
            assert len(results) > 0, f"'{query}' için sonuç bulunamadı"

        # Context oluşturma
        context = await engine.search_for_context("Hangisi daha verimli?")
        assert len(context) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
