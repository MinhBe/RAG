"""Okapi BM25 over pre-tokenised documents."""

import math
from collections import Counter


class BM25:
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.term_freqs = [Counter(doc) for doc in corpus]
        self.doc_lens = [len(doc) for doc in corpus]
        self.avg_len = sum(self.doc_lens) / max(len(corpus), 1)

        df: Counter[str] = Counter()
        for tf in self.term_freqs:
            df.update(tf.keys())
        n = len(corpus)
        # BM25+ style idf that never goes negative for very common terms.
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, length in zip(self.term_freqs, self.doc_lens):
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_len)
            for term in set(query):
                freq = tf.get(term)
                if freq:
                    score += self.idf[term] * freq * (self.k1 + 1) / (freq + norm)
            out.append(score)
        return out
