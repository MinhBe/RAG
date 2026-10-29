"""Câu hỏi nối tiếp trong hội thoại (app/agent/followup.py).

Lỗi gốc: answer_with_citations nhận history nhưng không dùng, nên "còn với người
quản lý thì sao?" được tra như một câu độc lập.
"""

import pytest

from app.agent.followup import (
    history_block,
    last_user_question,
    looks_like_follow_up,
    merge_hits,
    search_with_history,
)


def H(*ids):
    return [{"node_id": i} for i in ids]


HISTORY = [
    {"role": "user", "content": "Thời gian thử việc tối đa là bao lâu?"},
    {"role": "assistant", "content": "Tối đa 180 ngày với người quản lý doanh nghiệp."},
]


def test_last_user_question_skips_assistant_and_blank_turns():
    hist = [*HISTORY, {"role": "assistant", "content": "x"}, {"role": "user", "content": "  "}]
    assert last_user_question(hist) == "Thời gian thử việc tối đa là bao lâu?"
    assert last_user_question([]) is None
    assert last_user_question(None) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Còn với người quản lý doanh nghiệp thì sao?", True),
        ("Vậy tiền lương trả thế nào?", True),
        ("Thế phải báo trước bao nhiêu ngày?", True),
        ("Trường hợp đó có bị phạt không?", True),
        ("người quản lý thì?", True),                           # câu cụt
        ("Tuổi nghỉ hưu của người lao động là bao nhiêu?", False),
        ("Người sử dụng lao động có được đơn phương chấm dứt hợp đồng không?", False),
    ],
)
def test_looks_like_follow_up(text, expected):
    assert looks_like_follow_up(text) is expected


def test_merge_gives_primary_most_slots_and_dedupes():
    out = merge_hits(H("a1", "a2", "a3", "a4", "a5", "a6", "a7"), H("b1", "a1", "b2", "b3"), 8)
    ids = [h["node_id"] for h in out]
    assert ids[:6] == ["a1", "a2", "a3", "a4", "a5", "a6"]   # 3/4 của 8 chỗ
    assert ids[6:] == ["b1", "b2"]                            # a1 trùng bị bỏ
    assert len(ids) == len(set(ids)) == 8


def test_merge_fills_from_primary_when_secondary_runs_out():
    ids = [h["node_id"] for h in merge_hits(H("a1", "a2", "a3", "a4"), H("b1"), 4)]
    assert ids == ["a1", "a2", "a3", "b1"]


class FakeSearch:
    def __init__(self):
        self.queries = []

    def __call__(self, db, query, top_k):
        self.queries.append(query)
        return H(*(f"{query[:6]}-{i}" for i in range(top_k)))


def test_no_history_searches_once_with_the_message():
    fake = FakeSearch()
    out = search_with_history(None, "Tuổi nghỉ hưu?", [], top_k=4, search=fake)
    assert fake.queries == ["Tuổi nghỉ hưu?"]
    assert len(out) == 4


def test_follow_up_puts_combined_query_first():
    fake = FakeSearch()
    out = search_with_history(None, "Còn người quản lý thì sao?", HISTORY, top_k=8, search=fake)
    assert fake.queries == ["Còn người quản lý thì sao?", "Thời gian thử việc tối đa là bao lâu? Còn người quản lý thì sao?"]
    assert out[0]["node_id"].startswith("Thời g")             # truy vấn ghép đứng đầu


def test_new_topic_keeps_its_own_results_first():
    fake = FakeSearch()
    out = search_with_history(None, "Tuổi nghỉ hưu của người lao động là bao nhiêu?", HISTORY, top_k=8, search=fake)
    assert out[0]["node_id"].startswith("Tuổi n")
    assert sum(h["node_id"].startswith("Tuổi n") for h in out) == 6


def test_history_block_keeps_two_user_turns_and_trims_answers():
    long_answer = "x" * 500
    hist = [
        {"role": "user", "content": "câu 1"},
        {"role": "assistant", "content": "trả lời 1"},
        {"role": "user", "content": "câu 2"},
        {"role": "assistant", "content": long_answer},
        {"role": "user", "content": "câu 3"},
    ]
    block = history_block(hist)
    assert "câu 1" not in block
    assert block.splitlines()[0] == "Người dùng: câu 2"
    assert "Người dùng: câu 3" in block
    assert len(block.splitlines()[1]) < 320 and block.splitlines()[1].endswith("…")
    assert history_block([]) == ""


# ── trên kho thật: chính các ca đã đo khi sửa lỗi ───────────────────────────

CASES = [
    ("Thời gian thử việc tối đa là bao lâu?", "Còn với người quản lý doanh nghiệp thì sao?", "blld2019-d25"),
    ("Người lao động được nghỉ phép năm bao nhiêu ngày?", "Làm lâu năm thì có được tăng thêm không?", "blld2019-d114"),
    ("Làm thêm giờ tối đa bao nhiêu giờ một năm?", "Vậy tiền lương trả thế nào?", "blld2019-d98"),
    ("Người sử dụng lao động có được đơn phương chấm dứt hợp đồng không?", "Thế phải báo trước bao nhiêu ngày?", "blld2019-d36"),
    # đối chứng: câu hỏi mới khác chủ đề không được bị lịch sử làm nhiễu
    ("Người lao động được nghỉ phép năm bao nhiêu ngày?", "Tuổi nghỉ hưu của người lao động là bao nhiêu?", "blld2019-d169"),
]


@pytest.mark.db
@pytest.mark.parametrize(("prev", "message", "article"), CASES)
def test_answering_article_reaches_the_llm_context(db, prev, message, article):
    from app.rag.search import search_nodes

    history = [{"role": "user", "content": prev}, {"role": "assistant", "content": "…"}]
    hits = search_with_history(db, message, history, top_k=8, search=search_nodes)
    articles = ["-".join(h["node_id"].split("-")[:2]) for h in hits]
    assert article in articles, articles
