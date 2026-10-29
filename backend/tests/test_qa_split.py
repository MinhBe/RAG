"""Tình huống dài: tra từng vấn đề rồi gộp kết quả (không gọi DB / LLM thật)."""

from app.agent import qa


def _h(i):
    return {"node_id": i}


def test_issue_hits_puts_each_issue_first_and_drops_duplicates(monkeypatch):
    found = {"hậu quả chấm dứt trái luật": [_h("d41"), _h("d39"), _h("d40")],
             "nghĩa vụ khi sáp nhập": [_h("d43"), _h("d41"), _h("d44")]}
    monkeypatch.setattr(qa, "search_nodes", lambda db, q, top_k: found[q][:top_k])
    whole = [_h("d179"), _h("d182"), _h("d43")]
    out = [h["node_id"] for h in qa._issue_hits(None, list(found), whole)]
    assert out == ["d41", "d39", "d40", "d43", "d44", "d179", "d182"]


def test_split_issues_falls_back_to_no_split_on_error():
    class Router:
        def extract_json(self, msgs, task):
            raise RuntimeError("Dahl lỗi")

    assert qa._split_issues(Router(), "tình huống") == []


def test_long_case_threshold_leaves_normal_questions_alone():
    assert len("Thời gian thử việc tối đa là bao lâu?".split()) < qa.LONG_CASE_WORDS
