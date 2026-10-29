"""Tra cứu bộ câu hỏi phỏng vấn trong pv_chunk (chế độ ẩn /pv).

Trả về cùng dạng với app/rag/search.search_nodes (node_id, display, text, score)
để luồng hỏi đáp và đồ thị dùng lại được. Mỗi câu có 3 đoạn nên lấy dư rồi gộp
theo mã câu, giữ điểm cao nhất; text trả về là trọn câu để LLM có đủ ngữ cảnh.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.pv.library import load_library
from app.rag.embeddings import embed_one


@lru_cache(maxsize=1)
def items_by_id() -> dict[str, dict[str, Any]]:
    return {it["id"]: {**it, "group_title": g["title"]} for g in load_library() for it in g["items"]}


def item_display(item: dict[str, Any]) -> str:
    return f"{item['id']} · {item['title']}"


def item_text(item: dict[str, Any]) -> str:
    return (
        f"Nhóm: {item['group_title']}\nSếp hỏi: {item['question']}\n\n"
        f"Chốt kỹ thuật:\n{item['technical']}\n\n"
        f"Ví dụ tư vấn: {item['consulting']}\n\nVí dụ đàm phán: {item['negotiation']}"
    )


def search_pv(db: Session, query: str, *, top_k: int = 6) -> list[dict[str, Any]]:
    if not (db.execute(text("SELECT count(*) FROM pv_chunk WHERE embedding IS NOT NULL")).scalar() or 0):
        return []
    rows = db.execute(
        text(
            """
            SELECT item_id, 1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM pv_chunk WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :k
            """
        ),
        {"vec": str(embed_one(query)), "k": top_k * 3},
    )
    best: dict[str, float] = {}
    for item_id, score in rows:
        best.setdefault(item_id, float(score))  # đã xếp theo điểm giảm dần
    items = items_by_id()
    hits = []
    for item_id, score in list(best.items())[:top_k]:
        it = items.get(item_id)
        if it is None:  # thư viện đổi mà chưa chạy lại scripts/embed_pv
            continue
        hits.append({
            "node_id": item_id, "display": item_display(it), "text": item_text(it),
            "group": it["group"], "score": score,
        })
    return hits
