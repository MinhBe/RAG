"""Bộ trích dẫn chiếu: phần khó là đoán đúng văn bản đích, không phải bắt con số."""

from app.ingestion.references import extract_refs


def targets(text, src_doc, **kw):
    return [t for t, _ in extract_refs(text, src_doc, **kw)]


def test_bare_reference_stays_in_source_document():
    assert targets("theo quy định tại khoản 2 Điều 35", "blld2019") == ["blld2019-d35-k2"]


def test_explicit_law_name_points_to_labour_code():
    got = targets("Người sử dụng lao động theo khoản 2 Điều 2 của Bộ luật Lao động.", "nd145_2020")
    assert got == ["blld2019-d2-k2"]


def test_this_law_means_the_source_document():
    assert targets("quy định tại Điều 35 của Bộ luật này", "blld2019") == ["blld2019-d35"]


def test_decree_bare_reference_inherits_article_context():
    # Nghị định 145 có tới Điều 115, nên "khoản 3 Điều 12" để trống tên văn bản
    # vẫn khớp được trong chính nó; ngữ cảnh của Điều cha phải kéo nó sang Bộ luật.
    ctx = "Người sử dụng lao động theo khoản 2 Điều 2 của Bộ luật Lao động. Quản lý lao động theo khoản 3 Điều 12."
    got = targets("Quản lý lao động theo khoản 3 Điều 12.", "nd145_2020", article_context=ctx)
    assert got == ["blld2019-d12-k3"]


def test_decree_without_context_falls_back_to_itself():
    assert targets("theo khoản 3 Điều 12", "nd145_2020") == ["nd145_2020-d12-k3"]


def test_point_clause_article_and_lists():
    got = targets("điểm d khoản 1 Điều 35, điểm d khoản 2 Điều 36; khoản 4 Điều 46", "blld2019")
    assert got == ["blld2019-d35-k1-d", "blld2019-d36-k2-d", "blld2019-d46-k4"]


def test_old_code_naming_itself_stays_old():
    assert targets("khoản 1 Điều 37 của Bộ luật Lao động", "blld2012") == ["blld2012-d37-k1"]


def test_repeated_reference_is_reported_once():
    assert targets("Điều 35 và Điều 35", "blld2019") == ["blld2019-d35"]


def test_empty_text():
    assert extract_refs("", "blld2019") == []
