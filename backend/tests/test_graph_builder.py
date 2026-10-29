"""Bất biến của knowledge graph — những thứ từng hỏng thật trong lúc phát triển.

- node mồ côi: node thêm sau khi dựng cạnh không có cạnh "contains", bị bố cục
  văng ra xa hàng nghìn đơn vị
- cạnh trỏ tới node không có trong kết quả làm d3 ném lỗi
- nhãn in mã nội bộ (blld2019) thay cho tên văn bản
"""

from collections import Counter

import pytest

from app.graph.builder import build_graph

pytestmark = pytest.mark.db

CASES = [("", 150), ("", 40), ("nghỉ phép năm", 5), ("tiền lương làm thêm giờ", 20)]


@pytest.fixture(scope="module", params=CASES, ids=[f"{q or 'all'}-{k}" for q, k in CASES])
def graph(request, db):
    query, top_k = request.param
    return build_graph(db, query, top_k)


def test_has_nodes_and_edges(graph):
    assert graph["nodes"] and graph["edges"]


def test_no_orphans(graph):
    contained = {e["target"] for e in graph["edges"] if e["type"] == "contains"}
    orphans = [n["id"] for n in graph["nodes"] if n["type"] != "document" and n["id"] not in contained]
    assert orphans == []


def test_every_edge_end_is_a_node(graph):
    ids = {n["id"] for n in graph["nodes"]}
    dangling = [e for e in graph["edges"] if e["source"] not in ids or e["target"] not in ids]
    assert dangling == []


def test_no_duplicate_nodes_or_edges(graph):
    assert len({n["id"] for n in graph["nodes"]}) == len(graph["nodes"])
    pairs = Counter((e["source"], e["target"]) for e in graph["edges"])
    assert [p for p, c in pairs.items() if c > 1] == []


def test_hierarchy_runs_document_chapter_article(graph):
    by_id = {n["id"]: n for n in graph["nodes"]}
    triplets = {(by_id[e["source"]]["type"], e["type"], by_id[e["target"]]["type"]) for e in graph["edges"]}
    assert ("document", "contains", "chapter") in triplets
    assert ("chapter", "contains", "article") in triplets


def test_labels_use_document_names(graph):
    leaked = [n["label"] for n in graph["nodes"] if "blld" in n["label"] or "nd145" in n["label"]]
    assert leaked == []
    assert all(n.get("doc_name") for n in graph["nodes"])


def test_empty_result_is_empty_graph(db):
    # câu hỏi không khớp node nào vẫn phải trả cấu trúc rỗng hợp lệ
    out = build_graph(db, "", 0)
    assert out == {"nodes": [], "edges": [], "query": ""}
