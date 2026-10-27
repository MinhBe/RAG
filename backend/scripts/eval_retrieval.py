"""Retrieval smoke eval: recall@k and MRR for BM25, dense and hybrid.

python scripts/eval_retrieval.py [--embedder hashing|bge-m3]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import REPO_ROOT, get_settings  # noqa: E402
from app.rag.embeddings import build_embedder  # noqa: E402
from app.rag.index import HybridIndex  # noqa: E402
from app.rag.loader import load_documents  # noqa: E402

KS = (1, 3, 5)


def is_relevant(hit, case) -> bool:
    return hit.chunk.doc_id == case["doc_id"] and case["section"].lower() in hit.chunk.section.lower()


def evaluate(index: HybridIndex, cases: list[dict], mode: str) -> dict:
    recall = {k: 0 for k in KS}
    rr_total = 0.0
    misses = []
    for case in cases:
        hits = index.search(case["question"], top_k=max(KS), mode=mode)
        rank = next((i for i, h in enumerate(hits, start=1) if is_relevant(h, case)), None)
        for k in KS:
            recall[k] += rank is not None and rank <= k
        rr_total += 1 / rank if rank else 0
        if rank is None or rank > 3:
            misses.append(case["id"])
    n = len(cases)
    return {"mode": mode, **{f"recall@{k}": recall[k] / n for k in KS}, "mrr": rr_total / n, "misses@3": misses}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", default=get_settings().embedder)
    parser.add_argument("--cases", default=str(REPO_ROOT / "eval" / "retrieval_smoke.jsonl"))
    args = parser.parse_args()

    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    index = HybridIndex(load_documents(get_settings().data_dir), build_embedder(args.embedder))
    print(f"{len(cases)} questions, {len(index.chunks)} chunks, embedder={index.embedder.name}\n")
    print(f"{'mode':<8} {'R@1':>6} {'R@3':>6} {'R@5':>6} {'MRR':>6}  misses@3")
    for mode in ("bm25", "dense", "hybrid"):
        r = evaluate(index, cases, mode)
        print(
            f"{mode:<8} {r['recall@1']:>6.2f} {r['recall@3']:>6.2f} {r['recall@5']:>6.2f} {r['mrr']:>6.2f}  {','.join(r['misses@3']) or '-'}"
        )


if __name__ == "__main__":
    main()
