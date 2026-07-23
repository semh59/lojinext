"""
TIR Yakıt Takip - RAG (Retrieval-Augmented Generation) Engine
Sentence-BERT + FAISS ile vektör arama
"""

import asyncio
import threading
import time
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from app.config import settings
from v2.modules.ai_assistant.infrastructure.rag.vector_store import (
    FAISS_AVAILABLE,
    FAISSVectorStore,
    SearchResult,
)
from v2.modules.platform_infra.logging.logger import get_logger

# Lazy imports for heavy dependencies
SENTENCE_TRANSFORMERS_AVAILABLE = False

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
else:
    try:
        from sentence_transformers import SentenceTransformer

        SENTENCE_TRANSFORMERS_AVAILABLE = True
    except ImportError:
        SentenceTransformer = None


logger = get_logger(__name__)


class RAGEngine:
    """
    Retrieval-Augmented Generation motoru.

    1. Sefer, araç, şoför verilerini embedding'e çevirir
    2. FAISS'te saklar
    3. Kullanıcı sorusuna en yakın kayıtları bulur
    4. Context olarak AI'ya verir

    Embedding Model: paraphrase-multilingual-MiniLM-L12-v2
    - Türkçe dahil 50+ dil desteği
    - 384 boyutlu embedding
    - Hızlı inference

    Vector Store: FAISS
    - Yüksek performanslı similarity search
    - GPU desteği (opsiyonel)
    - Milyonlarca vektör için optimize
    """

    # Config defaults (loaded from settings/env)
    EMBEDDING_MODEL: Optional[str] = None
    EMBEDDING_DIM: Optional[int] = None
    RAG_MAX_CHARS: int = 4000
    SIMILARITY_THRESHOLD: float = 0.35

    def __init__(self):
        self.embedder = None
        self.vector_store = None
        self.is_initialized = False
        self.status = "offline"
        self._init_lock = threading.Lock()
        self._last_inference_time_ms: float = 0.0

        # Prioritize settings/env over hardcoded defaults
        self.EMBEDDING_MODEL = settings.AI_EMBEDDING_MODEL or "BAAI/bge-m3"
        self.EMBEDDING_DIM = settings.AI_EMBEDDING_DIM or 1024
        self.RAG_MAX_CHARS = settings.AI_RAG_MAX_CHARS or 4000
        self.SIMILARITY_THRESHOLD = settings.AI_RAG_THRESHOLD or 0.35
        self.MAX_DOCUMENT_CHARS = settings.AI_RAG_MAX_DOC_CHARS or 10000

        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE:
            logger.warning("RAG dependencies missing (sentence-transformers or faiss)")
            return

        # Start loading in background thread to avoid blocking FastAPI startup
        self.status = "loading"
        threading.Thread(target=self._initialize_sync, daemon=True).start()

    def _initialize_sync(self):
        """Synchronous initialization for background thread."""
        with self._init_lock:
            try:
                # Embedding model - SECURITY: trust_remote_code=False explicit
                logger.info(
                    f"Loading embedding model in background: {self.EMBEDDING_MODEL}"
                )
                self.embedder = SentenceTransformer(
                    self.EMBEDDING_MODEL,
                    trust_remote_code=False,  # SECURITY FIX: No arbitrary code execution
                )

                # FAISS vector store
                self.vector_store = FAISSVectorStore(self.EMBEDDING_DIM)
                self.is_initialized = True

                # Load persisted index before signalling ready so that
                # wait_until_ready() guarantees disk state is applied.
                self.load_from_disk()
                self.status = "ready"
                logger.info("RAG Engine background initialization complete")

            except Exception as e:
                logger.error(f"RAG Engine initialization failed: {e}")
                self.is_initialized = False
                self.status = "error"

    def wait_until_ready(self, timeout: float = 60.0) -> bool:
        """Wait until engine is ready (blocks until timeout)."""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_initialized and self.status == "ready":
                return True
            if self.status == "error":
                return False
            time.sleep(0.1)
        return False

    def save_to_disk(self, path: str = "app/data/vector_store"):
        """Vektör dükkanını diske kaydet.

        Path WORKDIR'e (`/app`) göre relatif — `app/data/...` repo'nun
        `app/` paketinin ALTINDAKİ `data/` klasörüne (`/app/app/data/...`)
        çözümlenir, ki bu docker-compose'un `app_data:/app/app/data`
        named-volume mount'uyla aynı yol (kök CLAUDE.md'nin "Index
        persisted to app/data/ai_kb/" dokümantasyonuyla tutarlı — repo
        köküne göre `app/data/...`). Eski `"data/vector_store"` varsayılanı
        bu mount'un DIŞINA (`/app/data/...`) yazıyordu; indeks her
        container yeniden-oluşturmada kayboluyor, replica'lar arasında
        paylaşılmıyordu (2026-07-17 dedektif denetiminde bulundu).
        """
        if self.is_initialized and self.vector_store:
            self.vector_store.save_index(path)

    def load_from_disk(self, path: str = "app/data/vector_store"):
        """Vektör dükkanını diskten yükle (bkz. `save_to_disk` docstring'i)."""
        if self.is_initialized and self.vector_store:
            self.vector_store.load_index(path)

    async def _generate_embedding(self, text: str):
        """Metin için embedding üret (CPU-bound, thread'de çalışır)."""
        if not self.embedder:
            raise RuntimeError("Embedding model not loaded")
        return await asyncio.to_thread(self.embedder.encode, text)

    def _create_document_id(self, source_type: str, source_id: int) -> str:
        """Benzersiz document ID oluştur."""
        return f"{source_type}_{source_id}"

    async def index_vehicle(
        self, vehicle_data: Dict, user_id: Optional[int] = None
    ) -> bool:
        """Araç verisini indeksle."""
        if not self.is_initialized:
            return False

        try:
            # Paranoid validation
            plaka = str(vehicle_data.get("plaka", "")).strip()[:20]
            if not plaka:
                return False

            doc_id = self._create_document_id("vehicle", vehicle_data["id"])

            text = f"""
            Araç: {plaka}
            Marka/Model: {str(vehicle_data.get("marka", ""))[:50]} {str(vehicle_data.get("model", ""))[:50]}
            Yıl: {vehicle_data.get("yil", "Bilinmiyor")}
            Hedef Tüketim: {vehicle_data.get("hedef_tuketim", 32.0)} L/100km
            Tank Kapasitesi: {vehicle_data.get("tank_kapasitesi", 600)} litre
            Durum: {"Aktif" if vehicle_data.get("aktif", True) else "Pasif"}
            """

            embedding = await self._generate_embedding(text.strip())
            metadata = {
                "source_type": "vehicle",
                "source_id": vehicle_data["id"],
                "plaka": plaka,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }

            self.vector_store.add(
                doc_id, text.strip(), embedding, metadata, user_id=user_id
            )
            return True

        except Exception as e:
            logger.error(f"Vehicle indexing error: {e}")
            return False

    async def index_driver(
        self,
        driver_data: Dict,
        stats: Optional[Dict] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """Şoför verisini indeksle."""
        if not self.is_initialized:
            return False

        try:
            # Paranoid validation
            ad_soyad = str(driver_data.get("ad_soyad", "")).strip()[:100]
            if not ad_soyad:
                return False

            doc_id = self._create_document_id("driver", driver_data["id"])

            text = f"""
            Şoför: {ad_soyad}
            Ehliyet Sınıfı: {str(driver_data.get("ehliyet_sinifi", "E"))[:10]}
            Performans Skoru: {driver_data.get("score", 1.0)}
            Durum: {"Aktif" if driver_data.get("aktif", True) else "Pasif"}
            """

            if stats:
                text += f"""
                Toplam Sefer: {stats.get("toplam_sefer", 0)}
                Toplam KM: {stats.get("toplam_km", 0)}
                Ortalama Tüketim: {stats.get("ort_tuketim", 0)} L/100km
                Filo Karşılaştırma: {stats.get("filo_karsilastirma", 0)}%
                """

            embedding = await self._generate_embedding(text.strip())
            metadata = {
                "source_type": "driver",
                "source_id": driver_data["id"],
                "ad_soyad": ad_soyad,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }

            self.vector_store.add(
                doc_id, text.strip(), embedding, metadata, user_id=user_id
            )
            return True

        except Exception as e:
            logger.error(f"Driver indexing error: {e}")
            return False

    async def index_trip(self, trip_data: Dict, user_id: Optional[int] = None) -> bool:
        """Sefer verisini indeksle."""
        if not self.is_initialized:
            return False

        try:
            doc_id = self._create_document_id("trip", trip_data["id"])

            tarih = trip_data.get("tarih", "")
            if isinstance(tarih, date):
                tarih = tarih.isoformat()

            # Paranoid validation
            cikis = str(trip_data.get("cikis_yeri", ""))[:100]
            varis = str(trip_data.get("varis_yeri", ""))[:100]

            text = f"""
            Sefer #{trip_data["id"]}
            Tarih: {tarih}
            Güzergah: {cikis} → {varis}
            Mesafe: {trip_data.get("mesafe_km", 0)} km
            Yük: {trip_data.get("ton", 0)} ton
            Tüketim: {trip_data.get("tuketim", "Bilinmiyor")} L/100km
            Durum: {str(trip_data.get("durum", "Planlandı"))[:20]}
            """

            embedding = await self._generate_embedding(text.strip())
            metadata = {
                "source_type": "trip",
                "source_id": trip_data["id"],
                "tarih": tarih,
                "cikis_yeri": cikis,
                "varis_yeri": varis,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }

            self.vector_store.add(
                doc_id, text.strip(), embedding, metadata, user_id=user_id
            )
            return True

        except Exception as e:
            logger.error(f"Trip indexing error: {e}")
            return False

    # 2026-07-18 ölü-kod temizliği: index_alert/index_log/index_event/
    # bulk_index silindi — repo genelinde sıfır prod çağıran (yalnız
    # kendi testleri), dalga-12 öncesinden beri ölüydü.

    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_types: List[str] = None,
        user_id: Optional[int] = None,
    ) -> List[SearchResult]:
        """Vektör arama (Async & Multi-threaded)."""
        if not self.is_initialized:
            return []

        t_start = time.perf_counter()
        try:
            # Input sanitization
            query = str(query).strip()[:500]
            if not query:
                return []

            # Guard: Limit top_k to prevent excessive resource usage
            if top_k > 20:
                top_k = 20

            # Embedding üretimi zaten thread'de yapılıyor
            query_embedding = await self._generate_embedding(query)

            # FAISS'in kendi arama işlemi de thread'e alınmalı (CPU-bound)
            results = await asyncio.to_thread(
                self.vector_store.search,
                query_embedding,
                top_k,
                source_types,
                user_id=user_id,
            )

            search_results = []
            for idx, score in results:
                doc = self.vector_store.documents.get(idx, "")
                metadata = self.vector_store.metadatas.get(idx, {})

                search_results.append(
                    SearchResult(
                        document=doc,
                        metadata=metadata,
                        score=round(score, 4),
                        source_type=metadata.get("source_type", "unknown"),
                    )
                )

            elapsed_ms = (time.perf_counter() - t_start) * 1000
            self._last_inference_time_ms = round(elapsed_ms, 2)
            logger.info(
                f"RAG search completed | query_len={len(query)} | "
                f"results={len(search_results)} | time={self._last_inference_time_ms}ms"
            )
            return search_results

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error(f"Search error ({elapsed_ms:.1f}ms): {e}")
            return []

    async def search_for_context(
        self,
        query: str,
        top_k: int = 3,
        max_chars: int = 4000,  # Context Window Guard
        user_id: Optional[int] = None,
    ) -> str:
        """AI context için arama sonuçlarını formatla (Guard Katmanlı)."""
        t_start = time.perf_counter()
        results = await self.search(query, top_k, user_id=user_id)

        if not results:
            return ""

        context_parts = ["### İlgili Geçmiş Veriler (RAG)"]
        current_len = 0

        for i, result in enumerate(results, 1):
            source_map = {
                "vehicle": "🚛 Araç",
                "driver": "👤 Şoför",
                "trip": "📍 Sefer",
                "alert": "⚠️ Uyarı",
                "log": "📋 Log",
                "event": "⚡ Olay",
            }
            source_label = source_map.get(result.source_type, "📄 Kayıt")

            # Guard: Similarity Threshold
            if result.score < self.SIMILARITY_THRESHOLD:
                logger.debug(f"Skipping result with low score: {result.score:.2f}")
                continue

            # Guard: Karakter bazlı limit kontrolü
            entry = f"\n**{i}. {source_label}** (Benzerlik: {result.score:.0%})\n{result.document}"

            if current_len + len(entry) > max_chars:
                context_parts.append(
                    "\n[... Diğer veriler bağlam sınırını aşmamak için dahil edilmedi ...]"
                )
                break

            context_parts.append(entry)
            current_len += len(entry)

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            f"RAG context search | query_len={len(query)} | "
            f"context_chars={current_len} | total_time={elapsed_ms:.1f}ms"
        )
        return "\n".join(context_parts)

    def get_stats(self) -> Dict:
        """İndeks istatistikleri."""
        if not self.is_initialized:
            return {"initialized": False}

        return {
            "initialized": True,
            "total_documents": self.vector_store.count() if self.vector_store else 0,
            "embedding_model": self.EMBEDDING_MODEL,
            "vector_store": "FAISS",
            "last_inference_time_ms": self._last_inference_time_ms,
        }

    def clear_index(self) -> bool:
        """Tüm indeksi temizle."""
        if not self.is_initialized:
            return False

        try:
            self.vector_store.clear()
            logger.info("RAG index cleared")
            return True
        except Exception as e:
            logger.error(f"Clear index error: {e}")
            return False


# Singleton
_rag_engine = None
_rag_engine_lock = threading.Lock()


def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        with _rag_engine_lock:
            if _rag_engine is None:  # Double-check locking
                _rag_engine = RAGEngine()
    return _rag_engine


def is_rag_available() -> bool:
    """RAG kullanılabilir mi kontrol et"""
    return SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE
