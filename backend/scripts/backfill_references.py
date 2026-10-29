"""Dựng cạnh dẫn chiếu giữa các node luật.

    docker compose exec api python -m scripts.backfill_references --dry-run
    docker compose exec api python -m scripts.backfill_references

Chỉ giữ dẫn chiếu trỏ tới node có thật trong kho — đó cũng là bộ lọc nhiễu
chính: một dẫn chiếu đoán sai văn bản thường không khớp node nào.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from sqlalchemy import text as sa_text

from app.db.base import engine
from app.ingestion.references import extract_refs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="chỉ thống kê, không ghi")
    ap.add_argument("--samples", type=int, default=12, help="số ví dụ in ra")
    args = ap.parse_args()

    with engine.begin() as conn:
        rows = conn.execute(sa_text(
            "SELECT node_id, doc_id, parent_id, level, text FROM legal_node"
        )).all()

        by_id = {r.node_id: r for r in rows}
        known = set(by_id)

        # toàn văn của mỗi Điều = text của nó + text mọi hậu duệ, dùng làm ngữ cảnh
        article_of: dict[str, str] = {}
        for r in rows:
            anc = r.node_id
            while anc and by_id.get(anc) and by_id[anc].level != "article":
                anc = by_id[anc].parent_id
            if anc:
                article_of[r.node_id] = anc
        article_text: dict[str, list[str]] = {}
        for r in rows:
            art = article_of.get(r.node_id)
            if art:
                article_text.setdefault(art, []).append(r.text or "")
        article_ctx = {k: " ".join(v) for k, v in article_text.items()}

        pairs: list[tuple[str, str, str]] = []
        unresolved = Counter()
        for r in rows:
            ctx = article_ctx.get(article_of.get(r.node_id, ""), None)
            for target, snippet in extract_refs(r.text or "", r.doc_id, article_context=ctx):
                if target == r.node_id:
                    continue
                if target in known:
                    pairs.append((r.node_id, target, snippet))
                else:
                    unresolved[target.split("-")[0]] += 1

        cross = sum(1 for f, t, _ in pairs if by_id[f].doc_id != by_id[t].doc_id)
        lvl = Counter(by_id[t].level for _, t, _ in pairs)

        print(f"Dẫn chiếu khớp node:  {len(pairs)}")
        print(f"  chéo văn bản:       {cross}")
        print(f"  theo cấp đích:      {dict(lvl)}")
        print(f"  node nguồn có cạnh: {len({f for f, _, _ in pairs})}")
        print(f"Không khớp node nào:  {sum(unresolved.values())} {dict(unresolved)}")

        print("\nVí dụ:")
        for f, t, s in pairs[: args.samples]:
            print(f"  {f:28s} --[{s}]--> {t}")

        if args.dry_run:
            print("\n(dry-run, chưa ghi gì)")
            return 0

        conn.execute(sa_text("""
            CREATE TABLE IF NOT EXISTS node_reference (
                from_id  VARCHAR(96) NOT NULL REFERENCES legal_node(node_id) ON DELETE CASCADE,
                to_id    VARCHAR(96) NOT NULL REFERENCES legal_node(node_id) ON DELETE CASCADE,
                ref_text TEXT,
                PRIMARY KEY (from_id, to_id)
            )
        """))
        conn.execute(sa_text("TRUNCATE node_reference"))
        for i in range(0, len(pairs), 500):
            conn.execute(
                sa_text(
                    "INSERT INTO node_reference (from_id, to_id, ref_text) "
                    "VALUES (:f, :t, :s) ON CONFLICT DO NOTHING"
                ),
                [{"f": f, "t": t, "s": s} for f, t, s in pairs[i:i + 500]],
            )
        print(f"\nĐã ghi {len(pairs)} cạnh vào node_reference.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
