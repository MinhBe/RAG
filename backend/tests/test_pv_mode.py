"""Chế độ ẩn /pv: đồ thị, tra cứu và hỏi đáp trên bộ câu hỏi phỏng vấn."""

from collections import Counter

import pytest

from app.pv.graph import build_pv_graph
from app.pv.library import load_library


def test_graph_covers_the_whole_library_without_a_query():
    g = build_pv_graph(None, "", 150)
    types = Counter(n["type"] for n in g["nodes"])
    n_items = sum(len(grp["items"]) for grp in load_library())
    assert types["item"] == n_items and types["group"] == len(load_library())
    assert types["layer"] <= 4
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])


def test_graph_keeps_only_tags_shared_by_two_questions():
    g = build_pv_graph(None, "", 150)
    per_tag = Counter(e["target"] for e in g["edges"] if e["type"] == "tagged")
    assert per_tag and min(per_tag.values()) >= 2


def test_run_chat_routes_pv_mode_to_the_interview_library(monkeypatch):
    from app.agent import pipeline
    from app.pv import qa

    monkeypatch.setattr(qa, "answer_pv", lambda m, h: iter([("token", {"text": "pv"}), ("done", {})]))
    assert list(pipeline.run_chat("RAG là gì?", [], "pv"))[0] == ("token", {"text": "pv"})


def test_answer_pv_drops_invented_citations(monkeypatch):
    from app.pv import qa

    hit = {"node_id": "G06-A02", "display": "G06-A02 · Chunk", "text": "...", "score": 0.8}

    class Router:
        def extract_json(self, msgs, task):
            return {"summary": "Theo cấu trúc.", "sections": [],
                    "citation_node_ids": ["G06-A02", "G99-X99"]}

    monkeypatch.setattr(qa, "get_router", Router)
    monkeypatch.setattr(qa, "SessionLocal", lambda: type("S", (), {"close": lambda self: None})())
    monkeypatch.setattr(qa, "search_with_history", lambda *a, **k: [hit])
    cites = [d["node_id"] for e, d in qa.answer_pv("chunking?") if e == "citation"]
    assert cites == ["G06-A02"]


@pytest.mark.db
def test_search_pv_finds_the_chunking_question(db):
    from app.pv.search import search_pv

    hits = search_pv(db, "chunk văn bản pháp lý theo Điều Khoản hay theo số ký tự", top_k=5)
    if not hits:
        pytest.skip("pv_chunk trống — chạy scripts.embed_pv trước")
    assert {"G06-A02", "G00-A11"} & {h["node_id"] for h in hits[:3]}
