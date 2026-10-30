"""Thử phân cụm chủ đề trên embedding các Điều đang có hiệu lực.

    docker compose exec api python -m scripts.probe_clusters

Câu hỏi cần trả lời trước khi đầu tư: cụm có mang thông tin mới không, hay chỉ
lặp lại Chương? Đo bằng NMI/ARI với Chương, và tỉ lệ cụm gom được Điều của cả
Bộ luật lẫn Nghị định (thứ Chương không làm được, vì Chương nằm trong một văn bản).
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sqlalchemy import text as sa_text

from app.db.base import engine


def load():
    with engine.connect() as c:
        rows = c.execute(sa_text(
            "SELECT node_id, doc_id, chapter_no, heading, embedding::text AS emb "
            "FROM legal_node WHERE level='article' AND effective_to IS NULL "
            "AND embedding IS NOT NULL ORDER BY node_id"
        )).all()
    X = np.array([json.loads(r.emb) for r in rows], dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    return rows, X


def main() -> None:
    rows, X = load()
    docs = np.array([r.doc_id for r in rows])
    chap = np.array([f"{r.doc_id}:{r.chapter_no}" for r in rows])
    print(f"{len(rows)} Điều có hiệu lực: {dict(Counter(docs))}, {len(set(chap))} Chương\n")

    print(" k  silhouette  NMI~Chương  ARI~Chương  cụm trộn 2 văn bản")
    best = None
    for k in (12, 16, 20, 24, 30, 36):
        lab = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
        sil = silhouette_score(X, lab, metric="cosine")
        nmi = normalized_mutual_info_score(chap, lab)
        ari = adjusted_rand_score(chap, lab)
        mixed = sum(1 for c in range(k) if len(set(docs[lab == c])) > 1)
        print(f"{k:2d}  {sil:10.3f}  {nmi:10.3f}  {ari:10.3f}  {mixed:3d}/{k}")
        if best is None or sil > best[1]:
            best = (k, sil, lab)

    # agglomerative cosine for comparison at the best k
    k, _, lab = best
    agg = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(X)
    print(f"\nAgglomerative k={k}: silhouette={silhouette_score(X, agg, metric='cosine'):.3f}"
          f"  cỡ cụm lớn nhất={max(Counter(agg).values())}")

    print(f"\n── Mẫu cụm KMeans k={k} (cụm trộn 2 văn bản trước) ──")
    order = sorted(range(k), key=lambda c: (-len(set(docs[lab == c])), -int((lab == c).sum())))
    for c in order[:10]:
        idx = np.where(lab == c)[0]
        cnt = Counter(docs[idx])
        heads = [f"{rows[i].node_id.split('-')[0][:6]}/Đ{rows[i].node_id.split('-d')[1]}: {(rows[i].heading or '')[:48]}"
                 for i in idx[:6]]
        print(f"\nCụm {c}  ({len(idx)} Điều, {dict(cnt)})")
        for h in heads:
            print("   ", h)


if __name__ == "__main__":
    main()
