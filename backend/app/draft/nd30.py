"""Soạn văn bản hành chính theo thể thức Nghị định 30/2020/NĐ-CP (M5).

Hỗ trợ: quyết định, công văn, thông báo, tờ trình. Phần "Căn cứ" lấy từ RAG
(chỉ văn bản còn hiệu lực). Có kiểm tra thể thức và xuất DOCX. Quy trình có bước
duyệt (HITL) trước khi xuất — xem routes /api/draft/preview và /api/draft/export.

Tham khảo cấu trúc thể thức: vbhc / ND30_Skills (ghi nguồn).
"""

from __future__ import annotations

from dataclasses import dataclass, field

DOC_TYPES = {
    "quyet_dinh": "QUYẾT ĐỊNH",
    "cong_van": "CÔNG VĂN",
    "thong_bao": "THÔNG BÁO",
    "to_trinh": "TỜ TRÌNH",
}

QUOC_HIEU = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
TIEU_NGU = "Độc lập - Tự do - Hạnh phúc"


@dataclass
class DraftInput:
    doc_type: str  # key trong DOC_TYPES
    org_name: str  # tên cơ quan ban hành
    org_parent: str | None = None  # cơ quan chủ quản (nếu có)
    number: str | None = None  # số/ký hiệu, vd "12/QĐ-..."
    place: str = "Hà Nội"  # địa danh
    date_str: str | None = None  # ngày tháng năm (tự điền nếu trống)
    subject: str = ""  # trích yếu nội dung
    bases: list[str] = field(default_factory=list)  # các "Căn cứ"
    body: str = ""  # nội dung chính
    signer_title: str = "GIÁM ĐỐC"  # chức vụ người ký
    signer_name: str = ""  # họ tên người ký
    recipients: list[str] = field(default_factory=lambda: ["Như trên", "Lưu: VT."])


def _today_vn() -> str:
    from datetime import date

    d = date.today()
    return f"ngày {d.day:02d} tháng {d.month:02d} năm {d.year}"


def _recipient_lines(recipients: list[str]) -> list[str]:
    """Theo NĐ30: mỗi nơi nhận kết thúc bằng ";", riêng dòng cuối bằng "."."""
    items = [r.strip().rstrip(";.").strip() for r in recipients if r.strip()]
    return [f"- {r}{'.' if i == len(items) - 1 else ';'}" for i, r in enumerate(items)]


def format_check(d: DraftInput) -> list[str]:
    """Kiểm tra thể thức tối thiểu theo NĐ30. Trả list cảnh báo."""
    issues = []
    if d.doc_type not in DOC_TYPES:
        issues.append(f"Loại văn bản không hợp lệ: {d.doc_type}")
    if not d.org_name.strip():
        issues.append("Thiếu tên cơ quan ban hành.")
    if not d.subject.strip():
        issues.append("Thiếu trích yếu nội dung (phần tên loại và trích yếu).")
    if not d.body.strip():
        issues.append("Thiếu nội dung chính.")
    if d.doc_type == "quyet_dinh" and not d.bases:
        issues.append("Quyết định nên có phần 'Căn cứ'.")
    if not d.signer_name.strip():
        issues.append("Thiếu họ tên người ký.")
    if not d.number:
        issues.append("Thiếu số/ký hiệu văn bản.")
    return issues


def render_text(d: DraftInput) -> str:
    """Bản xem trước dạng text theo bố cục NĐ30."""
    date_str = d.date_str or _today_vn()
    type_label = DOC_TYPES.get(d.doc_type, d.doc_type.upper())
    L: list[str] = []
    # Khối cơ quan (trái) và quốc hiệu (phải) — trình bày tuyến tính cho text.
    if d.org_parent:
        L.append(d.org_parent.upper())
    L.append(d.org_name.upper())
    L.append(f"Số: {d.number or '..../'}")
    L.append("")
    L.append(QUOC_HIEU)
    L.append(TIEU_NGU)
    L.append(f"{d.place}, {date_str}")
    L.append("")
    L.append(type_label)
    if d.subject:
        if d.doc_type == "cong_van":
            L.append(f"V/v {d.subject}")
        else:
            L.append(d.subject)
    L.append("")
    if d.bases:
        for b in d.bases:
            L.append(f"Căn cứ {b};")
        L.append("")
    L.append(d.body.strip())
    L.append("")
    L.append(f"{'Nơi nhận:':<40}{d.signer_title}")
    L.extend(_recipient_lines(d.recipients))
    L.append("")
    L.append(f"{'':<40}{d.signer_name}")
    return "\n".join(L)


def render_docx(d: DraftInput) -> bytes:
    """Xuất DOCX theo thể thức NĐ30 (căn lề, canh giữa quốc hiệu/tên loại)."""
    import io

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    date_str = d.date_str or _today_vn()
    type_label = DOC_TYPES.get(d.doc_type, d.doc_type.upper())

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)

    def p(text="", *, align=None, bold=False, italic=False, size=None):
        par = doc.add_paragraph()
        run = par.add_run(text)
        run.bold = bold
        run.italic = italic
        if size:
            run.font.size = Pt(size)
        if align:
            par.alignment = align
        return par

    center = WD_ALIGN_PARAGRAPH.CENTER

    # Quốc hiệu - tiêu ngữ (canh giữa, trên cùng theo mẫu rút gọn)
    p(QUOC_HIEU, align=center, bold=True)
    p(TIEU_NGU, align=center, bold=True)
    p("")
    if d.org_parent:
        p(d.org_parent.upper())
    p(d.org_name.upper(), bold=True)
    p(f"Số: {d.number or '..../'}")
    p(f"{d.place}, {date_str}", align=WD_ALIGN_PARAGRAPH.RIGHT, italic=True)
    p("")
    p(type_label, align=center, bold=True, size=14)
    if d.subject:
        p(f"V/v {d.subject}" if d.doc_type == "cong_van" else d.subject, align=center, bold=True)
    p("")
    for b in d.bases:
        p(f"Căn cứ {b};", italic=True)
    if d.bases:
        p("")
    for para in d.body.strip().split("\n"):
        p(para)
    p("")

    # Nơi nhận + chữ ký (hai cột rút gọn)
    p("Nơi nhận:", bold=True, italic=True)
    for line in _recipient_lines(d.recipients):
        p(line)
    p("")
    p(d.signer_title, align=center, bold=True)
    p("")
    p("")
    p(d.signer_name, align=center, bold=True)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
