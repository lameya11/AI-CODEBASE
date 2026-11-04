"""Per-repo vector store with FAISS or numpy fallback."""
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.embeddings import Embedder, get_embedder

logger = logging.getLogger(__name__)

_VECTOR_BACKEND: str = "numpy"  # updated on first use if FAISS is available


class VectorStore:
    """
    Per-repository vector index.

    Uses FAISS IndexFlatIP if available, otherwise numpy matrix multiplication.
    Persists the index and chunk ID mapping under DATA_DIR/indexes/{repo_id}/.
    """

    def __init__(self, repo_id: str, index_dir: Path) -> None:
        self.repo_id = repo_id
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self._chunk_ids: list[int] = []
        self._vectors: Optional[np.ndarray] = None   # shape (n, dim)
        self._faiss_index = None
        self._use_faiss = False
        self._dim: int = 0

        # Try to load existing index from disk
        self._load()

    # ---- public interface ----

    def add(self, chunk_ids: list[int], texts: list[str], embedder: Optional[Embedder] = None) -> None:
        """Embed texts and add them to the index."""
        if not texts:
            return
        emb = embedder or get_embedder()
        vecs = emb.embed_texts(texts)  # already L2-normalized
        self._dim = vecs.shape[1]

        if self._use_faiss or self._try_init_faiss(self._dim):
            self._faiss_index.add(vecs)  # type: ignore
        else:
            if self._vectors is None:
                self._vectors = vecs
            else:
                self._vectors = np.vstack([self._vectors, vecs])

        self._chunk_ids.extend(chunk_ids)
        self._save()

    def search(self, query: str, k: int = 8, embedder: Optional[Embedder] = None) -> list[dict]:
        """
        Search for the top-k closest chunks.

        Returns list of dicts: {chunk_id, score, rank}.
        """
        if not self._chunk_ids:
            return []

        emb = embedder or get_embedder()
        qvec = emb.embed_texts([query])  # shape (1, dim)

        if self._use_faiss and self._faiss_index is not None:
            scores, indices = self._faiss_index.search(qvec, min(k, len(self._chunk_ids)))
            results = []
            for rank, (idx, score) in enumerate(zip(indices[0], scores[0])):
                if idx < 0 or idx >= len(self._chunk_ids):
                    continue
                results.append({
                    "chunk_id": self._chunk_ids[idx],
                    "score": float(score),
                    "rank": rank,
                })
            return results
        else:
            # numpy cosine similarity (vectors are L2-normalized, so dot = cosine)
            if self._vectors is None or len(self._vectors) == 0:
                return []
            scores = (self._vectors @ qvec.T).squeeze()
            if scores.ndim == 0:
                scores = np.array([float(scores)])
            top_k = min(k, len(self._chunk_ids))
            indices = np.argsort(scores)[::-1][:top_k]
            return [
                {
                    "chunk_id": self._chunk_ids[int(i)],
                    "score": float(scores[i]),
                    "rank": rank,
                }
                for rank, i in enumerate(indices)
            ]

    def clear(self) -> None:
        """Remove all vectors from this index."""
        self._chunk_ids = []
        self._vectors = None
        self._faiss_index = None
        self._use_faiss = False

    def backend_name(self) -> str:
        return "faiss" if self._use_faiss else "numpy"

    # ---- persistence ----

    @property
    def _index_path(self) -> Path:
        return self.index_dir / "index.faiss"

    @property
    def _numpy_path(self) -> Path:
        return self.index_dir / "vectors.npy"

    @property
    def _ids_path(self) -> Path:
        return self.index_dir / "chunk_ids.json"

    def _save(self) -> None:
        """Persist index and chunk ID list to disk."""
        self._ids_path.write_text(json.dumps(self._chunk_ids))
        if self._use_faiss and self._faiss_index is not None:
            import faiss  # type: ignore
            faiss.write_index(self._faiss_index, str(self._index_path))
        elif self._vectors is not None:
            np.save(str(self._numpy_path), self._vectors)

    def _load(self) -> None:
        """Try to load a previously saved index from disk."""
        if not self._ids_path.exists():
            return
        try:
            self._chunk_ids = json.loads(self._ids_path.read_text())
        except Exception:
            self._chunk_ids = []
            return

        # Try FAISS first
        if self._index_path.exists():
            try:
                import faiss  # type: ignore
                self._faiss_index = faiss.read_index(str(self._index_path))
                self._use_faiss = True
                self._dim = self._faiss_index.d
                global _VECTOR_BACKEND
                _VECTOR_BACKEND = "faiss"
                return
            except Exception:
                pass

        # Numpy fallback
        if self._numpy_path.exists():
            try:
                self._vectors = np.load(str(self._numpy_path))
                self._dim = self._vectors.shape[1] if self._vectors.ndim == 2 else 0
            except Exception:
                self._vectors = None

    def _try_init_faiss(self, dim: int) -> bool:
        """Try to create a FAISS index; return True on success."""
        global _VECTOR_BACKEND
        try:
            import faiss  # type: ignore
            self._faiss_index = faiss.IndexFlatIP(dim)
            self._use_faiss = True
            _VECTOR_BACKEND = "faiss"
            return True
        except Exception:
            return False


def get_vector_backend() -> str:
    return _VECTOR_BACKEND
