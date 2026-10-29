"""Luồng có gọi LLM thật: hỏi đáp có trích dẫn, báo cáo nhiều văn bản, tổng hợp án lệ.

Thay cho scripts/smoke_qa.py, smoke_report.py, smoke_precedent.py. Tốn quota nên
mặc định bỏ qua; chạy bằng:  RUN_LLM_TESTS=1 python -m pytest -m llm
"""

import pytest

pytestmark = [pytest.mark.db, pytest.mark.llm]


def _collect(events):
    out = {"token": "", "citation": [], "section": [], "error": []}
    for name, data in events:
        if name == "token":
            out["token"] += data["text"]
        elif name in out:
            out[name].append(data)
    return out


def test_qa_cites_the_probation_article(db):
    from app.agent.qa import answer_with_citations

    res = _collect(answer_with_citations("Thời gian thử việc tối đa là bao lâu?"))
    assert res["error"] == []
    assert res["token"].strip()
    cited = [c["node_id"] for c in res["citation"]]
    assert any(c.startswith("blld2019-d25") for c in cited), cited


def test_qa_only_cites_retrieved_nodes(db):
    """LLM bịa node_id thì phải bị lọc bỏ trước khi tới người dùng."""
    from app.agent.qa import answer_with_citations
    from app.db.models import LegalNode

    res = _collect(answer_with_citations("Làm thêm giờ tối đa bao nhiêu giờ một năm?"))
    for c in res["citation"]:
        assert db.get(LegalNode, c["node_id"]) is not None, c["node_id"]


def test_multi_document_report(db):
    from app.report.multi_doc import build_report

    r = build_report("quy định về làm thêm giờ và thời giờ nghỉ ngơi", top_k=12)
    assert len(r["markdown"]) > 200
    assert r["sources"]


def test_precedent_synthesis(db):
    from sqlalchemy import text

    from app.agent.precedent import synthesize

    if not db.execute(text("SELECT count(*) FROM precedent")).scalar():
        pytest.skip("chưa nạp án lệ (fetch_precedents)")
    r = synthesize("tranh chấp về đơn phương chấm dứt hợp đồng lao động trái pháp luật", top_k=3)
    assert r["summary"].strip()
    assert 0 < len(r["cases"]) <= 3
