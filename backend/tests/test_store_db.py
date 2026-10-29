"""Tra cứu, hiệu lực theo ngày, lịch sử sửa đổi, tên văn bản — trên kho thật.

Thay cho scripts/smoke_asof.py, phần tra cứu của smoke_qa.py và phần
node_history của smoke_report.py: các script đó chỉ in ra, không kiểm gì.
"""

from datetime import date

import pytest
from sqlalchemy import text

from app.amend.store import law_as_of, node_history
from app.rag.search import doc_name, search_nodes

pytestmark = pytest.mark.db


def _titles(rows):
    return {r["title"] for r in rows}


def test_law_as_of_2015_is_the_2012_code(db):
    titles = _titles(law_as_of(db, date(2015, 6, 1)))
    assert "Bộ luật Lao động 2012" in titles
    assert "Bộ luật Lao động 2019" not in titles


def test_law_as_of_2023_replaces_2012_with_2019(db):
    titles = _titles(law_as_of(db, date(2023, 6, 1)))
    assert "Bộ luật Lao động 2019" in titles
    assert "Bộ luật Lao động 2012" not in titles


def test_node_history_follows_supersession_to_2019(db):
    old_id = db.execute(text("SELECT old_id FROM node_supersession ORDER BY old_id LIMIT 1")).scalar()
    if old_id is None:
        pytest.skip("chưa chạy run_diff: không có quan hệ sửa đổi")
    chain = node_history(db, old_id)
    assert chain[0]["node_id"] == old_id and chain[0]["step"] == 0
    assert len(chain) >= 2
    assert chain[1]["node_id"].startswith("blld2019-")


@pytest.mark.parametrize(
    ("question", "article"),
    [
        ("Thời gian thử việc tối đa là bao lâu?", "blld2019-d25"),
        ("Thời giờ làm việc bình thường trong một ngày tối đa là bao nhiêu giờ?", "blld2019-d105"),
        ("Tuổi nghỉ hưu của người lao động là bao nhiêu?", "blld2019-d169"),
    ],
)
def test_search_finds_the_answering_article_in_top3(db, question, article):
    hits = search_nodes(db, question, top_k=3)
    articles = {"-".join(h["node_id"].split("-")[:2]) for h in hits}
    assert article in articles, [h["node_id"] for h in hits]


def test_search_hits_carry_level_and_readable_name(db):
    hits = search_nodes(db, "nghỉ hằng năm", top_k=5)
    assert all(h["level"] in {"article", "clause", "point"} for h in hits)
    assert all("blld" not in h["display"] and "nd145" not in h["display"] for h in hits)


@pytest.mark.parametrize(
    ("doc_id", "name"),
    [
        ("blld2019", "Bộ luật Lao động 2019"),
        ("blld2012", "Bộ luật Lao động 2012"),
        ("nd145_2020", "Nghị định 145/2020/NĐ-CP"),
        ("khong_co", "khong_co"),
    ],
)
def test_doc_name(db, doc_id, name):
    assert doc_name(doc_id) == name
