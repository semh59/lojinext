"""FAISS tabanlı vektör veritabanı. Thread-safe, dosya-tabanlı persist."""

import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from v2.modules.platform_infra.logging.logger import get_logger

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    faiss = None
    FAISS_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Vektör arama sonucu"""

    document: str
    metadata: Dict
    score: float
    source_type: str  # 'vehicle', 'driver', 'trip', 'alert', 'log', 'event'


class FAISSVectorStore:
    """
    FAISS tabanlı vektör veritabanı.
    Yüksek performanslı similarity search.
    THREAD-SAFE implementation for concurrent access.
    """

    # SECURITY: Index size limit (OOM önleme)
    MAX_INDEX_SIZE = 1_000_000  # 1M döküman limiti (Hotfix: Improved capacity)

    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        self.documents: Dict[int, str] = {}  # idx -> document
        self.metadatas: Dict[int, Dict] = {}  # idx -> metadata
        self.doc_id_to_idx: Dict[str, int] = {}  # doc_id -> idx
        self.idx_to_doc_id: Dict[int, str] = {}  # idx -> doc_id
        self.next_idx = 0
        self._lock = threading.Lock()  # Thread-safe guard

        if FAISS_AVAILABLE:
            # L2 distance index (cosine similarity için normalize ediyoruz)
            self.index = faiss.IndexFlatIP(embedding_dim)  # Inner Product
        else:
            self.index = None

    def add(
        self,
        doc_id: str,
        document: str,
        embedding: np.ndarray,
        metadata: Dict,
        user_id: Optional[int] = None,
    ):
        """Döküman ekle/güncelle (Thread-safe)."""
        if self.index is None:
            return

        # Paranoid Validation: Input validation
        if not document or len(document) < 5:
            logger.warning(f"Rejecting too short document for RAG: {doc_id}")
            return

        # SECURITY: Index size limit check
        if self.count() >= self.MAX_INDEX_SIZE:
            logger.warning(
                "FAISS index full (%d docs). Learning silently stopped. doc_id=%s",
                self.MAX_INDEX_SIZE,
                doc_id,
            )
            return False

        # Protection: Max document size (Do prevent OOM/DoS)
        MAX_DOC_SIZE = 10000  # Hard limit for vector store
        if len(document) > MAX_DOC_SIZE:
            logger.warning(
                f"Truncating document {doc_id} (size {len(document)} > {MAX_DOC_SIZE})"
            )
            document = document[:MAX_DOC_SIZE]

        with self._lock:  # CRITICAL SECTION: Dicts and Index update
            # Normalize for cosine similarity
            embedding = embedding.astype(np.float32)
            faiss.normalize_L2(embedding.reshape(1, -1))

            # Metadata zenginleştirme (Multi-tenancy)
            metadata = metadata.copy()
            if user_id is not None:
                metadata["user_id"] = user_id

            # Mevcut doc_id varsa, eski kaydı "deleted" olarak işaretle (upsert)
            if doc_id in self.doc_id_to_idx:
                old_idx = self.doc_id_to_idx[doc_id]
                # Eski metadata'yı "deleted" olarak işaretle (FAISS silme desteklemez)
                self.metadatas[old_idx]["_deleted"] = True

            idx = self.next_idx
            self.next_idx += 1

            self.documents[idx] = document
            self.metadatas[idx] = metadata
            self.doc_id_to_idx[doc_id] = idx
            self.idx_to_doc_id[idx] = doc_id

            self.index.add(embedding.reshape(1, -1))

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        source_types: List[str] = None,
        user_id: Optional[int] = None,
    ) -> List[tuple]:
        """Cosine similarity ile arama (Thread-safe)."""
        if self.index is None or self.index.ntotal == 0:
            return []

        with (
            self._lock
        ):  # FAISS search itself is often thread-safe, but dict access is not
            # Normalize query
            query = query_embedding.astype(np.float32).reshape(1, -1)
            faiss.normalize_L2(query)

            # Search
            k = min(
                top_k * 5, self.index.ntotal
            )  # Filtre için daha fazla al (user_id filtresi için pay bırak)
            distances, indices = self.index.search(query, k)

            results = []
            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:  # Geçersiz index
                    continue

                metadata = self.metadatas.get(idx, {})

                # 1. Silinmiş kayıtları atla
                if metadata.get("_deleted"):
                    continue

                # 2. Multi-tenancy guard: Sadece ilgili kullanıcının verisi veya anonim veri
                if user_id is not None and metadata.get("user_id") is not None:
                    if metadata.get("user_id") != user_id:
                        continue

                # 3. Source type filtresi
                if source_types and metadata.get("source_type") not in source_types:
                    continue

                results.append((idx, float(dist)))

                if len(results) >= top_k:
                    break

            return results

    def save_index(self, folder_path: str):
        """İndeksi ve metadataları diske kaydet (Safe JSON + FAISS Native)"""
        if self.index is None or not FAISS_AVAILABLE:
            return

        import json
        from pathlib import Path

        path = Path(folder_path)
        path.mkdir(parents=True, exist_ok=True)

        with self._lock:  # Prevent modification while saving
            # 1. FAISS Index (Native)
            faiss.write_index(self.index, str(path / "faiss.index"))

            # 2. Metadata (JSON - Güvenli)
            metadata_payload = {
                "documents": self.documents,
                "metadatas": self.metadatas,
                "doc_id_to_idx": self.doc_id_to_idx,
                "idx_to_doc_id": self.idx_to_doc_id,
                "next_idx": self.next_idx,
                "embedding_dim": self.embedding_dim,
            }
            with open(path / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata_payload, f, ensure_ascii=False)

        logger.info(f"FAISS index saved to {folder_path}")

    def load_index(self, folder_path: str) -> bool:
        """İndeksi ve metadataları diskten yükle"""
        if not FAISS_AVAILABLE:
            return False

        import json
        from pathlib import Path

        path = Path(folder_path)
        index_file = path / "faiss.index"
        meta_file = path / "metadata.json"

        if not index_file.exists() or not meta_file.exists():
            return False

        try:
            with self._lock:  # Thread-safe reload
                # 1. FAISS Index
                # read_index → Index (supertype); runtime nesnesi IndexFlatIP.
                # Lib stub'ı bu daralmayı ifade edemiyor.
                self.index = faiss.read_index(str(index_file))  # type: ignore[assignment]

                # 2. Metadata
                with open(meta_file, encoding="utf-8") as f:
                    data = json.load(f)

                    # SECURITY/ROBUSTNESS: Dimension check
                    loaded_dim = data.get("embedding_dim")
                    if loaded_dim and loaded_dim != self.embedding_dim:
                        logger.error(
                            f"Dimension mismatch! Expected {self.embedding_dim}, "
                            f"but loaded index has {loaded_dim}. Clearing index."
                        )
                        # Reset to expected state
                        self.index = faiss.IndexFlatIP(self.embedding_dim)
                        self.documents = {}
                        self.metadatas = {}
                        self.doc_id_to_idx = {}
                        self.idx_to_doc_id = {}
                        self.next_idx = 0
                        return False

                    # JSON anahtarları string gelir, int'e çevir
                    self.documents = {int(k): v for k, v in data["documents"].items()}
                    self.metadatas = {int(k): v for k, v in data["metadatas"].items()}
                    self.doc_id_to_idx = data["doc_id_to_idx"]
                    self.idx_to_doc_id = {
                        int(k): v for k, v in data["idx_to_doc_id"].items()
                    }
                    self.next_idx = data["next_idx"]
                    self.embedding_dim = data["embedding_dim"]

            logger.info(
                f"FAISS index loaded from {folder_path} ({self.count()} vectors)"
            )
            return True
        except Exception as e:
            logger.error(f"FAISS load error: {e}")
            return False

    def count(self) -> int:
        with self._lock:
            return self.index.ntotal if self.index else 0

    def clear(self):
        with self._lock:
            if FAISS_AVAILABLE:
                self.index = faiss.IndexFlatIP(self.embedding_dim)
            self.documents.clear()
            self.metadatas.clear()
            self.doc_id_to_idx.clear()
            self.idx_to_doc_id.clear()
            self.next_idx = 0
