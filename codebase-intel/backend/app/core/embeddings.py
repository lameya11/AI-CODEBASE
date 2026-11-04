"""Embedder interface with SentenceTransformer and hashing fallback implementations."""
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_ACTIVE_EMBEDDER: Optional["Embedder"] = None
_EMBEDDER_NAME: str = "unknown"


class Embedder(ABC):
    """Abstract base class for text embedders."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Embed a list of texts.

        Returns an L2-normalized float32 ndarray of shape (len(texts), dim).
        """
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimensionality."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this embedder."""
        ...


class HashingEmbedder(Embedder):
    """
    Deterministic hashing-based TF-IDF-style embedder.

    Does NOT require any model download. Suitable for offline use.
    Each text is hashed into a fixed-size float32 vector using MD5-seeded
    pseudo-random projections of character n-gram frequencies.
    """

    DIM = 128

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self.DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            vecs[i] = self._hash_text(text)
        # L2 normalize
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (vecs / norms).astype(np.float32)

    def _hash_text(self, text: str) -> np.ndarray:
        """Convert text to a deterministic fixed-length float32 vector."""
        vec = np.zeros(self.DIM, dtype=np.float32)
        words = text.lower().split()
        for word in set(words):
            digest = hashlib.md5(word.encode()).digest()
            for j in range(min(16, self.DIM // 8)):
                idx = (digest[j] + digest[(j + 1) % 16] * 256) % self.DIM
                val = (digest[(j + 2) % 16] / 255.0) - 0.5
                vec[idx] += val * words.count(word)
        return vec

    @property
    def dim(self) -> int:
        return self.DIM

    @property
    def name(self) -> str:
        return "HashingEmbedder"


class SentenceTransformerEmbedder(Embedder):
    """Embedder backed by the sentence-transformers library."""

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        self._model = SentenceTransformer(self.MODEL_NAME)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(vecs, dtype=np.float32)

    @property
    def dim(self) -> int:
        return self._model.get_sentence_embedding_dimension()  # type: ignore

    @property
    def name(self) -> str:
        return f"SentenceTransformerEmbedder({self.MODEL_NAME})"


def get_embedder() -> Embedder:
    """
    Return the globally active embedder, initializing it on first call.

    Tries SentenceTransformerEmbedder first; falls back to HashingEmbedder.
    """
    global _ACTIVE_EMBEDDER, _EMBEDDER_NAME
    if _ACTIVE_EMBEDDER is not None:
        return _ACTIVE_EMBEDDER

    try:
        _ACTIVE_EMBEDDER = SentenceTransformerEmbedder()
        _EMBEDDER_NAME = _ACTIVE_EMBEDDER.name
        logger.info("Using SentenceTransformerEmbedder")
    except Exception as exc:
        logger.warning("SentenceTransformerEmbedder unavailable (%s); falling back to HashingEmbedder", exc)
        _ACTIVE_EMBEDDER = HashingEmbedder()
        _EMBEDDER_NAME = _ACTIVE_EMBEDDER.name

    return _ACTIVE_EMBEDDER


def get_embedder_name() -> str:
    """Return the name of the currently active embedder (initializes if needed)."""
    get_embedder()
    return _EMBEDDER_NAME
