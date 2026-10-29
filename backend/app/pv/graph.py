"""Knowledge graph của bộ câu hỏi phỏng vấn (chế độ ẩn /pv).

Cùng dạng dữ liệu với app/graph/builder.build_graph để trang /graph vẽ được mà
không đổi giao diện; chỉ đổi ontology:

    Nhóm (group) ──chứa──▶ Câu hỏi (item) ──thuộc lớp──▶ Lớp (layer: A/B/C/T)
                                 └──gắn thẻ──▶ Chủ đề (tag)

Chỉ giữ chủ đề có từ hai câu trở lên trong cả thư viện: chủ đề một câu không nối
được hai câu với nhau, chỉ thêm nhiễu.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.pv.library import LAYERS, load_library
from app.pv.search import search_pv

_TEXT_PREVIEW = 600


@lru_cache(maxsize=1)
def _shared_tags() -> frozenset[str]:
    count = Counter(t for g in load_library() for it in g["items"] for t in it["tags"])
    return frozenset(t for t, n in count.items() if n >= 2)


def _node(id_: str, type_: str, label: str, group: str, heading: str, text: str = "", score: float = 0.0):
    return {
        "id": id_, "label": label, "doc_id": group, "doc_type": "pv", "level": type_, "type": type_,
        "heading": heading, "text": text[:_TEXT_PREVIEW], "score": score, "ghost": False,
    }


def build_pv_graph(db: Session, query: str, top_k: int) -> dict[str, Any]:
    """Không có query: cả thư viện. Có query: các câu gần nhất cùng nhóm, lớp, chủ đề của chúng."""
    scores: dict[str, float] | None = None
    if query.strip():
        scores = {h["node_id"]: h["score"] for h in search_pv(db, query, top_k=min(top_k, 40))}

    shared = _shared_tags()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(node: dict[str, Any]) -> None:
        if node["id"] not in seen:
            seen.add(node["id"])
            nodes.append(node)

    for g in load_library():
        items = [it for it in g["items"] if scores is None or it["id"] in scores]
        if not items:
            continue
        add(_node(g["group"], "group", f"{g['group']} · {g['title']}", g["group"], g["title"]))
        for it in items:
            add(_node(it["id"], "item", it["id"], g["group"], it["title"], it["question"],
                      (scores or {}).get(it["id"], 0.0)))
            edges.append({"source": g["group"], "target": it["id"], "type": "contains"})
            layer = f"layer:{it['layer']}"
            add(_node(layer, "layer", f"{it['layer']} · {LAYERS.get(it['layer'], '')}", "layer",
                      LAYERS.get(it["layer"], it["layer"])))
            edges.append({"source": it["id"], "target": layer, "type": "in_layer"})
            for tag in it["tags"]:
                if tag in shared:
                    add(_node(f"tag:{tag}", "tag", tag, "tag", tag))
                    edges.append({"source": it["id"], "target": f"tag:{tag}", "type": "tagged"})
    return {"nodes": nodes, "edges": edges, "query": query}
