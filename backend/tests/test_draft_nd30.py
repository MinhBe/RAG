"""Soạn văn bản theo thể thức NĐ30 (thay cho scripts/smoke_draft.py)."""

from dataclasses import replace

import pytest

from app.draft.nd30 import DraftInput, format_check, render_docx, render_text

VALID = DraftInput(
    doc_type="quyet_dinh",
    org_parent="CÔNG TY CỔ PHẦN ABC",
    org_name="Phòng Nhân sự",
    number="12/QĐ-NS",
    subject="Về việc xử lý kỷ luật lao động",
    bases=["Bộ luật Lao động ngày 20 tháng 11 năm 2019"],
    body="Điều 1. Thi hành kỷ luật lao động bằng hình thức khiển trách.",
    signer_title="GIÁM ĐỐC",
    signer_name="Trần Văn B",
    date_str="ngày 01 tháng 10 năm 2026",
)


def test_valid_draft_has_no_warnings():
    assert format_check(VALID) == []


@pytest.mark.parametrize(
    ("change", "warning"),
    [
        ({"doc_type": "don_xin"}, "Loại văn bản không hợp lệ"),
        ({"org_name": "  "}, "Thiếu tên cơ quan ban hành"),
        ({"subject": ""}, "Thiếu trích yếu"),
        ({"body": ""}, "Thiếu nội dung chính"),
        ({"bases": []}, "Căn cứ"),
        ({"signer_name": ""}, "Thiếu họ tên người ký"),
        ({"number": None}, "Thiếu số/ký hiệu"),
    ],
)
def test_each_missing_part_is_flagged(change, warning):
    issues = format_check(replace(VALID, **change))
    assert any(warning in i for i in issues), issues


def test_rendered_text_has_the_nd30_skeleton():
    text = render_text(VALID)
    for part in [
        "CÔNG TY CỔ PHẦN ABC",
        "PHÒNG NHÂN SỰ",                      # cơ quan ban hành viết hoa
        "Số: 12/QĐ-NS",
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "Độc lập - Tự do - Hạnh phúc",
        "Hà Nội, ngày 01 tháng 10 năm 2026",
        "Căn cứ Bộ luật Lao động ngày 20 tháng 11 năm 2019;",
        "Nơi nhận:",
        "Trần Văn B",
    ]:
        assert part in text, part
    # quốc hiệu đứng trước tên loại văn bản
    assert text.index("CỘNG HÒA") < text.index("QUYẾT ĐỊNH")


@pytest.mark.parametrize(
    "recipients",
    [
        ["Như trên", "Lưu: VT."],        # mặc định: dòng cuối người dùng đã gõ dấu chấm
        ["Như trên;", "Phòng KT", "Lưu: VT"],
    ],
)
def test_recipients_end_with_semicolon_and_the_last_with_period(recipients):
    text = render_text(replace(VALID, recipients=recipients))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- ")]
    assert lines[-1].endswith("VT.") and not lines[-1].endswith(".;")
    assert all(ln.endswith(";") and not ln.endswith(";;") for ln in lines[:-1])


def test_docx_recipients_match_text():
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(render_docx(VALID)))
    lines = [p.text for p in doc.paragraphs if p.text.startswith("- ")]
    assert lines == ["- Như trên;", "- Lưu: VT."]


def test_docx_is_a_real_office_file():
    data = render_docx(VALID)
    assert data[:2] == b"PK"          # .docx là file zip
    assert len(data) > 5_000
