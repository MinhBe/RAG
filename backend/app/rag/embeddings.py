"""Dense embedders.

`HashingEmbedder` is a dependency-free baseline (character n-grams hashed into a
fixed vector) so the project runs offline and in CI. `BgeM3Embedder` is the
real model; it needs `requirements-ml.txt` and downloads ~2.3 GB on first use.
"""

import hashlib
from typing import Protocol

import numpy as np

from app.rag.text import fold, normalize, syllables


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalised vectors, one row per text."""
        ...


def _l2(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


class HashingEmbedder:
    name = "hashing-char-ngram"

    def __init__(self, dim: int = 2048, ngram_range: tuple[int, int] = (3, 5)) -> None:
        self.dim = dim
        self.ngram_range = ngram_range

    def _features(self, text: str) -> list[str]:
        folded = " " + " ".join(fold(s) for s in syllables(normalize(text))) + " "
        feats = []
        lo, hi = self.ngram_range
        for n in range(lo, hi + 1):
            feats.extend(folded[i : i + n] for i in range(len(folded) - n + 1))
        return feats

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat in self._features(text):
                # Python's hash() is salted per process; use a stable hash instead.
                h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "little")
                sign = 1.0 if (h >> 63) else -1.0
                out[row, h % self.dim] += sign
        return _l2(out)


class BgeM3Embedder:
    name = "BAAI/bge-m3"

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # optional dependency

        self.model = SentenceTransformer(self.name)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, normalize_embeddings=True, batch_size=16)
        return np.asarray(vectors, dtype=np.float32)


def build_embedder(kind: str) -> Embedder:
    if kind == "bge-m3":
        return BgeM3Embedder()
    if kind == "hashing":
        return HashingEmbedder()
    raise ValueError(f"Unknown embedder: {kind}")
