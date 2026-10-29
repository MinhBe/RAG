"""Nhúng (embedding) — tự host, không gọi API ngoài.

EMBEDDER=hashing : vector băm tất định, chạy ngay, không tải model (M0/M1).
EMBEDDER=vie-v2  : AITeamVN/Vietnamese_Embedding_v2 (cần requirements-ml.txt).
EMBEDDER=bge-m3  : BAAI/bge-m3.

Mọi chế độ trả vector đúng EMBED_DIM để cột pgvector không đổi khi nâng cấp
(đổi model vẫn phải index lại, nhưng lược đồ giữ nguyên).
"""

from __future__ import annotations

import hashlib
import threading

from loguru import logger

from app.config import get_settings
from app.rag.text import tokenize

settings = get_settings()
DIM = settings.embed_dim

_MODEL = None
# Luồng nạp sẵn lúc khởi động và câu hỏi đầu tiên có thể cùng gọi _load_model.
_LOAD_LOCK = threading.Lock()


def _hash_embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for t in texts:
        vec = [0.0] * DIM
        for tok in tokenize(t):
            h = int.from_bytes(hashlib.md5(tok.encode("utf-8")).digest()[:8], "big")
            idx = h % DIM
            sign = 1.0 if (h >> 63) & 1 else -1.0
            vec[idx] += sign
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        out.append([v / norm for v in vec])
    return out


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL
        from sentence_transformers import SentenceTransformer

        name = {
            "vie-v2": "AITeamVN/Vietnamese_Embedding_v2",
            "bge-m3": "BAAI/bge-m3",
        }.get(settings.embedder, settings.embedder)
        logger.info("Tải model embedding: {}", name)
        _MODEL = SentenceTransformer(name)
    return _MODEL


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if settings.embedder == "hashing":
        return _hash_embed(texts)
    model = _load_model()
    vecs = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
