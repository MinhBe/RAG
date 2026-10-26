"""Hybrid retrieval: BM25 + dense vectors, fused with Reciprocal Rank Fusion."""

from dataclasses import dataclass

import numpy as np

from app.rag.bm25 import BM25
from app.rag.embeddings import Embedder
from app.rag.loader import Chunk, Document, chunk_document
from app.rag.text import tokenize


@dataclass
class Hit:
    chunk: Chunk
    score: float  # fused RRF score
    bm25_score: float
    dense_score: float
    bm25_rank: int | None
    dense_rank: int | None


class HybridIndex:
    def __init__(self, documents: list[Document], embedder: Embedder) -> None:
        self.documents = {d.doc_id: d for d in documents}
        self.chunks: list[Chunk] = [c for d in documents for c in chunk_document(d)]
        self.embedder = embedder
        self.bm25 = BM25([tokenize(c.indexed_text) for c in self.chunks])
        self.vectors = embedder.embed([c.indexed_text for c in self.chunks])

    def search(
        self,
        query: str,
        top_k: int = 5,
        candidates: int = 20,
        rrf_k: int = 60,
        mode: str = "hybrid",  # "bm25" and "dense" exist for ablation in the eval
    ) -> list[Hit]:
        bm25 = np.asarray(self.bm25.scores(tokenize(query)))
        dense = self.vectors @ self.embedder.embed([query])[0]

        bm25_order = [i for i in np.argsort(-bm25)[:candidates] if bm25[i] > 0]
        dense_order = list(np.argsort(-dense)[:candidates])
        bm25_rank = {int(i): r for r, i in enumerate(bm25_order, start=1)}
        dense_rank = {int(i): r for r, i in enumerate(dense_order, start=1)}

        fused: dict[int, float] = {}
        rankings = {"hybrid": (bm25_rank, dense_rank), "bm25": (bm25_rank,), "dense": (dense_rank,)}[mode]
        for ranks in rankings:
            for i, r in ranks.items():
                fused[i] = fused.get(i, 0.0) + 1.0 / (rrf_k + r)

        best = sorted(fused, key=fused.get, reverse=True)[:top_k]
        return [
            Hit(
                chunk=self.chunks[i],
                score=fused[i],
                bm25_score=float(bm25[i]),
                dense_score=float(dense[i]),
                bm25_rank=bm25_rank.get(i),
                dense_rank=dense_rank.get(i),
            )
            for i in best
        ]
