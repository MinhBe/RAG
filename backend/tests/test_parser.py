"""Test parser trên một đoạn luật lao động giả lập cấu trúc thật."""

from app.ingestion.parser import assign_ids, parse_articles, validate

SAMPLE = """Chương I
NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Bộ luật Lao động quy định tiêu chuẩn lao động.
Điều 2. Đối tượng áp dụng
1. Người lao động, người học nghề, người tập việc.
2. Người sử dụng lao động.
Điều 25. Thời gian thử việc
Thời gian thử việc do hai bên thỏa thuận, chỉ được thử việc một lần, bảo đảm:
1. Không quá 180 ngày đối với công việc của người quản lý doanh nghiệp.
2. Không quá 60 ngày đối với công việc cần trình độ cao đẳng trở lên.
3. Không quá 30 ngày đối với công việc cần trình độ trung cấp.
4. Không quá 06 ngày làm việc đối với công việc khác.
"""


def test_parse_structure():
    arts = parse_articles(SAMPLE)
    assert [a["number"] for a in arts] == [1, 2, 25]
    a25 = arts[-1]
    assert a25["heading"] == "Thời gian thử việc"
    assert len(a25["clauses"]) == 4
    assert "180 ngày" in a25["clauses"][0]["text"]


def test_assign_ids():
    arts = parse_articles(SAMPLE)
    assign_ids("blld2019", arts)
    assert arts[-1]["article_id"] == "blld2019-d25"
    assert arts[-1]["clauses"][0]["clause_id"] == "blld2019-d25-k1"


def test_validate_clean():
    arts = parse_articles(SAMPLE)
    errs = validate(arts, SAMPLE)
    # Điều không liên tục (1,2,25) là cảnh báo hợp lệ với đoạn trích; bỏ qua lỗi đó.
    non_seq = [e for e in errs if "không liên tục" not in e]
    assert non_seq == [], non_seq
